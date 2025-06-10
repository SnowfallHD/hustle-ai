import json
import re
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_ideas():
    with open("memory/ideas.json", "r") as f:
        lines = f.readlines()
        if not lines:
            raise ValueError("No ideas found. Run researcher.py first.")
        ideas = [json.loads(line.strip()) for line in lines]
    return ideas[-1]

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
        model="gpt-4-1106-preview",  # more consistent output
        messages=[{"role": "user", "content": prompt}]
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
