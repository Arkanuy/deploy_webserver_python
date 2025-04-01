from flask import Flask, Response
import requests
from bs4 import BeautifulSoup
import threading
import time
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    options.add_argument("--disable-extensions")
    
    try:
        # Explicitly specify the chromedriver path
        driver = webdriver.Chrome(
            options=options
        )
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {str(e)}")
        raise

def scrape_mods():
    driver = None
    try:
        driver = setup_selenium()
        logger.info("WebDriver initialized successfully")
        
        driver.get("https://gtid.site/")
        logger.info("Navigated to website")
        
        # Wait for either the mods section to load or timeout after 10 seconds
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section#modsChecker"))
            )
            logger.info("Found mods section")
        except Exception as wait_error:
            logger.error(f"Wait error: {str(wait_error)}")
            # If mods section not found, check if we're still on redirect page
            if "Redirecting" in driver.title:
                return "Website is still redirecting. Try again later."
            return "Could not find mods section on the website."
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        mods_section = soup.find('section', {'id': 'modsChecker'})
        
        if not mods_section:
            logger.error("Could not find mods section using BeautifulSoup")
            return "Could not find mods section on the website."
            
        # Improved mod detection logic
        mod_entries = mods_section.select('ul li.flex')
        
        if not mod_entries:
            logger.warning("No mod entries found in expected format")
            # Try alternative selector based on the HTML you shared
            mod_entries = mods_section.select('ul li')
        
        mods = []
        for mod in mod_entries:
            # Find the span with the mod name
            mod_name = mod.select_one('span.break-words')
            if mod_name and mod_name.text.strip() and "No mods online" not in mod_name.text:
                mods.append(mod_name.text.strip())
        
        logger.info(f"Found {len(mods)} mods online")
        return "\n".join(mods) if mods else "No mods online."
    
    except Exception as e:
        logger.error(f"Error in scrape_mods: {str(e)}")
        return f"Error: {str(e)}"
    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

def update_data():
    global latest_data, last_updated
    while True:
        try:
            if time.time() - last_updated >= 60:
                logger.info("Updating data...")
                new_data = scrape_mods()
                latest_data = new_data
                last_updated = time.time()
                logger.info("Data updated successfully")
        except Exception as e:
            logger.error(f"Error in update_data thread: {str(e)}")
        time.sleep(1)

@app.route("/")
def index():
    return Response(latest_data, mimetype="text/plain")

@app.route("/health")
def health():
    return Response("OK", mimetype="text/plain")

if __name__ == "__main__":
    logger.info("Starting application")
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("DEBUG") != "True":
        threading.Thread(target=update_data, daemon=True).start()
        logger.info("Update thread started")
    app.run(host="0.0.0.0", port=PORT)
