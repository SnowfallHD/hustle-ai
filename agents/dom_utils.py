import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

def safe_click(driver, element, retries=3, delay=0.5):
    """
    Safely attempts to click a Selenium element using JavaScript execution.
    Retries if the click is intercepted.
    """
    for _ in range(retries):
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except ElementClickInterceptedException:
            time.sleep(delay)
    return False

def safe_find(driver_or_context, by, value, retries=3, delay=0.5, timeout=None):
    """Attempts to find a single element with optional timeout support."""
    if timeout:
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                return driver_or_context.find_element(by, value)
            except NoSuchElementException:
                time.sleep(delay)
    else:
        for _ in range(retries):
            try:
                return driver_or_context.find_element(by, value)
            except NoSuchElementException:
                time.sleep(delay)
    return None

def safe_text(context, by, value, default="N/A", retries=2, delay=0.25):
    """
    Safely extracts and strips text from an element inside a given context.
    Retries if the element isn't immediately found. Returns a fallback default if missing.
    """
    for _ in range(retries):
        try:
            element = context.find_element(by, value)
            return element.text.strip()
        except NoSuchElementException:
            time.sleep(delay)
    return default
