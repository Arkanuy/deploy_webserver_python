from flask import Flask, Response
import requests
from bs4 import BeautifulSoup
import threading
import time
import os

PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)
latest_data = "No mods online."
last_updated = 0

def scrape_mods():
    try:
        session = requests.Session()
        session.max_redirects = 5  # Limit redirects
        
        # First try to follow redirects automatically
        response = session.get(
            "https://gtid.site/",
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            allow_redirects=True,
            timeout=10
        )
        
        # If we get HTML with meta refresh, try to extract the destination URL
        if 'meta http-equiv="refresh"' in response.text.lower():
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta_refresh:
                content = meta_refresh.get('content', '')
                if 'url=' in content.lower():
                    redirect_url = content.split('url=')[1]
                    response = session.get(
                        redirect_url,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        },
                        allow_redirects=True,
                        timeout=10
                    )
        
        soup = BeautifulSoup(response.text, 'html.parser')
        mods_section = soup.find('section', {'id': 'modsChecker'})
        
        if not mods_section:
            return "Could not find mods section on the website."
            
        # Check if the default "No mods online" message is present
        no_mods_message = mods_section.find('span', string=lambda text: "No mods online" in str(text))
        if no_mods_message:
            return "No mods online."
            
        # Find all mod entries
        mod_entries = mods_section.select('ul li.flex.items-start')
        
        mods = []
        for mod in mod_entries:
            mod_name = mod.find('span', class_='break-words')
            if mod_name and "No mods online" not in mod_name.text:
                mods.append(mod_name.text.strip())
        
        return "\n".join(mods) if mods else "No mods online."
    
    except requests.RequestException as e:
        return f"Error scraping website: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"

def update_data():
    global latest_data, last_updated
    while True:
        if time.time() - last_updated >= 60:
            new_data = scrape_mods()
            latest_data = new_data
            last_updated = time.time()
        time.sleep(1)

@app.route("/")
def index():
    return Response(latest_data, mimetype="text/plain")

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("DEBUG") != "True":
        threading.Thread(target=update_data, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
