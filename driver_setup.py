from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os
import time

def get_driver():
    """
    Optimized Chrome setup for Render's low-memory environment.
    """
    options = Options()
    
    # Path for Google Chrome in the Docker container
    docker_path = "/usr/bin/google-chrome-stable"
    options.binary_location = os.getenv("CHROME_BIN", docker_path)

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--single-process")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Additional memory optimizations
    options.add_argument("--disable-extensions")
    options.add_argument("--no-zygote")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(15)
        return driver
    except Exception as e:
        print(f"Error launching Chrome: {e}")
        return None

def safe_get(driver, url, retries=2):
    """
    Safely get a URL with retries.
    """
    for attempt in range(retries + 1):
        try:
            driver.get(url)
            return True
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt == retries:
                return False
            time.sleep(2)
    return False
