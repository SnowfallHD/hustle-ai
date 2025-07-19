import subprocess
import time
import json
import os
from datetime import datetime

# === CONFIG ===
FOCUS_AGENT = "researcher"
SCRIPT_PATH = f"agents/{FOCUS_AGENT}.py"
BACKUP_PATH = f"{SCRIPT_PATH}.bak"
ERROR_LOG = "logs/researcher_errors.log"
LLM_FIX_SCRIPT = "agents/fix_with_llm.py"  # you create this helper for GPT calls

os.makedirs("logs", exist_ok=True)

def log_patch(error_text, llm_response):
    with open("logs/self_update_history.txt", "a", encoding="utf-8") as f:
        f.write(f"\n=== {datetime.now()} ===\n")
        f.write("ERROR:\n")
        f.write(error_text + "\n\n")
        f.write("LLM PATCH:\n")
        f.write(llm_response + "\n")

def run_script_and_capture_output():
    print(f"[INFO] Running {FOCUS_AGENT}...")
    try:
        result = subprocess.run(["python", SCRIPT_PATH], capture_output=True, text=True, timeout=60)
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return "", "[TIMEOUT] Script took too long and was terminated."

def extract_playwright_errors(stderr):
    lines = stderr.splitlines()
    relevant = [line for line in lines if "playwright" in line.lower() or "selector" in line.lower()]
    return "\n".join(relevant)

def log_error(error_text):
    with open(ERROR_LOG, "a") as f:
        f.write(f"\n=== {datetime.now()} ===\n{error_text}\n")

def backup_original():
    if not os.path.exists(BACKUP_PATH):
        with open(SCRIPT_PATH, "r") as src, open(BACKUP_PATH, "w") as dst:
            dst.write(src.read())
        print("[INFO] Backed up original script.")

def send_to_llm_and_get_fix(error_text):
    print("[INFO] Sending error to LLM for fix...")
    result = subprocess.run(["python", LLM_FIX_SCRIPT, error_text], capture_output=True, text=True)
    return result.stdout  # should be the fixed code returned from GPT/Claude

def write_fixed_script(new_code):
    with open(SCRIPT_PATH, "w") as f:
        f.write(new_code)
    print("[INFO] Wrote fixed code to researcher.py.")

def revert_to_backup():
    print("[INFO] Reverting to backup...")
    with open(BACKUP_PATH, "r") as src, open(SCRIPT_PATH, "w") as dst:
        dst.write(src.read())

def main():
    print("[LOOP] Starting HustleAI Self-Correction Loop")
    backup_original()

    while True:
        stdout, stderr = run_script_and_capture_output()
        if "Traceback" not in stderr:
            print("[SUCCESS] Script ran without critical error.")
            break

        error = extract_playwright_errors(stderr)
        if error:
            log_error(error)
            new_code = send_to_llm_and_get_fix(error)
            if "def" in new_code and "playwright" in new_code:
                log_patch(error, new_code)
                write_fixed_script(new_code)
            else:
                print("[WARNING] LLM response suspicious — reverting.")
                revert_to_backup()
        else:
            print("[INFO] No playwright-related errors found.")
            break

        print("[LOOP] Sleeping before next retry...")
        time.sleep(30)

if __name__ == "__main__":
    main()
