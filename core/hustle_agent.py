import os
import json
import base64
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class HustleAgent:
    def __init__(self, model="gpt-4o", client=None):
        self.model = model
        self.client = client or OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _encode_image(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def ask(self, prompt: str, html: str = None, screenshot_path: str = None, expect_json: bool = False):
        """Main interface to reason over tasks."""
        messages = [{"role": "user", "content": prompt}]

        if html:
            messages.append({"role": "user", "content": f"HTML context:\n\n{html[:8000]}"})
        if screenshot_path:
            base64_img = self._encode_image(screenshot_path)
            messages.append({
                "role": "user",
                "content": [
                    { "type": "text", "text": prompt },
                    { "type": "image_url", "image_url": { "url": f"data:image/png;base64,{base64_img}" } }
                ]
            })

        print(f"[🧠] Sending prompt to {self.model}...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        content = response.choices[0].message.content.strip()

        if expect_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                print("[⚠️] GPT response was not valid JSON.")
                return {"type": "text", "value": content}

        return content

    def enrich_offer(self, offer: dict):
        prompt = f"""
        Enrich this affiliate offer for marketing:

        Name: {offer.get("name")}
        Description: {offer.get("description")}

        Return JSON with:
        - Hook
        - Ideal platform
        - Best content type
        - Monetization difficulty (Low/Medium/High)
        - Expected ROI (Low/Medium/High)
        """
        return self.ask(prompt, expect_json=True)

    def get_selector_from_dom(self, html: str, task: str):
        prompt = f"""
        Here's a task: "{task}"
        Read the HTML and return the most reliable CSS selector or description to accomplish it.
        Format: {{ "type": "selector" or "text", "value": "..." }}
        """
        return self.ask(prompt, html=html, expect_json=True)

    def locate_from_vision(self, screenshot_path: str, task: str):
        prompt = f"""
        You are a visual AI assistant. Given a screenshot of a web page, your task is to locate an element that matches this instruction:

        ➡️ "{task}"

        Respond ONLY with a JSON object in this format:
        {{
        "type": "selector" | "text" | "description",
        "value": "string describing the element to interact with",
        "confidence": float between 0 and 1 (your confidence in this match)
        }}

        Be specific. If you can provide a CSS selector, do so. Otherwise, return the most accurate visible text or a strong description of the visual element. Do not wrap your output in triple backticks or Markdown formatting.
        """

        result = self.ask(prompt, screenshot_path=screenshot_path, expect_json=True)

        if isinstance(result, dict):
            # Patch in confidence if missing
            if "confidence" not in result:
                result["confidence"] = 1.0
        return result

    
    def create_marketing_bundle(self, offer):
        prompt = f"""
        Given this affiliate offer:

        Name: {offer.get("name")}
        Description: {offer.get("description")}
        Hook: {offer.get("hook")}
        Platform: {offer.get("platform")}
        Content Type: {offer.get("content")}
        ROI: {offer.get("roi")}
        Difficulty: {offer.get("difficulty")}

        Generate a marketing bundle in JSON format:
        - short_hook: 5-10 word punchy version of the hook
        - ad_caption: Instagram/TikTok caption format (max 300 characters)
        - script_idea: A TikTok or Reels video script outline for this offer
        - CTA: A strong, urgent call to action
        - hashtags: 5-8 hashtags for this offer type/platform
        """
        return self.ask(prompt, expect_json=True)

