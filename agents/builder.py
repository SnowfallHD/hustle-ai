import json
import re
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    with open("memory/outputs.json", "a", encoding="utf-8") as f:
        json.dump(outputs, f)
        f.write("\n")

    return outputs

def run_build():
    idea = load_ideas()
    return build_assets(idea)

if __name__ == "__main__":
    output = run_build()
    print(json.dumps(output, indent=2))
