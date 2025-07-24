import os
import json
from dotenv import load_dotenv
from core.hustle_agent import HustleAgent

load_dotenv()
OUTPUT_DIR = "memory/built_content"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class BuilderTask:
    def __init__(self, agent: HustleAgent):
        self.agent = agent

    def load_enriched_offers(self, input_path="memory/ideas.json"):
        print("[📥] Loading enriched offers...")
        offers = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    offers.append(json.loads(line))
                except:
                    continue
        print(f"[✅] Loaded {len(offers)} offers.")
        return offers

    def generate_assets(self, offer):
        print(f"[🧠] Generating content for: {offer['name']}")
        return self.agent.create_marketing_bundle(offer)

    def save_assets(self, offer, assets):
        filename = f"{offer['name'][:50].replace(' ', '_').replace('/', '_')}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(assets, f, indent=2, ensure_ascii=False)
        print(f"[💾] Saved content to: {filepath}")

    def run(self):
        offers = self.load_enriched_offers()
        for offer in offers:
            try:
                assets = self.generate_assets(offer)
                self.save_assets(offer, assets)
            except Exception as e:
                print(f"[❌] Failed to build content for {offer.get('name')}: {e}")
                continue

if __name__ == "__main__":
    agent = HustleAgent()
    task = BuilderTask(agent)
    task.run()
