from fastapi import FastAPI, Request, HTTPException
from twilio.rest import Client
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# ===== Load Twilio credentials from .env file =====
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_FROM = os.getenv("TWILIO_FROM")
DRIVER_NUMBER = os.getenv("DRIVER_NUMBER")

# ===== Track processed tool calls to prevent duplicate SMS =====
processed_calls = set()

# ===== Webhook endpoint — Vapi sends data here after call =====
@app.post("/notify")
async def notify_operations(request: Request):

    # ===== Parse incoming request =====
    try:
        data = await request.json()
        print("Received data:", data)
    except Exception as e:
        print("Request parse error:", e)
        raise HTTPException(status_code=400, detail="Invalid JSON request")

    # ===== Extract tool call arguments from Vapi payload =====
    try:
        tool_call = data["message"]["toolCallList"][0]
        args = tool_call["function"]["arguments"]
        tool_call_id = tool_call["id"]
    except Exception as e:
        print("Tool call extraction error:", e)
        raise HTTPException(status_code=422, detail="Could not extract tool call data")

    # ===== Prevent duplicate SMS for same tool call =====
    if tool_call_id in processed_calls:
        print(f"Duplicate tool call ignored: {tool_call_id}")
        return {
            "results": [{
                "toolCallId": tool_call_id,
                "result": "Already processed"
            }]
        }
    processed_calls.add(tool_call_id)
    print(f"Processing tool call ID: {tool_call_id}")

    # ===== Get customer info from extracted arguments =====
    try:
        name = args.get("name", "Unknown")
        booking_id = args.get("booking_id", "Unknown")
        pax_count = args.get("pax_count", 0)
        luggage_ready = args.get("luggage_ready", True)
        meeting_point = args.get("meeting_point", True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Name: {name} | Booking: {booking_id} | Pax: {pax_count} | Luggage: {luggage_ready} | Meeting Point: {meeting_point}")
    except Exception as e:
        print("Argument extraction error:", e)
        raise HTTPException(status_code=422, detail="Could not extract arguments")

    # ===== Validate required fields =====
    if booking_id == "Unknown" or pax_count == 0:
        print("Warning: Missing required fields")

    # ===== Build WhatsApp message =====
    try:
        whatsapp_message = (
            f"Arrivee client\n"
            f"--------------\n"
            f"Nom: {name}\n"
            f"Booking: {booking_id}\n"
            f"Pax: {pax_count}\n"
            f"Bagages: {'Oui' if luggage_ready else 'Non'}\n"
            f"Point RDV: {'Oui' if meeting_point else 'Non'}\n"
            f"Appel: {timestamp}"
        )
    except Exception as e:
        print("Message build error:", e)
        raise HTTPException(status_code=500, detail="Could not build message")

    # ===== Send WhatsApp message to driver/dispatcher =====
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        client.messages.create(
            body=whatsapp_message,
            from_=TWILIO_FROM,
            to=DRIVER_NUMBER
        )
        print("WhatsApp SMS sent successfully!")
    except Exception as e:
        print(f"SMS send error: {e}")

    # ===== Return success response back to Vapi =====
    return {
        "results": [{
            "toolCallId": tool_call_id,
            "result": "Success"
        }]
    }

# ===== Health check — confirms server is running =====
@app.get("/")
def health():
    return {
        "status": "Parking Valet Backend Running",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }