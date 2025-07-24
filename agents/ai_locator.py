import os
import json
import re
from bs4 import BeautifulSoup, Comment
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Helper: Strip tags and reduce HTML to core elements
def clean_html(html):
    from bs4 import BeautifulSoup, Comment
    import re

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-informative tags
    for tag in soup(["script", "style", "noscript", "meta", "link", "iframe", "svg", "base", "object", "head"]):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove hidden fields (inputs and elements)
    for el in soup.select('[type="hidden"], [aria-hidden="true"], [style*="display:none"], [style*="visibility:hidden"]'):
        el.decompose()

    # Remove base64 images
    for img in soup.find_all("img"):
        if img.get("src", "").startswith("data:image"):
            img.decompose()

    # Remove inline JS attributes
    for tag in soup.find_all():
        for attr in list(tag.attrs):
            if attr.lower().startswith("on") or attr.lower() in ["style", "class", "id"]:
                del tag[attr]

    # Optional: keep only tags that convey structure or meaning
    whitelist_tags = {"div", "a", "button", "form", "input", "label", "h1", "h2", "h3", "h4", "ul", "li", "span", "p", "strong", "em"}
    for tag in soup.find_all():
        if tag.name not in whitelist_tags:
            tag.unwrap()  # keep text, remove tag

    # Collapse excessive whitespace
    cleaned_html = str(soup)
    cleaned_html = re.sub(r"\s{2,}", " ", cleaned_html)

    return cleaned_html

# Core LLM wrapper
async def query_gpt(prompt):
    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"GPT Error: {e}")
        return None

# --- Public Methods ---

async def get_selector(html, target_description):
    html_snippet = clean_html(html)[:7000]  # stay under token limits

    prompt = f"""
    You are a Playwright automation expert. Your task is to extract a CSS selector for a specific UI element from the following HTML:

    {html_snippet}

    Target element: "{target_description}"

    Requirements:
    - Return the most specific and complete **CSS selector** string needed to locate the element.
    - Prefer `id`, `name`, or `type` attributes if available.
    - If no clear element exists, return "null" (just that string, nothing else).
    - Do **not** return any explanation, markdown, or extra text.

    Output format: Just the CSS selector string. No quotes, no backticks, no markdown.
    """

    raw = await query_gpt(prompt)

    if raw is None:
        print("⚠️ GPT returned None for selector.")
        return None

    selector = raw.strip().strip('"').strip("'")

    # Basic sanity check
    if selector.lower() == "null":
        return None

    if not selector.startswith(".") and not selector.startswith("#") and "[" not in selector:
        print(f"⚠️ GPT likely returned a non-selector: {selector}")
        return None

    return selector


async def analyze_site(html):
    html_snippet = clean_html(html)[:7000]
    prompt_template = f"""
    You are an AI site analyst. A user has loaded a webpage and needs a high-level understanding of its structure and purpose.

    Below is the cleaned HTML of the page:

    {html_snippet}

    Your job is to analyze this HTML and return a structured JSON object that answers the following:

    - has_login: true or false
    - site_type: "marketplace", "blog", "saas", etc. (choose one word that best describes the site, not limited to these examples - if the site is an affiliate marketplace, call it "affiliate" - if the site type cannot be determined, return "unknown" for site_type)

    ONLY return these fields in a JSON object.

    Example:
    {{
    "has_login": true,
    "site_type": "marketplace"
    }}

    Guidelines:
    - If a login form is directly present (e.g. with email/password inputs), or if there's a link clearly labeled "Login" or "Sign In", return has_login = true.

    ⚠️ Do NOT include any HTML selectors, CSS, explanations, markdown, or extra commentary.
    Return a valid JSON object only.
    """
    attempt = 0
    while attempt < 5:
        print("🔎 Final prompt sent to GPT:")
        print(prompt_template)

        raw_response = await query_gpt(prompt_template)

        if raw_response is None:
            print("⚠️ GPT returned None")
            continue

        if raw_response.strip() == "{response}":
            print("⚠️ GPT returned placeholder '{response}' — something's broken in prompt formatting or LLM logic.")
            continue

        try:
            result = json.loads(raw_response)
            return result
        except Exception as e:
            print(f"❌ Failed to parse JSON (attempt {attempt+1}): {e}\nRaw response: {raw_response}")
            attempt += 1

    print("🛑 analyze_site failed after 5 retries.")
    return {}

