import json
import time
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI

# Load environment variables
load_dotenv()
IS_DEV = os.getenv("DEV_MODE") == "1"
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


def handle_cookie_consent(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "CybotCookiebotDialogBodyButtons"))
        )
        allow_all_btn = driver.find_element(By.ID, "CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
        allow_all_btn.click()
        print("[INFO] Clicked 'Allow All' on Cookiebot.")
        time.sleep(1)
    except TimeoutException:
        print("[INFO] No Cookiebot popup detected.")
    except Exception as e:
        print(f"[WARN] Failed to handle Cookiebot: {e}")

def auto_login(driver):
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

        login_button.click()
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
    driver = start_driver()

    auto_login(driver)

    driver.get("https://www.digistore24-app.com/app/en/vendor/account/marketplace/all")
    time.sleep(3)

    try:
        WebDriverWait(driver, 35).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "product-list-item-container"))
        )
    except Exception as e:
        driver.save_screenshot("debug_login_failed.png")
        raise RuntimeError("Failed to load offers — likely not logged in.") from e

    offer_cards = driver.find_elements(By.CLASS_NAME, "product-list-item-container")
    print(f"[DEBUG] Found {len(offer_cards)} Digistore24 offers")

    offers = []
    for card in offer_cards[:5]:  # Limit for speed
        try:
            # Expand the card to reveal details
            try:
                expand_btn = card.find_element(By.CLASS_NAME, "ng-trigger-expandableBullet")
                driver.execute_script("arguments[0].click();", expand_btn)
                time.sleep(0.5)
            except:
                pass  # already expanded or button not found

            name = card.find_element(By.TAG_NAME, "h2").text.strip()

            earnings_text = card.find_element(By.XPATH, ".//div[contains(text(), 'Net earnings/sale')]/preceding-sibling::div").text.strip()
            price = card.find_element(By.XPATH, ".//div[contains(text(), 'Price')]/following-sibling::div").text.strip()
            commission = card.find_element(By.XPATH, ".//div[contains(text(), 'Commission')]/following-sibling::div").text.strip()
            cart_conversion = card.find_element(By.XPATH, ".//div[contains(text(), 'Cart conversion')]/following-sibling::div").text.strip()
            cancel_rate = card.find_element(By.XPATH, ".//div[contains(text(), 'Cancellation rate')]/following-sibling::div").text.strip()
            vendor = card.find_element(By.XPATH, ".//div[contains(text(), 'Vendor')]/following-sibling::div").text.strip()

            # Get Sales Page URL
            url = ""
            for link in card.find_elements(By.TAG_NAME, "a"):
                if "Sales page" in link.text:
                    url = link.get_attribute("href")
                    break

            offers.append({
                "name": name,
                "price": price,
                "commission": commission,
                "earnings_per_sale": earnings_text,
                "cart_conversion": cart_conversion,
                "cancellation_rate": cancel_rate,
                "vendor": vendor,
                "url": url
            })

        except Exception as e:
            print(f"[WARN] Skipped a card due to parsing error: {e}")

    if not IS_DEV:
        driver.quit()

    print("[INFO] Scraped offers:")
    print(json.dumps(offers, indent=2))
    return offers

def enrich_with_ai(offers):
    print("[INFO] Scraped offers:")
    print(json.dumps(offers, indent=2))
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
    offers = scrape_digistore_offers()

    if IS_DEV:
        print("[INFO] Running in DEV mode — skipping AI enrichment.")
        print(json.dumps(offers, indent=2))
        return offers

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
