import sys
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

error_input = sys.argv[1]

prompt = f"""
You're an expert Python and Playwright developer working inside a self-improving AI system called HustleAI.

The current script you're fixing is `researcher.py`, an autonomous web scraping agent responsible for:
- Logging into Digistore24
- Scraping product cards (title, category, commission %, etc.)
- Returning structured affiliate data
- Using Playwright (headless browser automation)

GOAL:
Your fix should ensure the researcher agent functions **robustly, without manual clicks**, handles **dynamic DOMs**, and uses **resilient selectors** (avoid brittle XPaths if possible). It must complete the full scrape loop or fail gracefully.

Only return a complete updated version of researcher.py.
No comments, no explanations — just valid Python code.
If you’re unsure, use try/except and make it work.
ERROR:
{error_input}
"""

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)

fixed_code = response.choices[0].message.content.strip()

# Strip ```python ... ``` if present
if fixed_code.startswith("```"):
    fixed_code = fixed_code.strip("`")  # remove all backticks
    if "python" in fixed_code:
        fixed_code = fixed_code.split("python", 1)[-1].strip()
    if fixed_code.endswith("```"):
        fixed_code = fixed_code[:-3].strip()

print(fixed_code)
