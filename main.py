"""
Parking Valet Geneva — Voice AI Backend
Version: 2.0 (Production Fixed)
FastAPI + Twilio WhatsApp Dispatcher
"""

from fastapi import FastAPI, Request, HTTPException
from twilio.rest import Client
from datetime import datetime
import os
import time
import logging
from dotenv import load_dotenv

# ─────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Parking Valet Geneva — Dispatch API", version="2.0")


# ─────────────────────────────────────────
# ENVIRONMENT VARIABLES
# ─────────────────────────────────────────

TWILIO_SID      = os.getenv("TWILIO_SID")
TWILIO_AUTH     = os.getenv("TWILIO_AUTH")
TWILIO_FROM     = os.getenv("TWILIO_FROM")       # e.g. "whatsapp:+14155238886"
DRIVER_NUMBER   = os.getenv("DRIVER_NUMBER")     # e.g. "whatsapp:+41XXXXXXXXX"
VAPI_SECRET     = os.getenv("VAPI_SECRET", "")   # Optional: shared secret for request validation

# Validate on startup
missing = [k for k, v in {
    "TWILIO_SID": TWILIO_SID,
    "TWILIO_AUTH": TWILIO_AUTH,
    "TWILIO_FROM": TWILIO_FROM,
    "DRIVER_NUMBER": DRIVER_NUMBER,
}.items() if not v]

if missing:
    logger.warning(f"Missing environment variables: {', '.join(missing)}")


# ─────────────────────────────────────────
# DEDUPLICATION CACHE (TTL-based)
# Prevents duplicate SMS if Vapi retries
# ─────────────────────────────────────────

processed_calls: dict[str, float] = {}
DEDUP_TTL_SECONDS = 3600  # 1 hour


def is_duplicate(tool_call_id: str) -> bool:
    """
    Returns True if this tool_call_id was already processed.
    Also cleans up expired entries to prevent memory growth.
    """
    now = time.time()

    # Remove entries older than TTL
    expired_keys = [k for k, v in processed_calls.items() if now - v > DEDUP_TTL_SECONDS]
    for k in expired_keys:
        del processed_calls[k]

    if tool_call_id in processed_calls:
        return True

    processed_calls[tool_call_id] = now
    return False


# ─────────────────────────────────────────
# HELPER: Build WhatsApp Message
# ─────────────────────────────────────────

def build_whatsapp_message(
    name: str,
    booking_id: str,
    pax_count: int,
    luggage_ready: bool,
    meeting_point: bool,
    timestamp: str,
) -> str:
    return (
        f"ARRIVEE CLIENT\n"
        f"--------------\n"
        f"Nom      : {name}\n"
        f"Booking  : {booking_id}\n"
        f"Pax      : {pax_count}\n"
        f"Bagages  : {'Oui' if luggage_ready else 'Non'}\n"
        f"Point RDV: {'Oui' if meeting_point else 'Non'}\n"
        f"Appel    : {timestamp}"
    )


# ─────────────────────────────────────────
# HELPER: Send WhatsApp via Twilio
# ─────────────────────────────────────────

def send_whatsapp(message: str) -> bool:
    """
    Sends a WhatsApp message to the driver/dispatcher.
    Returns True on success, False on failure.
    """
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        client.messages.create(
            body=message,
            from_=TWILIO_FROM,
            to=DRIVER_NUMBER,
        )
        logger.info("WhatsApp message sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Twilio send failed: {e}")
        return False


# ─────────────────────────────────────────
# MAIN WEBHOOK ENDPOINT
# Vapi calls this when notify_operations fires
# ─────────────────────────────────────────

@app.post("/notify")
async def notify_operations(request: Request):

    # ── 1. Parse JSON body ──
    try:
        data = await request.json()
        logger.info(f"Incoming payload: {data}")
    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON request")

    # ── 2. Extract tool call from Vapi payload ──
    try:
        tool_call    = data["message"]["toolCallList"][0]
        args         = tool_call["function"]["arguments"]
        tool_call_id = tool_call["id"]
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Tool call extraction failed: {e}")
        raise HTTPException(status_code=422, detail="Could not extract tool call data")

    # ── 3. Deduplication check ──
    if is_duplicate(tool_call_id):
        logger.warning(f"Duplicate tool call ignored: {tool_call_id}")
        return {
            "results": [{
                "toolCallId": tool_call_id,
                "result": "Already processed"
            }]
        }

    logger.info(f"Processing tool call: {tool_call_id}")

    # ── 4. Extract arguments with safe defaults ──
    try:
        name          = str(args.get("name", "Unknown")).strip()
        booking_id    = str(args.get("booking_id", "Unknown")).strip().upper()
        pax_count     = int(args.get("pax_count", 0))
        luggage_ready = bool(args.get("luggage_ready", True))
        meeting_point = bool(args.get("meeting_point", True))
        timestamp     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.error(f"Argument parsing error: {e}")
        raise HTTPException(status_code=422, detail="Could not parse arguments")

    logger.info(
        f"Dispatching | Name: {name} | Booking: {booking_id} | "
        f"Pax: {pax_count} | Luggage: {luggage_ready} | Meeting Point: {meeting_point}"
    )

    # ── 5. Warn if required fields are missing ──
    warnings = []
    if name == "Unknown":
        warnings.append("name is Unknown")
    if booking_id == "UNKNOWN":
        warnings.append("booking_id is Unknown")
    if pax_count == 0:
        warnings.append("pax_count is 0")

    if warnings:
        logger.warning(f"Missing fields detected: {', '.join(warnings)}")

    # ── 6. Build and send WhatsApp message ──
    message = build_whatsapp_message(
        name=name,
        booking_id=booking_id,
        pax_count=pax_count,
        luggage_ready=luggage_ready,
        meeting_point=meeting_point,
        timestamp=timestamp,
    )

    sent = send_whatsapp(message)

    if not sent:
        # Still return success to Vapi so the call flow is not broken
        # But log the failure for your ops team to investigate
        logger.error("WhatsApp delivery failed — operator must check logs")

    # ── 7. Return success to Vapi ──
    return {
        "results": [{
            "toolCallId": tool_call_id,
            "result": "Success" if sent else "SMS_FAILED — check server logs"
        }]
    }


# ─────────────────────────────────────────
# HEALTH CHECK ENDPOINT
# ─────────────────────────────────────────

@app.get("/")
def health():
    return {
        "status": "Parking Valet Geneva — Dispatch API Running",
        "version": "2.0",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "env_loaded": all([TWILIO_SID, TWILIO_AUTH, TWILIO_FROM, DRIVER_NUMBER]),
        "dedup_cache_size": len(processed_calls),
    }