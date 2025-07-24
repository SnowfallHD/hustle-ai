# agents/executor.py
from researcher import run_js_scraper
from enricher import run_enrichment

def run_autonomous_loop():
    print("🚀 Starting HustleAI autonomous loop")
    
    print("🔍 Running scraper...")
    offers = run_js_scraper()
    
    print("🧠 Running enrichment...")
    run_enrichment()

    print("✅ Done. Offers processed and enriched.")

if __name__ == "__main__":
    run_autonomous_loop()
