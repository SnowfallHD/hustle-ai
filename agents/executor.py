import json
import os
from datetime import datetime
from hashlib import sha256
from slugify import slugify

# ---- SET YOUR MODE HERE ----
MODE = "draft"  # Options: "draft", "doc", etc.

# ---- Setup ----
OUTPUTS_PATH = os.path.join("memory", "outputs.json")
PROCESSED_HASHES_PATH = os.path.join("memory", "outputs_processed.jsonl")

def get_processed_hashes():
    hashes = set()
    if not os.path.exists(PROCESSED_HASHES_PATH):
        return hashes
    with open(PROCESSED_HASHES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                h = sha256((data.get("name", "") + data.get("hook", "")).encode()).hexdigest()
                hashes.add(h)
            except:
                continue
    return hashes

def save_assets_to_files(output):
    name = output.get("name", "unknown")
    slug = slugify(name)[:50]  # Trim to avoid filesystem issues
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join("generated", f"{slug}_{timestamp}")
    os.makedirs(folder, exist_ok=True)

    # Save landing page
    with open(os.path.join(folder, "landing_page.txt"), "w", encoding="utf-8") as f:
        f.write(output['assets']['landing_page']['headline'] + "\n\n")
        for benefit in output['assets']['landing_page']['benefits']:
            f.write("- " + benefit + "\n")
        f.write("\n\nCTA: " + output['assets']['landing_page']['CTA'])
    print("[+] Wrote landing_page.txt")

    # Save ad hooks
    with open(os.path.join(folder, "ad_hooks.txt"), "w", encoding="utf-8") as f:
        for ad in output['assets']['ad_hooks']:
            if isinstance(ad, dict) and 'script' in ad:
                f.write(ad['script'] + "\n\n")
            elif isinstance(ad, str):
                f.write(ad + "\n\n")
    print("[+] Wrote ad_hooks.txt")

    # Save sales email
    with open(os.path.join(folder, "sales_email.txt"), "w", encoding="utf-8") as f:
        f.write(output['assets']['sales_email'])
    print("[+] Wrote sales_email.txt")

    print(f"[SUCCESS] All assets saved to: {folder}/")

def run_executor():
    print(f"[INFO] Executor mode: {MODE}")
    if not os.path.exists(OUTPUTS_PATH):
        print("[ERROR] outputs.json not found.")
        return

    processed_hashes = get_processed_hashes()

    with open(OUTPUTS_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        print(f"[DEBUG] Loaded {len(lines)} output(s)")

        for i, line in enumerate(lines):
            try:
                data = json.loads(line)
                h = sha256((data.get("name", "") + data.get("hook", "")).encode()).hexdigest()
                if h in processed_hashes:
                    print(f"[INFO] Skipping already processed: {data.get('name')}")
                    continue

                print(f"[INFO] Processing: {data.get('name')}")
                save_assets_to_files(data)

                with open(PROCESSED_HASHES_PATH, "a", encoding="utf-8") as pf:
                    json.dump(data, pf)
                    pf.write("\n")

            except json.JSONDecodeError as e:
                print(f"[WARN] Skipping bad JSON entry at line {i+1}: {e}")
            except Exception as e:
                print(f"[ERROR] Failed to process entry at line {i+1}: {e}")

if __name__ == "__main__":
    run_executor()
