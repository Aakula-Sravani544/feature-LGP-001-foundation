from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os
import time

def get_driver():
    """
    Optimized Chrome setup for Selenium stability.
    """
    options = Options()
    
    # Path for Google Chrome
    docker_path = "/usr/bin/google-chrome-stable"
    options.binary_location = os.getenv("CHROME_BIN", docker_path)

    # Mandatory Options (Requirement 1)
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Stability Options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-zygote")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--renderer-process-limit=1")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        print(f"Error launching Chrome: {e}")
        return None

def safe_get(driver, url):
    """
    Safe URL loading.
    """
    if driver is None: return False
    try:
        driver.get(url)
        return True
    except:
        return False
