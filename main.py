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
    
    # Add user agent to appear more like a regular browser
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.165 Safari/537.36")
    
    # Add these arguments to make headless Chrome less detectable
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    
    # Additional preferences to avoid detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    try:
        driver = webdriver.Chrome(options=options)
        
        # Execute CDP commands to make WebDriver undetectable
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        })
        
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
        
        # Wait for either the mods section to load or timeout after 15 seconds
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section#modsChecker"))
            )
            logger.info("Found mods section")
            
            # Additional wait for content to load
            time.sleep(3)
        except Exception as wait_error:
            logger.error(f"Wait error: {str(wait_error)}")
            if "Redirecting" in driver.title:
                return "Website is still redirecting. Try again later."
            return "Could not find mods section on the website."
        
        # Log the HTML for debugging
        page_html = driver.page_source
        logger.info(f"Page HTML length: {len(page_html)}")
        
        soup = BeautifulSoup(page_html, 'html.parser')
        mods_section = soup.find('section', {'id': 'modsChecker'})
        
        if not mods_section:
            logger.error("Could not find mods section using BeautifulSoup")
            return "Could not find mods section on the website."
        
        logger.info(f"Mods section found, content length: {len(str(mods_section))}")
        
        # Use the exact selector from the HTML provided
        mod_entries = mods_section.select('li.flex.items-start')
        logger.info(f"Found {len(mod_entries)} mod entries with new selector")
        
        mods = []
        if mod_entries:
            for i, mod in enumerate(mod_entries):
                logger.info(f"Processing entry {i}: length {len(str(mod))}")
                
                # Try to find the span with class break-words
                span = mod.select_one('span.break-words')
                if span:
                    mod_name = span.text.strip()
                    logger.info(f"Found mod name: {mod_name}")
                    mods.append(mod_name)
        
        # If we still can't find mods, try a more generic approach
        if not mods:
            logger.info("Trying alternative method to find mods")
            # Look for all li elements in the mods section
            all_li = mods_section.find_all('li')
            logger.info(f"Found {len(all_li)} li elements")
            
            for li in all_li:
                spans = li.find_all('span')
                for span in spans:
                    text = span.text.strip()
                    if text and "No mods online" not in text:
                        logger.info(f"Found mod name via alternative method: {text}")
                        mods.append(text)
        
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
