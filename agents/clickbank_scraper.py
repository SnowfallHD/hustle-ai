import requests
import json

def scrape_clickbank_offers():
    url = "https://accounts.clickbank.com/graphql"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        # If needed: add your browser cookies below
        # "cookie": "cbid=your_cookie_here;"
    }

    payload = {
        "operationName": "MarketplaceSearch",
        "variables": {
            "parameters": {
                "keyword": "",
                "sort": "RANK",
                "limit": 10
            }
        },
        "query": """
        query MarketplaceSearch($parameters: MarketplaceSearchParameters!) {
          marketplaceSearch(parameters: $parameters) {
            results {
              listing {
                title
                description
              }
            }
          }
        }
        """
    }

    res = requests.post(url, headers=headers, data=json.dumps(payload))
    
    try:
        print("[DEBUG] Raw response text:")
        print(res.text)
        data = res.json()
        results = data['data']['marketplaceSearch']['results']
        offers = []
        for r in results:
            listing = r.get('listing', {})
            title = listing.get('title', '').strip()
            desc = listing.get('description', '').strip()
            if title and desc:
                offers.append({
                    "name": title,
                    "hook": desc,
                    "platform": "ClickBank",
                    "content": "Reels/TikToks"
                })
        return offers
    except Exception as e:
        print("[ERROR] Failed to parse response:", e)
        return []

# Save to ideas.json
if __name__ == "__main__":
    offers = scrape_clickbank_offers()
    if offers:
        with open("memory/ideas.json", "a") as f:
            for offer in offers:
                json.dump(offer, f)
                f.write("\n")
        print(f"[+] Saved {len(offers)} ClickBank offers to memory/ideas.json")
    else:
        print("[-] No offers found or request failed.")
