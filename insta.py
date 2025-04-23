import requests
from datetime import datetime

ACCESS_TOKEN = "EAARGZAhh6FeUBO1BcNnupzxFKg9arIi96vbbw4oZCQfjTU7oauMqxdQaO1FzNs50nMBNSxV0rUlv4h73hOb58u4w5mCbtZAaBYJZBBHNKeYnLbSyGWXcogpoWadVj5ZBUJ5S6i4K7FJNuUIDl8dRodAtXYZCy9f1b2uB55UOrC8fUN4lCeA1YN91XEJJ0HY4PtMbzZCGOE2"
IG_USER_ID = "17841439206364243"

image_url = "https://dein-server.de/pfad/zu/Unbenannt.png"  # Du brauchst hier eine echte URL!
caption = "🔥 TRIBE WORKOUT – jeden Donnerstag! 💪 Kostenlos & offen für alle. #tribe #bielefeld #workout"


create_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
media_payload = {
    "image_url": image_url,
    "caption": caption,
    "access_token": ACCESS_TOKEN
}
media_response = requests.post(create_url, data=media_payload)
creation_id = media_response.json().get("id")

# 2. Veröffentliche das Medienobjekt
if creation_id:
    publish_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    }
    publish_response = requests.post(publish_url, data=publish_payload)
    print(publish_response.json())
else:
    print("Fehler beim Erstellen des Medienobjekts:", media_response.text)