async def get_affiliate_fields(html_snippet: str):
    html_snippet = clean_html(html_snippet)[:5000]  # Token-safe trim

    prompt = f"""
    You are a senior affiliate marketer and short-form content strategist (TikTok, Reels, Shorts). Below is the HTML content of a product or service listing from a public marketplace (e.g. Digistore24, ClickBank, SaaS platform, course site, etc.).

    Your task: return a JSON array of the most important fields that should be scraped to promote or monetize this item. Prioritize:

    - Value proposition
    - Audience targeting
    - Key product/service features
    - Pricing and payout structure (affiliate commissions, EPC, etc.)
    - Conversion performance
    - Promotional support (sales pages, affiliate links)
    - Content angle opportunities (emotional appeal, urgency, etc.)

    Avoid backend details, UI elements, or generic layout info. Focus only on what a professional affiliate or video creator would need to position and promote this offer online.

    Here are examples of useful fields (do not limit to these, use judgment):
    - Product title
    - Price
    - Commission percentage
    - Description
    - Vendor name
    - Online since date
    - Audience or category
    - Cancellation rate
    - Sales page URL
    - Affiliate resource/support links
    - Primary CTA label
    - Key benefit claims

    Return only a valid JSON array of field names. No markdown. No explanation.

    HTML:
    {html_snippet}
    """
    response = await query_gpt(prompt)
    try:
        return json.loads(response)
    except Exception as e:
        print(f"⚠️ Failed to parse field list JSON: {e}\nRaw response: {response}")
        return []
    
async def get_selectors_from_strategy(html: str, site_type: str) -> dict:
    html_snippet = clean_html(html)[:7000]

    # Step 1 – natural language scraping strategy
    strategy_prompt = f"""
    You are an AI scraping strategist helping a Playwright-based automation system.

    A user is exploring a site identified as: **{site_type}**
    Here is the current page HTML (cleaned):
    {html_snippet}

    Return a concise scraping strategy in natural language. Answer in 3 short paragraphs:

    1. What the site appears to contain (e.g. product catalog, blog posts, dashboard data, listing grid, etc.)
    2. What valuable data or content might be extractable — describe it using UI terms like "product cards", "pagination buttons", "affiliate links", "expand buttons", "article titles", etc.
    3. What the next 2–3 actions should be for a scraper (e.g. login, click something, find key elements, extract loopable units)

    Respond as raw plain text.
    """
    strategy = await query_gpt(strategy_prompt)
    if not strategy:
        print("🛑 Failed to generate strategy.")
        return {}

    print("🧭 Scraping Strategy:\n", strategy)

    # Step 2 – ask for selector targets
    target_prompt = f"""
    You are an AI automation assistant. Based on the following scraping strategy, return a JSON array of UI elements this scraper should locate using CSS selectors:

    Strategy:
    {strategy}

    Output example:
    [
    "catalog_url",
    "product_card_selector",
    "pagination_button_selector",
    "affiliate_link_selector"
    ]

    Respond with only a valid JSON array, no extra text.
    """
    raw_targets = await query_gpt(target_prompt)
    try:
        target_fields = json.loads(raw_targets)
    except Exception as e:
        print(f"⚠️ Failed to parse selector target list: {e}\nRaw: {raw_targets}")
        return {}

    # Step 3 – resolve selectors via get_selector
    selectors = {}
    for target in target_fields:
        print(f"🎯 Locating selector for: {target}")
        selector = await get_selector(html, target.replace("_", " "))
        selectors[target] = selector

    return selectors

async def html_looks_valid(html: str) -> bool:
    cleaned = clean_html(html)[:7000]  # Token-safe trim
    prompt = f"""
    You are an AI system checking whether a given HTML snapshot is useful for site analysis.

    If the HTML mostly contains cookie banners, loading screens, modals, or empty markup, return false.
    If the HTML includes visible text content, page structure, navigation, or interactive elements like login forms or product listings, return true.

    HTML:
    {cleaned}

    Answer in JSON:
    {{"valid": true}} or {{"valid": false}}
    """

    response = await query_gpt(prompt)
    try:
        return json.loads(response).get("valid", False)
    except:
        return False

