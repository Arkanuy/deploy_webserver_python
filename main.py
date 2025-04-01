from flask import Flask, Response
import requests
from bs4 import BeautifulSoup
import threading
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

PORT = int(os.environ.get("PORT", 8000))

app = Flask(__name__)
latest_data = "No mods online."
last_updated = 0

def setup_selenium():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # No need to specify binary location - it will use the default Chrome installation
    # No need to specify executable_path - let Selenium handle it
    
    # Use the newer Service approach instead of executable_path
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def scrape_mods():
    driver = None
    try:
        driver = setup_selenium()
        driver.get("https://gtid.site/")
        
        # Wait for either the mods section to load or timeout after 10 seconds
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section#modsChecker"))
            )
        except:
            # If mods section not found, check if we're still on redirect page
            if "Redirecting" in driver.title:
                return "Website is still redirecting. Try again later."
            return "Could not find mods section on the website."
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        mods_section = soup.find('section', {'id': 'modsChecker'})
        
        if not mods_section:
            return "Could not find mods section on the website."
            
        # Check for "No mods online" message
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
    
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        if driver:
            driver.quit()

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
