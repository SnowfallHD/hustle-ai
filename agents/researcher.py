import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from enricher import enrich_offers
from ai_locator import get_selector, analyze_site, get_affiliate_fields, get_selectors_from_strategy, html_looks_valid

load_dotenv()

# 🔗 Target site (set dynamically)
TARGET_URL = "https://www.digistore24.com/"

# Site information
has_login: bool
site_type: str

# 🔐 Credentials (from .env)
DIGISTORE_EMAIL = os.getenv("DIGISTORE_EMAIL")
DIGISTORE_PASSWORD = os.getenv("DIGISTORE_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([DIGISTORE_EMAIL, DIGISTORE_PASSWORD, OPENAI_API_KEY]):
    raise EnvironmentError("Missing required environment variables in .env")


# Helper: Fill login form dynamically
async def login_if_needed(page, html):
    # Step 1: Analyze whether login is needed
    analysis = await analyze_site(html)

    if not analysis.get("has_login"):
        print("🔓 No login required.")
        return

    print("🔐 Login required. Attempting login...")

    # Step 2: Try clicking login link/button if present
    login_link_selector = await get_selector(html, "Login link or button in the top navigation")
    if login_link_selector:
        try:
            await page.click(login_link_selector)
            await page.wait_for_timeout(1500)  # allow modal or redirect to load
            html = await page.content()  # refresh HTML after login UI is visible
        except Exception as e:
            print(f"⚠️ Failed to click login link: {e}")

    # Step 3: Detect iframe if applicable
    iframe_selector = await get_selector(html, "Iframe containing the login form (if any)")
    if iframe_selector:
        try:
            frame_element = await page.query_selector(iframe_selector)
            frame = await frame_element.content_frame()
            email_selector = await get_selector(await frame.content(), "Email input field for login")
            password_selector = await get_selector(await frame.content(), "Password input field for login")
            submit_selector = await get_selector(await frame.content(), "Login button to submit the form")
            await frame.fill(email_selector, DIGISTORE_EMAIL)
            await frame.fill(password_selector, DIGISTORE_PASSWORD)
            await frame.click(submit_selector)
        except Exception as e:
            print(f"⚠️ Failed to login inside iframe: {e}")
            return
    else:
        # Step 4: Direct login form on page
        email_selector = await get_selector(html, "Email input field for login")
        password_selector = await get_selector(html, "Password input field for login")
        submit_selector = await get_selector(html, "Login button to submit the form")
        try:
            await page.fill(email_selector, DIGISTORE_EMAIL)
            await page.fill(password_selector, DIGISTORE_PASSWORD)
            await page.click(submit_selector)
        except Exception as e:
            print(f"⚠️ Failed to login on main page: {e}")
            return

    # Step 5: Wait for login to complete
    await page.wait_for_load_state("networkidle")
    print("✅ Logged in successfully.")

# Helper: Navigate to marketplace or main scrape zone using pre-processed site_info
async def navigate_to_target_area(page, site_info):
    catalog_url = site_info.get("catalog_url")
    if not catalog_url:
        print("🛑 No catalog_url found in site_info.")
        return None

    print(f"🛒 Navigating to catalog: {catalog_url}")
    await page.goto(catalog_url)
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    return site_info

async def scrape(page, site_info, selectors):
    site_type = site_info.get("site_type", "unknown")

    if site_type == "affiliate":
        return await scrape_affiliate_cards(page, site_info, selectors)
    else:
        return await scrape_general_site(page, selectors)

async def scrape_affiliate_cards(page, site_info, selectors):
    offers = []

    # Handle dropdown to increase items per page
    if site_info.get("has_page_size_dropdown"):
        try:
            await page.click(site_info["page_size_dropdown_selector"])
            await page.click(site_info["max_items_option_selector"])
            await page.wait_for_timeout(2000)
            print("✅ Maximized items per page.")
        except:
            print("⚠️ Pagination optimization failed.")

    page_number = 1
    while True:
        print(f"📄 Scraping page {page_number}...")

        content_selector = selectors.get("product_card_selector")
        if not content_selector:
            print("⚠️ No product_card_selector returned.")
            break

        content_elements = await page.query_selector_all(content_selector)
        print(f"🔍 Found {len(content_elements)} product cards.")

        for element in content_elements:
            el_html = await element.inner_html()
            item_data = {}

            # Optional: Handle detail view expansion if needed
            if site_info.get("product_detail_selector"):
                try:
                    detail = await element.query_selector(site_info["product_detail_selector"])
                    if detail:
                        await detail.click()
                        await page.wait_for_timeout(1000)
                except:
                    print("⚠️ Could not expand detail view.")

            # AI-based field extraction
            field_list = await get_affiliate_fields(el_html)
            for field in field_list:
                sel = await get_selector(el_html, field)
                if sel:
                    el = await element.query_selector(sel)
                    if el:
                        text = await el.inner_text() if "link" not in field.lower() else await el.get_attribute("href")
                        item_data[field.lower().replace(" ", "_")] = text.strip() if text else ""

            # Handle promotion link
            promo_link = ""
            if site_info.get("promote_button_selector") and site_info.get("promotion_link_selector"):
                try:
                    btn = await element.query_selector(site_info["promote_button_selector"])
                    if btn:
                        await btn.click()
                        await page.wait_for_timeout(2000)
                        link_el = await page.query_selector(site_info["promotion_link_selector"])
                        if link_el:
                            promo_link = await link_el.get_attribute("value")
                except:
                    print("⚠️ Failed to extract promotion link.")
            item_data["promotion_link"] = promo_link
            offers.append(item_data)

        # 🔄 Check for "Next" page
        next_selector = await get_selector(await page.content(), "Next page button")
        if next_selector:
            try:
                print("➡️ Found pagination button. Moving to next page...")
                await page.click(next_selector)
                await page.wait_for_timeout(2000)
                page_number += 1
            except Exception as e:
                print(f"⚠️ Pagination failed: {e}")
                break
        else:
            print("🛑 No more pages detected.")
            break

    return offers

async def scrape_general_site(page, selectors):
    html = await page.content()
    field_list = await get_selectors_from_strategy(html)

    result = {}

    for field in field_list:
        sel = await get_selector(html, field)
        if sel:
            try:
                el = await page.query_selector(sel)
                if el:
                    # Extract href if it's a link-related field
                    if "link" in field.lower():
                        text = await el.get_attribute("href")
                    else:
                        text = await el.inner_text()
                    if text:
                        result[field.lower().replace(" ", "_")] = text.strip()
                    else:
                        print(f"⚠️ No text found for field '{field}' using selector '{sel}'")
                else:
                    print(f"⚠️ Element not found for selector: {sel} → field: {field}")
            except Exception as e:
                print(f"❌ Error while querying selector {sel}: {e}")
        else:
            print(f"⚠️ No selector returned for field: {field}")

    return [result] if result else []

async def dismiss_cookie_popup_if_present(page):
    """
    Try to dismiss Cookiebot popups by clicking the first visible button inside the modal.
    """
    try:
        modal_selector = "#CybotCookiebotDialog"
        modal = page.locator(modal_selector)

        if await modal.is_visible():
            print("🍪 Cookiebot dialog detected.")

            # Try the common accept button first
            try:
                accept_button = modal.locator('button#CybotCookiebotDialogBodyButtonAccept')
                if await accept_button.is_visible():
                    print("🍪 Clicking Cookiebot Accept button...")
                    await accept_button.click()
                    await page.wait_for_timeout(1000)
            except:
                pass  # fallback to generic loop if not present

            # Click the first visible button inside the modal
            buttons = modal.locator("button")
            count = await buttons.count()
            for i in range(count):
                btn = buttons.nth(i)
                if await btn.is_visible():
                    print(f"🍪 Attempting to click button #{i} inside cookie dialog...")
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    break

            # Confirm it's gone
            try:
                await page.wait_for_function(
                    """() => {
                        const el = document.querySelector('#CybotCookiebotDialog');
                        return !el || el.offsetParent === null;
                    }""",
                    timeout=5000
                )
                print("✅ Cookie modal fully dismissed.")
                return True
            except:
                print("⚠️ Cookie modal still present after click attempt.")
                return False
        else:
            print("🍪 Cookie dialog not detected.")
            return False

    except Exception as e:
        print(f"⚠️ Error while handling cookie popup: {e}")
        return False

MAX_HTML_ATTEMPTS = 3
# Main dynamic researcher agent
async def researcher():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print(f"🌐 Visiting {TARGET_URL}...")
        await page.goto(TARGET_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)

        # Step 1: Handle cookie popup
        await dismiss_cookie_popup_if_present(page)

        html = None
        for attempt in range(MAX_HTML_ATTEMPTS):
            await page.wait_for_timeout(1500 + attempt * 500)
            html = await page.content()

            if await html_looks_valid(html):
                print(f"✅ Valid HTML detected on attempt {attempt+1}")
                break
            else:
                print(f"⚠️ Attempt {attempt+1}: HTML still looks invalid... retrying...")

        if not html or not await html_looks_valid(html):
            print("❌ Failed to retrieve valid HTML after multiple attempts.")
            await browser.close()
            return

        # 👇 Continue site analysis with clean HTML
        site_analysis = await analyze_site(html)

        await page.wait_for_timeout(1000)  # small buffer

        # Step 2: Analyze the site structure
        html = await page.content()
        site_analysis = await analyze_site(html)
        print("🧠 Site Analysis:", site_analysis)

        has_login = site_analysis.get("has_login", False)
        site_type = site_analysis.get("site_type", "unknown")

        # Step 3: Login if required
        if has_login:
            print("🔐 Site requires login. Attempting login...")
            await login_if_needed(page, html)
            await page.wait_for_timeout(1500)
            html = await page.content()  # Refresh HTML after login
        else:
            print("✅ No login required.")

        # Step 4: Navigate to marketplace/content area
        site_info = await navigate_to_target_area(page, site_analysis)
        if not site_info:
            print("🛑 Exiting: No scrapeable content detected.")
            await browser.close()
            return

        # Step 5: Get selectors after reaching main content
        html = await page.content()
        selectors = await get_selectors_from_strategy(html, site_type)
        if not selectors:
            print("🛑 Exiting: No selectors returned by GPT.")
            await browser.close()
            return

        # Step 6: Scrape content based on site type
        offers = await scrape(page, site_info, selectors)

        # Step 7: Enrich the scraped offers
        enriched = enrich_offers(offers)
        print("✅ Enriched Offers:")
        for offer in enriched:
            print(offer)

        await browser.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(researcher())
