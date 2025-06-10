import json
import os
from datetime import datetime

def load_output():
    with open("memory/outputs.json", "r", encoding="utf-8") as f:
        lines = f.readlines()
        print(f"[DEBUG] Found {len(lines)} line(s) in outputs.json")

        last_line = lines[-1].strip()
        try:
            data = json.loads(last_line)
            print("[DEBUG] Loaded JSON successfully.")
            return data
        except json.JSONDecodeError as e:
            print("[ERROR] JSON decode failed:", e)
            raise

def save_assets_to_files(output):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join("generated", timestamp)
    os.makedirs(folder, exist_ok=True)

    # Write landing page
    with open(os.path.join(folder, "landing_page.txt"), "w", encoding="utf-8") as f:
        f.write(output['landing_page']['headline'] + "\n\n")
        for benefit in output['landing_page']['benefits']:
            f.write("- " + benefit + "\n")
        f.write("\n\nCTA: " + output['landing_page']['CTA'])
    print("[+] Wrote landing_page.txt")

    # Write ad hooks
    with open(os.path.join(folder, "ad_hooks.txt"), "w", encoding="utf-8") as f:
        for ad in output['ad_hooks']:
            if isinstance(ad, dict) and 'script' in ad:
                f.write(ad['script'] + "\n\n")
            elif isinstance(ad, str):
                f.write(ad + "\n\n")
    print("[+] Wrote ad_hooks.txt")

    # Write sales email
    with open(os.path.join(folder, "sales_email.txt"), "w", encoding="utf-8") as f:
        f.write(output['sales_email'])
    print("[+] Wrote sales_email.txt")

    print(f"[SUCCESS] All assets saved to: {folder}/")

def run_executor():
    output = load_output()
    save_assets_to_files(output)

if __name__ == "__main__":
    run_executor()
