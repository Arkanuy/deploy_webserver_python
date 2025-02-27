from flask import Flask, Response
import requests
import re
import threading
import time
import os

# Konfigurasi dari Environment Variables
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
PORT = int(os.getenv("PORT", 5000))

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json"
}

app = Flask(__name__)
latest_data = ""

def extract_names(text):
    return [name.lower() for name in re.findall(r"@(\w+)", text)]

def get_messages(channel_id, limit=10):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit={limit}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        messages = response.json()
        all_names = []
        for msg in messages:
            if not msg.get("content") and 'embeds' in msg and msg['embeds']:
                embeds = msg['embeds'][0]
                description = embeds.get("description", "")
                names = extract_names(description)
                all_names.extend(names)
        return "\n".join(all_names) if all_names else "No mods found."
    else:
        return f"Error: {response.status_code}, {response.text}"

def update_data():
    global latest_data
    while True:
        latest_data = get_messages(CHANNEL_ID)
        time.sleep(10)

@app.route("/")
def index():
    return Response(latest_data, mimetype="text/plain")

if __name__ == "__main__":
    threading.Thread(target=update_data, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=True)
