# Parking-Valet.ch AI Voice Agent System

## Project Overview
AI-powered voice agent for Parking-Valet.ch at Geneva Airport.
Handles incoming customer calls, collects arrival information,
and notifies the operations team via WhatsApp.

## Tech Stack
- Vapi.ai — Voice orchestration
- OpenAI GPT-4o Mini — AI brain
- Deepgram — Speech transcription
- Twilio — WhatsApp notifications
- FastAPI — Backend server
- Python — Backend language

## Features
- French/English bilingual support
- Automated customer data collection
- Real-time WhatsApp notifications
- Duplicate SMS prevention
- Background noise handling
- Multi-call support

## Project Structure
parking-valet/
├── main.py          # FastAPI backend
├── .env.example     # Environment variables template
├── .gitignore       # Git ignore file
└── README.md        # Project documentation

## Environment Variables
Create a .env file based on .env.example:
- TWILIO_SID
- TWILIO_AUTH
- TWILIO_FROM
- DRIVER_NUMBER

## Setup
1. Install dependencies:
   pip install fastapi uvicorn twilio python-dotenv

2. Configure .env file with your credentials

3. Run the server:
   uvicorn main:app --reload --port 8000

4. Start ngrok tunnel:
   ngrok http 8000

5. Add ngrok URL to Vapi tool webhook

## Developer
Built by Tauqir & Team