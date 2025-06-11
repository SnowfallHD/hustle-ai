import json
import time
import os
import random
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI

load_dotenv()
IS_DEV = os.getenv("DEV_MODE") == "1"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def scrape_digistore_offers():
    profile_path = r"C:\Users\Coop\AppData\Roaming\Mozilla\Firefox\Profiles\rjpq4cir.selenium-test"  # <-- FIREFOX PROFILE PATH - (Change if profile ID changes)
    profile = webdriver.FirefoxProfile(profile_path)
    
    # options.add_argument('--headless')  # headless won't work with user profile
    options = Options()
    options.add_argument('--no-sandbox')
    options.headless = False # keep visible
    options.profile = profile # Attach profile to options
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0")


    driver = Firefox(service=Service(GeckoDriverManager().install()), options=options)


    driver.get("https://www.digistore24-app.com/app/en/vendor/account/marketplace/all")
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    time.sleep(random.uniform(2, 4))

    # Wait for the offer cards to load
    WebDriverWait(driver, 35).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "product-box"))
    )

    # Get the offer cards
    offer_cards = driver.find_elements(By.CLASS_NAME, "product-box")
    print(f"[DEBUG] Found {len(offer_cards)} Digistore24 offers")

    # Prepare container for scraped results
    offers = []

    # Loop through first 5 cards (or fewer if less available)
    for card in offer_cards[:5]:
        try:
            name = card.find_element(By.CLASS_NAME, "product-title").text
            earnings = card.find_element(By.CLASS_NAME, "earnings-per-sale").text
            url = card.find_element(By.TAG_NAME, "a").get_attribute("href")

            offers.append({
                "name": name,
                "description": f"Earnings per sale: {earnings}",
                "url": url
            })
        except Exception as e:
            print(f"[WARN] Skipped a card: {e}")

    print(driver.capabilities["browserName"])  # Should print: "firefox"
    # driver.quit()
    print(f"[DEBUG] Found {len(offers)} Digistore24 offers")

    if not IS_DEV:
        driver.quit()
        
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
            model="gpt-4",
            messages=[{"role": "system", "content": prompt}]
        )

        enriched_offer = response.choices[0].message.content
        enriched.append(json.loads(enriched_offer))

    return enriched

def run_research():
    offers = scrape_digistore_offers()
    
    if IS_DEV:
        print("[INFO] Running in DEV mode, skipping enrichment.")
        print(json.dumps(offers, indent=2))
        return offers

    enriched = enrich_with_ai(offers)
    with open("memory/ideas.json", "a") as f:
        for idea in enriched:
            json.dump(idea, f)
            f.write("\n")
    return enriched


if __name__ == "__main__":
    ideas = run_research()
    print(json.dumps(ideas, indent=2))
