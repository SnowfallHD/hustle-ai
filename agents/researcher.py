import os
import json
import time
import re
import unicodedata
from dotenv import load_dotenv
from openai import OpenAI
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
IS_DEV = os.getenv("DEV_MODE") == "1"

def clean_description(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.encode('ascii', 'ignore').decode()
    return text.strip()

def clean_title(raw_title):
    prompt = f"""
    Clean up this product name: "{raw_title}"
    Remove hype, marketing fluff, and special characters. Output only the cleaned title.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": "You are a product naming expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except:
        return raw_title

def handle_cookie_popup(page):
    try:
        page.wait_for_selector("#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll", timeout=5000)
        page.click("#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
        print("[INFO] Cookiebot accepted.")
    except:
        print("[INFO] No Cookiebot popup.")

def login(page):
    print("[DEBUG] Navigating to login page...")
    page.goto("https://www.digistore24.com/login", timeout=60000)
    handle_cookie_popup(page)
    time.sleep(1.5)

    try:
        print("[DEBUG] Injecting credentials through shadow DOM...")

        email = json.dumps(os.getenv("DIGISTORE_EMAIL"))
        password = json.dumps(os.getenv("DIGISTORE_PASSWORD"))
        if not email or not password:
            raise ValueError("Missing DIGISTORE_EMAIL or DIGISTORE_PASSWORD in .env!")

        # JS trick to inject into shadow DOM inputs
        page.evaluate(f'''
            () => {{
                const emailInput = document.querySelector("input[type='email']");
                const passInput = document.querySelector("input[type='password']");
                if (emailInput) emailInput.value = {email};
                if (passInput) passInput.value = {password};
            }}
        ''')

        print("[DEBUG] Submitting login form...")
        # Submit login form
        # Wait for the Login button using a visual fallback
        page.wait_for_selector("button", timeout=10000)
        buttons = page.query_selector_all("button")

        for button in buttons:
            if "login" in button.inner_text().lower():
                button.click()
                break
        else:
            raise RuntimeError("Login button not found.")

        page.wait_for_load_state("networkidle", timeout=15000)

        page.wait_for_load_state("networkidle", timeout=15000)

        if "login" in page.url.lower():
            page.screenshot(path="debug_login_failed.png")
            raise RuntimeError("Login failed — still on login page.")

        print("[✅] Login successful.")

    except Exception as e:
        page.screenshot(path="debug_final_page.png")
        raise RuntimeError(f"[ERROR] Login failed: {e}")

def set_100_per_page(page):
    page.goto("https://www.digistore24-app.com/app/en/vendor/account/marketplace/all", timeout=60000)
    handle_cookie_popup(page)

    page.wait_for_selector("text=Entries per page", timeout=10000)
    page.click("button[data-test='select-trigger']")
    page.click("text=100")
    page.wait_for_timeout(2000)

def scrape_all_offers(page):
    offers = []
    seen_names = set()

    while True:
        try:
            page.wait_for_selector(".product-list-item-container", timeout=10000)
        except PlaywrightTimeout:
            print("[WARN] No product cards found — skipping page.")
            break

        cards = page.query_selector_all(".product-list-item-container")
        print(f"[+] Found {len(cards)} offers")

        for card in cards:
            try:
                name_raw = card.query_selector("h2").inner_text().strip()
                if name_raw in seen_names:
                    continue
                seen_names.add(name_raw)
                name = clean_title(name_raw)

                info = {}
                for row in card.query_selector_all(".info-box"):
                    try:
                        k = row.query_selector(".font-medium").inner_text().strip()
                        v = row.query_selector_all("div")[-1].inner_text().strip()
                        info[k] = v
                    except:
                        continue

                desc_elem = card.query_selector("div.description")
                description_text = clean_description(desc_elem.inner_text()) if desc_elem else "N/A"

                sales_link = ""
                for link in card.query_selector_all("a"):
                    if "Sales page" in link.inner_text():
                        sales_link = link.get_attribute("href")
                        break

                offers.append({
                    "name": name,
                    "raw_name": name_raw,
                    "price": info.get("Price", ""),
                    "commission": info.get("Commission", ""),
                    "earnings_per_cart_visitor": info.get("Earnings/cart visitor", ""),
                    "cart_conversion": info.get("Cart conversion", ""),
                    "cancellation_rate": info.get("Cancellation rate", ""),
                    "vendor": info.get("Vendor", ""),
                    "url": sales_link,
                    "description": description_text
                })

            except Exception as e:
                print(f"[WARN] Failed to parse card: {e}")
                continue

        # Try to paginate
        next_btn = page.query_selector("a.page-link[href*='?page=']:last-child")
        if not next_btn or not next_btn.is_visible():
            print("[INFO] No more pages.")
            break

        next_btn.scroll_into_view_if_needed()
        next_btn.click()
        page.wait_for_timeout(2500)

    return offers

def enrich_with_ai(offers):
    enriched = []
    for offer in offers:
        prompt = f"""
        Name: {offer['name']}
        Description: {offer['description']}

        Return JSON:
        - Main hook or angle to sell this offer
        - Ideal traffic source (e.g., TikTok, IG, YT)
        - Type of content that would convert best
        - Monetization difficulty (Low/Medium/High)
        - Expected ROI (Low/Medium/High)
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": "You are an AI monetization strategist. Respond in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            parsed = json.loads(response.choices[0].message.content.strip())

            enriched.append({
                "name": offer["name"],
                "hook": parsed.get("Main hook", "N/A"),
                "platform": parsed.get("Ideal traffic source", "N/A"),
                "content": parsed.get("Type of content", "N/A"),
                "difficulty": parsed.get("Monetization difficulty", "N/A"),
                "roi": parsed.get("Expected ROI", "N/A")
            })

        except Exception as e:
            print(f"[ERROR] Failed to enrich: {offer['name']} — {e}")
            continue

    return enriched

def run_research():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not IS_DEV)
        context = browser.new_context()
        page = context.new_page()

        try:
            login(page)
            set_100_per_page(page)
            offers = scrape_all_offers(page)

            if IS_DEV:
                print("[DEBUG] Returning offers only (DEV_MODE).")
                return offers

            enriched = enrich_with_ai(offers)
            os.makedirs("memory", exist_ok=True)
            with open("memory/ideas.json", "a", encoding="utf-8") as f:
                for idea in enriched:
                    json.dump(idea, f)
                    f.write("\n")

            print(f"[✅] Enriched {len(enriched)} offers saved.")
            return enriched
        finally:
            browser.close()

if __name__ == "__main__":
    run_research()
