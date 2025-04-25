import os
import requests
import sys

def send_group_message():
    token = os.getenv("WHATSAPP_TOKEN")
    phone_number_id = os.getenv("PHONE_NUMBER_ID")
    group_id = os.getenv("GROUP_ID")
    if not all([token, phone_number_id, group_id]):
        print("FEHLER: Umgebungsvariablen WHATSAPP_TOKEN, PHONE_NUMBER_ID und GROUP_ID müssen gesetzt sein.")
        sys.exit(1)

    url = f"https://graph.facebook.com/v15.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": group_id,
        "type": "text",
        "text": {"body": "📢 Guten Morgen! Hier dein Wochen-Update für heute."}
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        print(f"Fehler beim Senden ({resp.status_code}): {resp.text}")
        sys.exit(1)

    print("✅ Nachricht erfolgreich gesendet.")

if __name__ == "__main__":
    send_group_message()
