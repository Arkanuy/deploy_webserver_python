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
from selenium.common.exceptions import WebDriverException, TimeoutException
import re

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
                
                // Additional evasion
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'id']
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """
        })
        
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {str(e)}")
        raise

def extract_mod_name(text):
    """Extract just the mod name from text that might include status like '(Undercover)'"""
    # Extract just the name part and convert to lowercase
    if not text:
        return None
    
    # If text contains a parenthesis, extract the part before it
    match = re.match(r'^([^(]+)', text)
    if match:
        name = match.group(1).strip().lower()
        logger.info(f"Extracted name '{name}' from '{text}'")
        return name
    
    # Otherwise just return the entire text in lowercase
    return text.strip().lower()

def scrape_mods():
    driver = None
    try:
        driver = setup_selenium()
        logger.info("WebDriver initialized successfully")
        
        driver.get("https://gtid.site/")
        logger.info("Navigated to website")
        
        # Check for Cloudflare or other protection
        time.sleep(5)
        if "checking your browser" in driver.page_source.lower() or "cloudflare" in driver.page_source.lower():
            logger.info("Detected protection page, waiting longer")
            time.sleep(15)
        
        # Wait for the page to fully load - increased wait time
        logger.info("Waiting for page to fully load")
        time.sleep(15)
        
        # First, try waiting for the specific element
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "modsChecker"))
            )
            logger.info("modsChecker element found via WebDriverWait")
        except TimeoutException:
            logger.warning("Timeout waiting for modsChecker element")
        
        # Try to directly execute JavaScript to find the element
        mods_html = driver.execute_script("""
            return document.getElementById('modsChecker') ? 
                   document.getElementById('modsChecker').innerHTML : 
                   'Element not found';
        """)
        logger.info(f"modsChecker content from JS: {mods_html[:200]}")
        
        # Check for iframes
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            logger.info(f"Found {len(iframes)} iframes")
            for i, iframe in enumerate(iframes):
                try:
                    logger.info(f"Switching to iframe {i}")
                    driver.switch_to.frame(iframe)
                    if "modsChecker" in driver.page_source:
                        logger.info("Found modsChecker in iframe")
                        break
                    driver.switch_to.default_content()
                except Exception as e:
                    logger.error(f"Error switching to iframe {i}: {e}")
                    driver.switch_to.default_content()
        
        # Try direct XPath approach
        try:
            mod_spans = driver.find_elements(By.XPATH, "//section[@id='modsChecker']//span[@class='break-words']")
            if mod_spans:
                mods = [extract_mod_name(span.text) for span in mod_spans if span.text.strip()]
                mods = [mod for mod in mods if mod]  # Filter out None values
                logger.info(f"Found {len(mods)} mods via XPath")
                if mods:
                    return "\n".join(mods)
        except Exception as e:
            logger.info(f"XPath attempt failed: {e}")
        
        # Try a more lenient XPath if the specific one fails
        try:
            mod_spans = driver.find_elements(By.XPATH, "//span[contains(@class, 'break-words')]")
            if mod_spans:
                mods = [extract_mod_name(span.text) for span in mod_spans if span.text.strip() and "No mods online" not in span.text]
                mods = [mod for mod in mods if mod]  # Filter out None values
                logger.info(f"Found {len(mods)} mods via lenient XPath")
                if mods:
                    return "\n".join(mods)
        except Exception as e:
            logger.info(f"Lenient XPath attempt failed: {e}")
        
        # Execute JavaScript to get the full rendered HTML
        page_html = driver.execute_script("return document.documentElement.outerHTML;")
        logger.info(f"Page HTML length from JS: {len(page_html)}")
        
        # Log presence of key elements
        logger.info(f"Contains 'modsChecker': {'modsChecker' in page_html}")
        logger.info(f"Contains 'break-words': {'break-words' in page_html}")
        logger.info(f"Contains 'Undercover': {'Undercover' in page_html}")
        logger.info(f"Contains 'Ubiops': {'Ubiops' in page_html}")
        logger.info(f"Contains 'Windyplay': {'Windyplay' in page_html}")
        
        soup = BeautifulSoup(page_html, 'html.parser')
        
        # Try to find mods section
        mods_section = soup.find('section', {'id': 'modsChecker'})
        
        if not mods_section:
            logger.warning("Could not find mods section using BeautifulSoup")
            
            # Pattern-based extraction - if we see the mod names in the HTML
            mod_names = []
            
            # Look for specific patterns in the HTML that might indicate mod names
            patterns = {
                "Ubiops (Undercover)": "ubiops",
                "Windyplay (Undercover)": "windyplay",
                # Add any other known mod names here
            }
            
            for pattern, mod_name in patterns.items():
                if pattern in page_html:
                    logger.info(f"Found mod name via pattern matching: {pattern} -> {mod_name}")
                    mod_names.append(mod_name)
            
            if mod_names:
                return "\n".join(mod_names)
            
            # Look for mentions of names without the "(Undercover)" part
            for name in ["Ubiops", "Windyplay"]:
                if name in page_html:
                    logger.info(f"Found {name} in raw HTML")
                    mod_names.append(name.lower())
            
            if mod_names:
                return "\n".join(mod_names)
            
            # Try to find any span with class containing 'break'
            spans = soup.find_all('span', class_=lambda c: c and 'break' in c)
            logger.info(f"Found {len(spans)} spans with 'break' in class name")
            
            mods = []
            for span in spans:
                text = span.text.strip()
                if text and "No mods online" not in text:
                    mod_name = extract_mod_name(text)
                    if mod_name:
                        logger.info(f"Found potential mod name from span with 'break' class: {text} -> {mod_name}")
                        mods.append(mod_name)
            
            if mods:
                return "\n".join(mods)
            
            return "No mods online (section not found)."
        
        logger.info(f"Mods section found, content length: {len(str(mods_section))}")
        
        # Try multiple selectors to find mod entries
        selectors = [
            'span.break-words',
            'li span.break-words',
            'span[class*="break"]',
            'li span',
            'li'
        ]
        
        mods = []
        
        for selector in selectors:
            try:
                elements = mods_section.select(selector)
                logger.info(f"Selector '{selector}' found {len(elements)} elements")
                
                for element in elements:
                    text = element.get_text().strip()
                    if text and "No mods online" not in text and text != "MODS CHECKER":
                        mod_name = extract_mod_name(text)
                        if mod_name and mod_name not in mods:  # Avoid duplicates
                            logger.info(f"Found potential mod name from selector '{selector}': {text} -> {mod_name}")
                            mods.append(mod_name)
            except Exception as e:
                logger.error(f"Error with selector '{selector}': {e}")
        
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
            current_time = time.time()
            if current_time - last_updated >= 60:  # Check every minute
                logger.info(f"Updating data... Last update was {int(current_time - last_updated)} seconds ago")
                new_data = scrape_mods()
                if new_data != latest_data:
                    logger.info(f"Data changed from '{latest_data}' to '{new_data}'")
                latest_data = new_data
                last_updated = current_time
                logger.info("Data updated successfully")
            else:
                logger.debug(f"Skipping update, last update was {int(current_time - last_updated)} seconds ago")
        except Exception as e:
            logger.error(f"Error in update_data thread: {str(e)}")
        time.sleep(5)  # Check more frequently but only update when needed

@app.route("/")
def index():
    return Response(latest_data, mimetype="text/plain")

@app.route("/health")
def health():
    return Response("OK", mimetype="text/plain")

@app.route("/force-update")
def force_update():
    global latest_data, last_updated
    try:
        logger.info("Force updating data...")
        new_data = scrape_mods()
        latest_data = new_data
        last_updated = time.time()
        return Response(f"Data updated: {latest_data}", mimetype="text/plain")
    except Exception as e:
        error_msg = f"Error during forced update: {str(e)}"
        logger.error(error_msg)
        return Response(error_msg, mimetype="text/plain")

if __name__ == "__main__":
    logger.info("Starting application")
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("DEBUG") != "True":
        threading.Thread(target=update_data, daemon=True).start()
        logger.info("Update thread started")
    app.run(host="0.0.0.0", port=PORT)
