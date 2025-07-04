import subprocess
import sys
import time
import os

print("[DEBUG] DEV_MODE =", os.getenv("DEV_MODE"))

def run_agent(script_path, label, timeout=300):  # e.g. 5-minute timeout
    print(f"\n[+] Running {label}...")
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            print(f"[ERROR] {label} failed:\n{result.stderr}")
        else:
            print(f"[{label} Output]\n{result.stdout}")
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {label} took too long and was terminated.")

def main():
    print("=== AI Income System: Daily Launch Cycle ===")
    run_agent("agents/researcher.py", "Researcher Agent")
    time.sleep(1)

    run_agent("agents/builder.py", "Builder Agent")
    time.sleep(1)

    run_agent("agents/executor.py", "Executor Agent")
    time.sleep(1)

    print("✅ Daily cycle completed.")

if __name__ == "__main__":
    main()
