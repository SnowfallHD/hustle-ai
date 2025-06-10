import json
import time
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def scrape_digistore_offers():
    profile_path = r"C:\Users\Coop\AppData\Roaming\Mozilla\Firefox\Profiles\rjpq4cir.selenium-test"  # YOUR FIREFOX PROFILE PATH
    profile = webdriver.FirefoxProfile(profile_path)
    
    # options.add_argument('--headless')  # headless won't work with user profile
    options = Options()
    options.add_argument('--no-sandbox')
    options.headless = False # keep visible

    driver = Firefox(service=Service(GeckoDriverManager().install()), options=options, firefox_profile=profile)


    driver.get("https://www.digistore24-app.com/app/en/vendor/account/marketplace/all")
                
    time.sleep(12)  # Give it a moment to fully load

    offers = []

    offer_cards = driver.find_elements(By.CSS_SELECTOR, ".product-list-entry")

    for card in offer_cards[:5]:
        try:
            name = card.find_element(By.CSS_SELECTOR, ".product-title").text
            earnings = card.find_element(By.CSS_SELECTOR, ".earnings-per-sale").text
            url = card.find_element(By.CSS_SELECTOR, ".product-title a").get_attribute("href")

            offers.append({
                "name": name,
                "description": f"Earnings per sale: {earnings}",
                "url": url
            })

        except Exception as e:
            print(f"[WARN] Skipped a card: {e}")

    print(driver.capabilities["browserName"])  # Should print: "firefox"
    driver.quit()
    print(f"[DEBUG] Found {len(offers)} Digistore24 offers")
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
            model="gpt-4",
            messages=[{"role": "system", "content": prompt}]
        )

        enriched_offer = response.choices[0].message.content
        enriched.append(json.loads(enriched_offer))

    return enriched

def run_research():
    offers = scrape_digistore_offers()
    enriched = enrich_with_ai(offers)
    with open("memory/ideas.json", "a") as f:
        for idea in enriched:
            json.dump(idea, f)
            f.write("\n")
    return enriched

if __name__ == "__main__":
    ideas = run_research()
    print(json.dumps(ideas, indent=2))

