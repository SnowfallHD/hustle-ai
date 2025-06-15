import json
import time
import os
import re
import unicodedata
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from dom_utils import safe_click, safe_find, safe_text
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI

# Load environment variables
load_dotenv()
IS_DEV = os.getenv("DEV_MODE") == "1"
print(f"[DEBUG] IS_DEV = {IS_DEV} (DEV_MODE={os.getenv('DEV_MODE')})")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Firefox profile
PROFILE_PATH = r"C:\\Users\\Coop\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles\\rjpq4cir.selenium-test"

def start_driver():
    options = Options()
    options.headless = False
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0")
    driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def clean_title(raw_title):
    prompt = f"""
    You are a product formatter. Clean up the following product name by removing marketing phrases, symbols like ™ or ®, and anything unnecessary. Return only the cleaned product title, nothing else.

    Product name: "{raw_title}"
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": "You are a product formatting expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] Failed to clean title with GPT: {e}")
        return raw_title
    
def clean_description(raw: str) -> str:
    if not raw:
        return ""

    # Normalize weird Unicode (e.g., smart quotes, non-breaking spaces)
    text = unicodedata.normalize("NFKD", raw)

    # Remove links (http/https and bare URLs)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)

    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)

    # Collapse excess whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove lingering unicode codes like \u00a0 if they slipped through
    text = text.encode('ascii', 'ignore').decode()

    # Trim
    return text.strip()

def handle_cookie_consent(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "CybotCookiebotDialogBodyButtons"))
        )
        allow_all_btn = driver.find_element(By.ID, "CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
        safe_click(driver, allow_all_btn)
        print("[INFO] Clicked 'Allow All' on Cookiebot.")
        time.sleep(1)
    except TimeoutException:
        print("[INFO] No Cookiebot popup detected.")
    except Exception as e:
        print(f"[WARN] Failed to handle Cookiebot: {e}")

def auto_login(driver):
    print("[DEBUG] Entered auto_login")
    email = os.getenv("DIGISTORE_EMAIL")
    password = os.getenv("DIGISTORE_PASSWORD")
    if not email or not password:
        raise ValueError("DIGISTORE_EMAIL and DIGISTORE_PASSWORD must be set in .env")

    driver.get("https://www.digistore24.com/login")
    time.sleep(2)
    handle_cookie_consent(driver)
    time.sleep(1)

    try:
        print("[DEBUG] Current URL:", driver.current_url)

        # Optional iframe switch
        try:
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe"))
            )
            print("[INFO] Switched to iframe.")
        except TimeoutException:
            print("[INFO] No iframe found. Continuing...")

        # Wait for inputs to be visible
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.NAME, "login_username"))
        )
        email_input = driver.find_element(By.NAME, "login_username")
        password_input = driver.find_element(By.NAME, "login_password")
        login_button = driver.find_element(By.NAME, "login_login")
        email_input.clear()
        email_input.send_keys(email)
        password_input.clear()
        password_input.send_keys(password)

        safe_click(driver, login_button)
        print("[INFO] Login form submitted.")
        time.sleep(5)

        # Check if login failed
        if "login" in driver.current_url.lower():
            raise RuntimeError("Login failed. Check your credentials.")

        print("[INFO] Login successful.")
    except Exception as e:
        # Dump HTML to debug file
        with open("debug_final_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        raise RuntimeError(f"Login flow failed: {e}")

def scrape_digistore_offers():
    print("[DEBUG] Starting scrape_digistore_offers()")
    print(f"[DEBUG] IS_DEV = {IS_DEV} (type: {type(IS_DEV)})")
    
    driver = start_driver()
    print("[DEBUG] Driver started")

    try:
        auto_login(driver)
        print("[DEBUG] Auto-login complete")

        driver.get("https://www.digistore24-app.com/app/en/vendor/account/marketplace/all")
        print("[DEBUG] Navigated to Digistore24 marketplace")

        time.sleep(3)

        try:
            WebDriverWait(driver, 35).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "product-list-item-container"))
            )
            print("[DEBUG] Offer cards loaded")
        except Exception as e:
            driver.save_screenshot("debug_login_failed.png")
            print(f"[ERROR] Failed to load offers: {e}")
            raise RuntimeError("Failed to load offers — likely not logged in.") from e

        offer_cards = driver.find_elements(By.CLASS_NAME, "product-list-item-container")
        print(f"[DEBUG] Found {len(offer_cards)} Digistore24 offers")

        offers = []
        parsed = 0
        for idx, card in enumerate(offer_cards):
            print(f"[DEBUG] Parsing offer card {idx + 1}")
            expand_btn = safe_find(card, By.CSS_SELECTOR, ".arrow-down-icon.cursor-pointer", timeout=2)
            if not expand_btn:
                print(f"[DEBUG] Skipping card {idx + 1} — no expand button")
                continue

            try:
                safe_click(driver, expand_btn)
                time.sleep(0.5)

                raw_name = safe_text(card, By.TAG_NAME, "h2")
                print(f"[DEBUG] Raw name: {raw_name}")
                name = clean_title(raw_name)
                print(f"[DEBUG] Cleaned name: {name}")

                earnings_text = safe_text(card, By.XPATH, ".//div[contains(text(), 'Earnings/cart visitor')]/following-sibling::div[1]")
                price = safe_text(card, By.XPATH, ".//div[contains(text(), 'Price')]/following-sibling::div[1]")
                commission = safe_text(card, By.XPATH, ".//div[contains(text(), 'Commission')]/following-sibling::div[1]")
                cart_conversion = safe_text(card, By.XPATH, ".//div[contains(text(), 'Cart conversion')]/following-sibling::div[1]")
                cancel_rate = safe_text(card, By.XPATH, ".//div[contains(text(), 'Cancellation rate')]/following-sibling::div[1]")
                vendor = safe_text(card, By.XPATH, ".//div[contains(text(), 'Vendor')]/following-sibling::div[1]")
                # Pull full description block
                try:
                    raw_description = safe_text(card, By.XPATH, ".//div[contains(@class, 'description')]")
                    description = clean_description(raw_description)
                except Exception:
                    description = "No description available"

                url = ""
                for link in card.find_elements(By.TAG_NAME, "a"):
                    if "Sales page" in link.text:
                        url = link.get_attribute("href")
                        break

                offers.append({
                    "name": name,
                    "raw_name": raw_name,
                    "price": price,
                    "commission": commission,
                    "earnings_per_cart_visitor": earnings_text,
                    "cart_conversion": cart_conversion,
                    "cancellation_rate": cancel_rate,
                    "vendor": vendor,
                    "url": url,
                    "description": description
                })

                parsed += 1
                print(f"[DEBUG] Parsed card {idx + 1}")
                if parsed >= 10:
                    print("[DEBUG] Reached max parse limit (10)")
                    break

            except Exception as e:
                print(f"[WARN] Failed to parse expanded card {idx + 1}: {e}")

    finally:
        print("[DEBUG] Entering finally block...")
        if not IS_DEV:
            print("[DEBUG] Quitting driver...")
            try:
                driver.quit()
                print("[DEBUG] Driver quit successfully")
            except Exception as quit_err:
                print(f"[ERROR] Failed to quit driver: {quit_err}")
        else:
            print("[DEBUG] Skipping driver.quit() because IS_DEV is True")

    print("[DEBUG] Returning offers")
    return offers

def enrich_with_ai(offers):
    enriched = []
    for offer in offers:
        prompt = f"""You are an AI monetization expert. Analyze the following affiliate offer:

        Name: {offer['name']}
        Description: {offer['description']}

        Return a JSON object that includes:
        - Main hook or angle to sell this offer
        - Ideal traffic source (TikTok, Google, Instagram, etc.)
        - Type of content that would convert best
        - Monetization difficulty (Low/Med/High)
        - Expected ROI (Low/Med/High)"""

        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business and product analysis expert. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7
        )

        enriched_offer = response.choices[0].message.content.strip()

        if not enriched_offer:
            print("[WARN] Empty OpenAI response. Skipping.")
            continue

        try:
            enriched.append(json.loads(enriched_offer))
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse AI response:\n{enriched_offer}\n{e}")

    return enriched


def run_research():
    print("[DEBUG] Entering run_research()")
    offers = scrape_digistore_offers()
    print("[DEBUG] scrape_digistore_offers() finished")

    if IS_DEV:
        print("[DEBUG] IS_DEV is True — skipping enrichment")
        return offers

    print("[DEBUG] Enriching offers with OpenAI")
    enriched = enrich_with_ai(offers)
    os.makedirs("memory", exist_ok=True)
    with open("memory/ideas.json", "a") as f:
        for idea in enriched:
            json.dump(idea, f)
            f.write("\n")
    return enriched


if __name__ == "__main__":
    ideas = run_research()
    print(json.dumps(ideas, indent=2))