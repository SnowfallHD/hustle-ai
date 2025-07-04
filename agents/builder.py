import json
import re
import os
from dotenv import load_dotenv
from openai import OpenAI
from hashlib import sha256

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
IS_DEV = os.getenv("DEV_MODE") == "1"

IDEAS_PATH = "memory/ideas.json"
OUTPUTS_PATH = "memory/outputs.json"

def already_processed_hashes():
    hashes = set()
    if not os.path.exists(OUTPUTS_PATH):
        return hashes
    with open(OUTPUTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                h = sha256((data.get("name", "") + data.get("hook", "")).encode()).hexdigest()
                hashes.add(h)
            except:
                continue
    return hashes

def load_ideas():
    if not os.path.exists(IDEAS_PATH):
        return []
    with open(IDEAS_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line.strip()) for line in f if line.strip()]

def save_remaining_ideas(remaining):
    with open(IDEAS_PATH, "w", encoding="utf-8") as f:
        for idea in remaining:
            f.write(json.dumps(idea) + "\n")

def extract_json_from_response(text):
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("No valid JSON object found in response.")

def build_assets(idea):
    prompt = f"""
            You are the Builder Agent for HustleAI. Here's an idea:

            Offer Name: {idea.get('name', 'N/A')}
            Hook: {idea.get('hook', 'N/A')}
            Platform: {idea.get('platform', 'N/A')}
            Content Type: {idea.get('content', 'N/A')}

            Create the following in raw JSON:
            1. landing_page: {{headline, benefits (list), CTA}}
            2. ad_hooks: list of short-form ad scripts
            3. sales_email: one-paragraph sales email (as a string)

            Return ONLY the JSON object.
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

        content = response.choices[0].message.content.strip()
        print("[DEBUG] GPT Output:", content[:200], "...\n")
        parsed = extract_json_from_response(content)

        idea["assets"] = parsed
        with open(OUTPUTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(idea) + "\n")

        print(f"[SUCCESS] Built and saved assets for: {idea['name']}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to build assets for {idea.get('name', 'Unknown')}: {e}")
        return False

def run_build():
    all_ideas = load_ideas()
    seen_hashes = already_processed_hashes()

    remaining_ideas = []
    processed_count = 0

    for idea in all_ideas:
        h = sha256((idea.get("name", "") + idea.get("hook", "")).encode()).hexdigest()
        if h in seen_hashes:
            print(f"[SKIP] Already processed: {idea['name']}")
            continue

        print(f"[BUILDING] {idea['name']}")
        success = build_assets(idea)
        if success:
            processed_count += 1
        else:
            remaining_ideas.append(idea)  # Retry next run

        if IS_DEV and processed_count >= 1:
            print("[DEBUG] DEV_MODE active — stopping after 1 idea.")
            break

    save_remaining_ideas(remaining_ideas)
    print(f"\n✅ Build complete. {processed_count} new idea(s) processed. {len(remaining_ideas)} remaining.")

if __name__ == "__main__":
    run_build()