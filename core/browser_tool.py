from playwright.sync_api import sync_playwright
import time
import json

class BrowserTool:
    def __init__(self, headless=True, devtools=False):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless, devtools=devtools)
        self.page = self.browser.new_page()

    def close(self):
        self.browser.close()
        self.playwright.stop()

    def goto(self, url):
        print(f"[🌐] Navigating to: {url}")
        self.page.goto(url)

    def wait_for_selector(self, selector, timeout=10000):
        print(f"[⏳] Waiting for selector: {selector}")
        return self.page.wait_for_selector(selector, timeout=timeout)

    def click(self, selector):
        print(f"[🖱️] Clicking: {selector}")
        try:
            el = self.page.locator(selector).first
            el.wait_for(state="visible", timeout=10000)
            el.click()
            print("[✅] Clicked element successfully.")
        except Exception as e:
            print(f"[❌] Click failed for selector '{selector}': {e}")
            raise

    def click_by_text(self, text):
        print(f"[🖱️] Clicking by text: {text}")
        try:
            self.page.get_by_text(text).click(timeout=10000)
        except Exception as e:
            raise RuntimeError(f"Failed to click by text: {text}") from e

    def click_by_description(self, description):
        print(f"[🧠] Searching for elements matching description: '{description}'")
        candidates = self.page.locator('button, a, select, option, div, span, label, input').all()
        print(f"[📋] Found {len(candidates)} elements")
        descriptions = []

        for i, el in enumerate(candidates):
            try:
                box = el.bounding_box()
                text = el.inner_text().strip()
                aria = el.get_attribute("aria-label")
                alt = el.get_attribute("alt")
                title = el.get_attribute("title")
                value = el.get_attribute("value")

                descriptions.append({
                    "index": i,
                    "text": text,
                    "aria": aria,
                    "alt": alt,
                    "title": title,
                    "value": value,
                    "box": box
                })
            except:
                continue

        with open("click_candidates_debug.json", "w") as f:
            json.dump(descriptions, f, indent=2)

        for el in candidates:
            try:
                el.hover()
                el.click(timeout=3000)
                print("[✅] Fuzzy click by description succeeded.")
                return
            except:
                continue

        raise RuntimeError(f"Failed to click any element matching description: '{description}'")

    def locate_and_click(self, agent, question, retry=True):
        print(f"[🤖] Asking agent to visually locate: {question}")
        screenshot = "temp_click.png"
        self.page.screenshot(path=screenshot, full_page=True)

        result = agent.locate_from_vision(screenshot, question)
        print("[❓] Raw GPT vision output:", str(result)[:500])

        if not result:
            raise RuntimeError("Vision agent failed to return actionable result.")

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                print("[⚠️] GPT response was not valid JSON.")
                start = result.find("{")
                end = result.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        result = json.loads(result[start:end])
                    except Exception as e:
                        raise RuntimeError("Failed to parse JSON from GPT response.") from e
                else:
                    raise RuntimeError("No valid JSON structure found in GPT response.")

        if not isinstance(result, dict):
            raise RuntimeError(f"Vision agent returned non-dict result: {result}")

        typ = result.get("type")
        value = result.get("value")
        confidence = result.get("confidence", None)

        print(f"[📍] type={typ}, value={value}, confidence={confidence}")

        try:
            if typ == "selector":
                self.click(value)
            elif typ == "text":
                self.click_by_text(value)
            elif typ == "description":
                self.click_by_description(value)
            else:
                raise RuntimeError(f"Unsupported click type: {typ}")
        except Exception as e:
            print(f"[❌] Failed to click with method '{typ}': {e}")
            if retry:
                print("[🔁] Retrying with rephrased question...")
                return self.locate_and_click(agent, f"(Retry) {question}", retry=False)
            else:
                self.page.screenshot(path="failed_click_debug.png")
                with open("last_bad_gpt_click.json", "w") as f:
                    f.write(json.dumps({"question": question, "result": result}, indent=2))
                raise
