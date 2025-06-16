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
from selenium.webdriver.common.action_chains import ActionChains
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
    
def wait_for_manual_click(driver, label=""):
    print(f"\n[DEBUG] === Waiting for MANUAL ACTION: {label} ===")
    print("[ACTION] Manually click the element now...")
    input("[INPUT] Press Enter when you’ve clicked it to capture...")

    element = driver.execute_script("return document.activeElement;")
    tag = element.tag_name
    text = element.text.strip()
    class_list = element.get_attribute("class")
    outer_html = element.get_attribute("outerHTML")

    print(f"\n[DEBUG] Captured element from manual click:")
    print(f"  ▶ Tag: {tag}")
    print(f"  ▶ Class: {class_list}")
    print(f"  ▶ Text: '{text}'")
    print(f"  ▶ Outer HTML Snippet:\n{outer_html[:300]}...\n")

    return element

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def select_entries_per_page(driver):
    try:
        print("[DEBUG] Locating 'Entries per page' label...")

        # Step 1: Wait for the label
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Entries per page')]"))
        )

        print("[DEBUG] Label found — attempting to locate dropdown button automatically...")

        # Step 2: Try automatic dropdown click
        try:
            dropdown_elem = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-test='select-trigger']"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_elem)
            time.sleep(0.2) # Wait for scroll to settle
            dropdown_elem.click()
            print("[INFO] Clicked dropdown automatically.")

        except Exception:
            print("[WARN] Automatic dropdown click failed — switching to manual mode.")
            print("[DEBUG] Waiting for manual click on the dropdown button...")

            # === Manual Click Handling ===
            dropdown_elem = wait_for_manual_click(driver, "Click the dropdown now")
            driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_elem)
            time.sleep(0.2) # Wait for scroll to settle
            if not safe_click(driver, dropdown_elem):
                raise Exception("Manual dropdown click failed.")

        # Step 3: Attempt to auto-select "100"
        try:
            hundred_option = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='100']"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", hundred_option)
            time.sleep(0.2) # Wait for scroll to settle
            hundred_option.click()
            print("[INFO] Clicked '100' automatically.")
        except Exception:
            print("[WARN] Automatic click on '100' failed — switching to manual mode.")
            hundred_elem = wait_for_manual_click(driver, "Now click the '100' option and then press ENTER here")
            driver.execute_script("arguments[0].scrollIntoView(true);", hundred_elem)
            time.sleep(0.2) # Wait for scroll to settle
            if not safe_click(driver, hundred_elem):
                raise Exception("Clicking '100' failed.")

        print("[SUCCESS] '100 entries per page' selected successfully.")
        time.sleep(3)

    except Exception as e:
        print(f"[ERROR] Failed to set 100 entries per page: {e}")

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
        time.sleep(2)

        # === Set to 100 entries per page ===
        try:
            print("[DEBUG] Attempting to set 100 entries per page...")

            # Wait for label to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Entries per page')]"))
            )
            label_elem = driver.find_element(By.XPATH, "//div[contains(text(), 'Entries per page')]")
            parent = label_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'flex')][1]")
            dropdown_btn = parent.find_element(By.XPATH, ".//button[contains(@class, 'min-h-[40px')]")

            # Force scroll into center AND make visible
            driver.execute_script("""
                arguments[0].style.display = 'block';
                arguments[0].scrollIntoView({block: 'center'});
            """, dropdown_btn)

            time.sleep(0.3)
            dropdown_btn.click()
            print("[INFO] Clicked the 'Entries per page' dropdown.")

            opt_100 = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='100']"))
            )

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opt_100)
            time.sleep(0.2)
            opt_100.click()
            print("[SUCCESS] Selected 100 entries per page")

            # Wait until more than 10 cards are visible
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CLASS_NAME, "product-list-item-container")) > 10
            )
            print("[DEBUG] 100 offers should now be visible")
        except Exception as e:
            print(f"[WARN] Could not set 100 entries per page: {e}")

        # === Gather all offer card elements across pages ===
        all_offer_cards = []

        while True:
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "product-list-item-container"))
            )
            cards = driver.find_elements(By.CLASS_NAME, "product-list-item-container")
            print(f"[DEBUG] Found {len(cards)} offers on this page")
            all_offer_cards.extend(cards)

            # === End of pagination guard ===
            if len(cards) < 100:
                print("[INFO] Detected last page based on offer count. Exiting pagination loop.")
                break

            # Try to click next page automatically
            try:
                print("[DEBUG] Attempting to click 'Next' pagination arrow automatically...")

                all_page_links = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.page-link[href*='?page=']"))
                )
                
                if not all_page_links:
                    raise Exception("No page-link elements found.")

                next_btn = all_page_links[-1]  # usually the last one is 'Next'
                
                if "disabled" in next_btn.get_attribute("class") or not next_btn.get_attribute("href"):
                    print("[INFO] Next button is disabled — reached last page.")
                    break

                driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                safe_click(driver, next_btn)
                print("[INFO] Clicked 'Next' pagination button.")

                # Wait for the page to update
                WebDriverWait(driver, 10).until(
                    EC.staleness_of(cards[0])
                )

                # Wait for new cards to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "product-list-item-container"))
                )
            except Exception as e:
                print(f"[WARN] Could not click next page automatically: {e}")
                print("[DEBUG] Waiting for manual click on pagination arrow...")

                # === Manual Click Handling ===
                try:
                    next_btn = wait_for_manual_click(driver, "Click the NEXT arrow now and then press ENTER")
                    driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                    time.sleep(0.2) # Wait for scroll to settle
                    safe_click(driver, next_btn)
                    time.sleep(1) # Wait for the page to update
                except Exception as ex:
                    print(f"[DEBUG] No more pages or manual next click skipped: {ex}")
                    break

        print(f"[DEBUG] Total offers collected: {len(all_offer_cards)}")

        # === Parse all offers ===
        offers = []
        for idx, card in enumerate(all_offer_cards):
            print(f"[DEBUG] Parsing offer card {idx + 1}")

            try:
                # Optional: expand only if needed — test if expand actually reveals hidden info
                expand_btn = safe_find(card, By.CSS_SELECTOR, ".arrow-down-icon.cursor-pointer", timeout=1)
                if expand_btn:
                    try:
                        safe_click(driver, expand_btn)
                        time.sleep(0.2)  # minimal delay if needed
                    except:
                        print(f"[WARN] Could not click expand for card {idx + 1}")

                raw_name = safe_text(card, By.TAG_NAME, "h2")
                name = clean_title(raw_name)

                # === Batch info field extraction ===
                info_map = {}
                info_rows = card.find_elements(By.CLASS_NAME, "info-box")
                for row in info_rows:
                    try:
                        key_el = row.find_element(By.CLASS_NAME, "font-medium")
                        val_el = row.find_elements(By.TAG_NAME, "div")[-1]
                        key = key_el.text.strip()
                        val = val_el.text.strip()
                        info_map[key] = val
                    except Exception:
                        continue

                price = info_map.get("Price", "")
                commission = info_map.get("Commission", "")
                earnings_text = info_map.get("Earnings/cart visitor", "")
                cart_conversion = info_map.get("Cart conversion", "")
                cancel_rate = info_map.get("Cancellation rate", "")
                vendor = info_map.get("Vendor", "")

                # === Optional description extraction ===
                try:
                    raw_description = safe_text(card, By.XPATH, ".//div[contains(@class, 'description')]")
                    description = clean_description(raw_description)
                except Exception:
                    description = "No description available"

                # === Extract sales page URL ===
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

                print(f"[DEBUG] Parsed card {idx + 1}")

            except Exception as e:
                print(f"[WARN] Failed to parse card {idx + 1}: {e}")

        return offers
        
    finally:
        print("[DEBUG] Entering finally block...")
        if not IS_DEV:
            try:
                driver.quit()
                print("[DEBUG] Driver quit successfully")
            except Exception as quit_err:
                print(f"[ERROR] Failed to quit driver: {quit_err}")
        else:
            print("[DEBUG] Skipping driver.quit() because IS_DEV is True")

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