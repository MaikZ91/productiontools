import requests

ACCESS_TOKEN = "EAARGZAhh6FeUBO1BcNnupzxFKg9arIi96vbbw4oZCQfjTU7oauMqxdQaO1FzNs50nMBNSxV0rUlv4h73hOb58u4w5mCbtZAaBYJZBBHNKeYnLbSyGWXcogpoWadVj5ZBUJ5S6i4K7FJNuUIDl8dRodAtXYZCy9f1b2uB55UOrC8fUN4lCeA1YN91XEJJ0HY4PtMbzZCGOE2"
IG_USER_ID = "17841439206364243"
IMAGE_URL = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png"
CAPTION = "🔥 TRIBE WORKOUT – jeden Donnerstag! 💪 Kostenlos & offen für alle. #tribe #bielefeld #workout"

# 1. Instagram Medienobjekt erstellen
media_payload = {
    "image_url": IMAGE_URL,
    "caption": CAPTION,
    "access_token": ACCESS_TOKEN
}
media_response = requests.post(f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media", data=media_payload)
media_json = media_response.json()
creation_id = media_json.get("id")

# 2. Medienobjekt veröffentlichen
if creation_id:
    publish_payload = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    }
    publish_response = requests.post(f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish", data=publish_payload)
    print("✅ Erfolgreich gepostet:", publish_response.json())
else:
    print("❌ Fehler beim Erstellen:", media_response.text)
