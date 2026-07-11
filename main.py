import os
import requests
from flask import Flask, request, jsonify
from google import genai

from google.cloud import storage

app = Flask(__name__)

# Retrieve environment variables configured in Cloud Run
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initialize the Gemini client
# The SDK automatically detects the GEMINI_API_KEY from environment variables,
# but passing it explicitly ensures a robust setup.
client = genai.Client(api_key=GEMINI_API_KEY)


def send_whatsapp_message(to_phone_number, text_content):
    """
    Sends a message back to the sender via the WhatsApp Cloud API.
    """
    if not WHATSAPP_TOKEN:
        print("Error: WHATSAPP_TOKEN environment variable is not configured.")
        return None
        
    url = "https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_number,
        "type": "text",
        "text": {
            "body": text_content
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        # Safeguard if response variable is not defined due to request failures
        try:
            print(f"Response body: {response.text}")
        except NameError:
            pass
        return None


@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Webhook Server is running.", 200


@app.route("/whatsapp_webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    # 1. Handle WhatsApp Webhook Verification (GET Request)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook verified successfully.")
            return challenge, 200
        else:
            print("Webhook verification failed. Token mismatch.")
            return "Forbidden", 403

    # 2. Handle Incoming WhatsApp Message (POST Request)
    elif request.method == "POST":
        data = request.get_json()
        print(f"Received webhook payload: {data}")

        if not data:
            return "Invalid Payload", 400

        try:
            # Parse WhatsApp JSON payload structure
            # Entry -> Changes -> Value -> Messages
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    
                    for msg in messages:
                        sender_id = msg.get("from")  # Sender's phone number
                        msg_type = msg.get("type")
                        
                        if msg_type == "text":
                            user_text = msg.get("text", {}).get("body", "")
                            print(f"Received text: '{user_text}' from sender: {sender_id}")
                            
                            # Generate answer using Gemini 2.5 Flash
                            try:
                                gemini_response = client.models.generate_content(
                                    model="gemini-1.5-flash",
                                    contents=user_text,
                                )
                                reply_text = gemini_response.text
                            except Exception as gemini_err:
                                print(f"Error calling Gemini API: {gemini_err}")
                                reply_text = "I encountered an error processing your query. Please try again shortly."
                            
                            # Reply to user
                            send_whatsapp_message(sender_id, reply_text)
                            
        except Exception as parse_err:
            print(f"Error parsing metadata payload: {parse_err}")

        # WhatsApp requires a 200 OK response promptly to stop repeating notifications
        return jsonify({"status": "received"}), 200

    return "Method Not Allowed", 405


if __name__ == "__main__":
    # Port configuration is managed automatically by Cloud Run environment
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
