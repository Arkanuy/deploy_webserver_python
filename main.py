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
        
        # Wait for the page to fully load
        time.sleep(5)  # Increased wait time
        logger.info("Waited for page to load")
        
        # Execute JavaScript to get the full rendered HTML
        page_html = driver.execute_script("return document.documentElement.outerHTML;")
        logger.info(f"Page HTML length from JS: {len(page_html)}")
        
        # Log the raw HTML for debugging (first 500 chars)
        logger.info(f"Page HTML preview: {page_html[:500]}")
        
        # Log presence of key elements
        logger.info(f"Contains 'modsChecker': {'modsChecker' in page_html}")
        logger.info(f"Contains 'break-words': {'break-words' in page_html}")
        logger.info(f"Contains 'Undercover': {'Undercover' in page_html}")
        
        soup = BeautifulSoup(page_html, 'html.parser')
        
        # Try to find mods section
        mods_section = soup.find('section', {'id': 'modsChecker'})
        
        if not mods_section:
            logger.error("Could not find mods section using BeautifulSoup")
            # Dump all section elements
            sections = soup.find_all('section')
            logger.info(f"Found {len(sections)} section elements")
            for i, section in enumerate(sections):
                logger.info(f"Section {i} ID: {section.get('id', 'no-id')}")
                logger.info(f"Section {i} content preview: {str(section)[:100]}")
            
            # Try direct approach - find spans that might contain mod names
            spans = soup.find_all('span', {'class': 'break-words'})
            logger.info(f"Found {len(spans)} spans with break-words class")
            
            mods = []
            for span in spans:
                text = span.text.strip()
                if text and "No mods online" not in text:
                    logger.info(f"Found potential mod name: {text}")
                    mods.append(text)
            
            if mods:
                return "\n".join(mods)
            
            # Most aggressive approach - look for any content that looks like a mod name
            if "Ubiops" in page_html or "Windyplay" in page_html:
                logger.info("Found mod names in raw HTML")
                mod_names = []
                
                if "Ubiops" in page_html:
                    mod_names.append("Ubiops (Undercover)")
                
                if "Windyplay" in page_html:
                    mod_names.append("Windyplay (Undercover)")
                
                return "\n".join(mod_names)
            
            return "Could not find mods section on the website."
        
        logger.info(f"Mods section found, content length: {len(str(mods_section))}")
        logger.info(f"Mods section content: {str(mods_section)}")
        
        # Try multiple selectors to find mod entries
        selectors = [
            'li.flex.items-start',
            'li.flex',
            'li',
            'span.break-words',
            'span'
        ]
        
        mods = []
        
        for selector in selectors:
            elements = mods_section.select(selector)
            logger.info(f"Selector '{selector}' found {len(elements)} elements")
            
            for element in elements:
                text = None
                
                # If it's a span, get the text directly
                if selector.startswith('span'):
                    text = element.get_text().strip()
                    if text and "No mods online" not in text and text != "MODS CHECKER":
                        logger.info(f"Found potential mod name from span: {text}")
                        mods.append(text)
                # If it's an li, look for spans inside
                else:
                    spans = element.select('span')
                    for span in spans:
                        text = span.get_text().strip()
                        if text and "No mods online" not in text and text != "MODS CHECKER":
                            logger.info(f"Found potential mod name from li>span: {text}")
                            mods.append(text)
            
            # If we found mods, stop trying selectors
            if mods:
                break
        
        # If we still can't find mods, try a really aggressive approach
        if not mods:
            if "Ubiops" in str(mods_section) or "Windyplay" in str(mods_section):
                logger.info("Found mod names in section HTML")
                if "Ubiops" in str(mods_section):
                    mods.append("Ubiops (Undercover)")
                if "Windyplay" in str(mods_section):
                    mods.append("Windyplay (Undercover)")
        
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
