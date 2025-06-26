import json
import re
import os
from dotenv import load_dotenv
from openai import OpenAI
from hashlib import sha256

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

IS_DEV = os.getenv("DEV_MODE") == "1"  # Only processes 1 idea when True

# Keep track of already-built ideas using hash of name+hook
def already_processed_hashes():
    hashes = set()
    path = "memory/ideas_enriched.json"
    if not os.path.exists(path):
        return hashes
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                enriched = json.loads(line)
                h = sha256((enriched.get("name", "") + enriched.get("hook", "")).encode()).hexdigest()
                hashes.add(h)
            except:
                continue
    return hashes

def load_ideas():
    with open("memory/ideas.json", "r", encoding="utf-8") as f:
        lines = f.readlines()

    ideas = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ideas.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"[WARN] Skipping bad idea line:\n{line}\n{e}")

    return ideas

def extract_json_from_response(text):
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parsing failed: {e}")
            raise
    raise ValueError("No valid JSON found in GPT response.")

def build_assets(idea):
    prompt = f"""
            You are the Builder Agent for HustleAI. Here's an idea you received:

            Offer Name: {idea.get('name', 'N/A')}
            Hook: {idea.get('hook', 'N/A')}
            Platform: {idea.get('platform', 'N/A')}
            Content Type: {idea.get('content', 'N/A')}

            Create the following in raw JSON:
            1. landing_page: {{headline, benefits (list), CTA}}
            2. ad_hooks: list of short-form ad scripts
            3. sales_email: one-paragraph sales email (as a string)

            Return ONLY the JSON object. Do not explain anything else.
            """

    try:
        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": "You are an AI monetization expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        print("[DEBUG] Raw GPT output:")
        print(response.choices[0].message.content)

        outputs = extract_json_from_response(response.choices[0].message.content)
        idea["assets"] = outputs

        with open("memory/ideas_enriched.json", "a", encoding="utf-8") as f:
            json.dump(idea, f)
            f.write("\n")

        return outputs

    except Exception as e:
        print(f"[ERROR] GPT generation failed for idea: {idea.get('name')} — {e}")
        return None

def run_build():
    ideas = load_ideas()
    seen_hashes = already_processed_hashes()
    built_count = 0

    for idea in ideas:
        h = sha256((idea.get("name", "") + idea.get("hook", "")).encode()).hexdigest()
        if h in seen_hashes:
            print(f"[INFO] Skipping already built idea: {idea.get('name')}")
            continue

        print(f"[INFO] Building assets for: {idea.get('name')}")
        build_assets(idea)
        built_count += 1

        if IS_DEV and built_count >= 1:
            print("[DEBUG] DEV mode active — stopping after 1 idea.")
            break

if __name__ == "__main__":
    run_build()
