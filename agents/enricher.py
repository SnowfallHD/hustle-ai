import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Helper: Query GPT for enrichment
async def enrich_offer(offer):
    # Format the dynamic offer data into a readable block
    formatted_fields = "\n".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in offer.items() if v.strip()])

    prompt = f"""
    You are an expert in content creation and digital marketing. The following item is a product or service scraped from a public marketplace or website.

    Based on the information provided, determine:

    1. What is this product or service really about?
    2. Is it a digital product, physical product, or service?
    3. What niche or audience is it intended for?
    4. How are people successfully promoting this type of product on platforms like TikTok and Instagram right now? Include successful hooks, content angles, CTA structures, and hashtags.
    5. What types of content (educational, emotional, story-based, skits, trends, etc.) work best for this specific offer?
    6. What should be avoided based on what doesn't work well for this category?
    7. Based on all of the above, generate a comprehensive content kit tailored for this product with the following files:

    - `product_summary.txt` – clear overview, audience fit, competitive edge
    - `hooks.txt` – 10 viral TikTok/Instagram hook examples
    - `scripts.txt` – 5 short-form video scripts optimized for Reels/Shorts
    - `hashtag_sets.txt` – 3 hashtag clusters by category (broad, niche, branded)
    - `angle_breakdown.txt` – detailed content angles that can be reused across videos
    - `cta_templates.txt` – best performing CTA variations for this product category

    Only generate clean and ready-to-save content. Do not output JSON, markdown, or explanations. Each section should be clearly labeled with a header and followed by the content.

    Here is the raw product data:

    {formatted_fields}
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return None


# Main enrichment entrypoint
def enrich_offers(offers):
    enriched = []
    for offer in offers:
        safe_title = offer['title'].strip().replace("/", "-").replace("\\", "-")[:50]
        folder = OUTPUT_DIR / safe_title
        folder.mkdir(exist_ok=True)

        print(f"✨ Enriching: {offer['title']}")
        import asyncio
        enriched_data = asyncio.run(enrich_offer(offer))

        if enriched_data:
            # Save entire content kit as one file, then split if needed
            full_output_path = folder / "content_kit.txt"
            with open(full_output_path, "w", encoding="utf-8") as f:
                f.write(enriched_data)
            print(f"✅ Saved content kit for '{offer['title']}'")
        else:
            print(f"❌ Skipped '{offer['title']}' due to enrichment failure.")

        enriched.append({"title": offer['title'], "folder": str(folder)})

    return enriched
