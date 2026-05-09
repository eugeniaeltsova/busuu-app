#!/usr/bin/env python3
"""
Busuu App — AI Setup Assistant
Run once on a new machine to set everything up.
No technical knowledge required.
"""

import json
import os
import secrets
import string
import subprocess
import sys
import webbrowser

APP_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = f"""You are a friendly, patient setup assistant helping a non-technical user \
install the Busuu Exercise App on their Mac.

The app folder is: {APP_DIR}

Work through this checklist in order. Complete each step fully before moving on.

─── STEP 1: Check Python ───────────────────────────────────────────────────
Run `python3 --version`.
- If 3.11 or higher → great, move on.
- If lower or missing → open https://www.python.org/downloads/ and tell the user
  to download Python 3.11, install it, then come back and type "done".

─── STEP 2: Create virtual environment ─────────────────────────────────────
Check if {APP_DIR}/.venv exists. If not, run:
  python3 -m venv {APP_DIR}/.venv
Confirm it was created successfully.

─── STEP 3: Install dependencies ───────────────────────────────────────────
Run:
  {APP_DIR}/.venv/bin/pip install -r {APP_DIR}/requirements.txt --quiet
If it fails, diagnose the error and fix it before continuing.

─── STEP 4: Configure the .env file ────────────────────────────────────────
Check if {APP_DIR}/.env exists and already has real values (not placeholders).
If it needs filling in:

  4a. DATABASE_URL — Supabase (free PostgreSQL)
      - Open https://supabase.com for the user
      - Instructions: create a free account → New project → Settings → Database
        → copy the "Direct connection" string
      - The URL format must be:
        postgresql+asyncpg://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres
      - Ask the user to paste their connection string

  4b. SECRET_KEY — generate one automatically with generate_secret tool

  4c. Azure OpenAI credentials
      - Open https://portal.azure.com for the user
      - Instructions: search "Azure OpenAI" → select their resource →
        Keys and Endpoint → copy Key 1 and Endpoint
      - AZURE_OPENAI_DEPLOYMENT is almost always "gpt-4o"
      - AZURE_OPENAI_API_VERSION is "2024-10-21" (use this default)
      - Ask the user for their API key and endpoint URL

  Once you have all values, write the complete .env file.

─── STEP 5: Export Busuu cookies ───────────────────────────────────────────
- Open https://busuu.com and tell the user to log in if they aren't already
- Open the Cookie-Editor Chrome extension page:
  https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
- Tell them: install it → go back to busuu.com → click the extension icon →
  click Export → Export as JSON → copy everything → paste into a new file
  called busuu_cookies.json and save it in the app folder
- Check that {APP_DIR}/busuu_cookies.json exists before continuing

─── STEP 6: Start the app ──────────────────────────────────────────────────
- Run: {APP_DIR}/.venv/bin/python {APP_DIR}/run.py  (in the background)
- Wait 3 seconds, then open http://localhost:8000
- Tell the user they're all set and explain what to do on the start page:
  enter their Busuu email, select their languages, the cookie file is already
  configured, then click Sync.

═══════════════════════════════════════════════════════════════════════════════
RULES:
- Plain English only — never show raw commands or code to the user
- One sentence explaining WHY before each step
- Always verify a step succeeded before moving to the next
- If something fails, fix it — never skip ahead
- Be warm and encouraging; celebrate each completed step with a short message
- Never ask the user to type a terminal command themselves — you run everything
- When asking for API keys, give exact step-by-step instructions with where to
  click, not just "go get your API key"
═══════════════════════════════════════════════════════════════════════════════
"""

TOOLS = [
    {
        "name": "run_command",
        "description": (
            "Run a shell command on the user's Mac and return stdout, stderr, and "
            "the exit code. Use for checking Python, installing packages, verifying "
            "files exist, starting the app, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "description": {
                    "type": "string",
                    "description": "Plain-English label shown to the user (e.g. 'Checking Python version')",
                },
            },
            "required": ["command", "description"],
        },
    },
    {
        "name": "write_file",
        "description": "Write text content to a file on disk (e.g. the .env file).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "ask_user",
        "description": (
            "Print a question and wait for the user to type a response. "
            "Use this to collect API keys, database URLs, or confirmations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The full question with all context the user needs to answer it",
                }
            },
            "required": ["question"],
        },
    },
    {
        "name": "open_url",
        "description": "Open a URL in the user's default browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "reason": {
                    "type": "string",
                    "description": "One-line label shown to the user explaining why we're opening this",
                },
            },
            "required": ["url", "reason"],
        },
    },
    {
        "name": "generate_secret",
        "description": "Generate a secure random string to use as SECRET_KEY in .env.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


# ── tool handlers ──────────────────────────────────────────────────────────────

def _run_command(command: str, description: str) -> dict:
    print(f"  → {description}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=APP_DIR,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 3 minutes", "success": False}
    except Exception as exc:
        return {"error": str(exc), "success": False}


def _write_file(path: str, content: str) -> dict:
    print(f"  → Writing {os.path.basename(path)}")
    try:
        with open(path, "w") as fh:
            fh.write(content)
        return {"success": True}
    except Exception as exc:
        return {"error": str(exc), "success": False}


def _ask_user(question: str) -> dict:
    print(f"\n{question}")
    answer = input("  ▶ ").strip()
    return {"response": answer}


def _open_url(url: str, reason: str) -> dict:
    print(f"  → Opening: {reason}")
    webbrowser.open(url)
    return {"opened": True}


def _generate_secret() -> dict:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    key = "".join(secrets.choice(alphabet) for _ in range(48))
    return {"secret": key}


def handle_tool(name: str, inputs: dict) -> dict:
    handlers = {
        "run_command": lambda i: _run_command(i["command"], i.get("description", "")),
        "write_file": lambda i: _write_file(i["path"], i["content"]),
        "ask_user": lambda i: _ask_user(i["question"]),
        "open_url": lambda i: _open_url(i["url"], i.get("reason", i["url"])),
        "generate_secret": lambda i: _generate_secret(),
    }
    handler = handlers.get(name)
    if handler:
        return handler(inputs)
    return {"error": f"Unknown tool: {name}"}


# ── bootstrap ──────────────────────────────────────────────────────────────────

def ensure_anthropic():
    try:
        import anthropic
        return anthropic
    except ImportError:
        print("Installing setup assistant (this takes a few seconds)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "anthropic", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import anthropic
        return anthropic


def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    print("\nThe setup assistant needs an Anthropic API key to run.")
    print("You can get a free one at https://console.anthropic.com")
    webbrowser.open("https://console.anthropic.com")
    print()
    return input("Paste your Anthropic API key here and press Enter: ").strip()


# ── main agent loop ────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 55)
    print("  Busuu Exercise App — Setup Assistant")
    print("=" * 55)
    print()
    print("This assistant will set up everything for you.")
    print("You won't need to type any technical commands.\n")

    anthropic = ensure_anthropic()
    api_key = get_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    messages = [
        {"role": "user", "content": "Please start the setup and guide me through each step."}
    ]

    while True:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        for block in response.content:
            if hasattr(block, "text") and block.text.strip():
                print(f"\n{block.text}")

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = handle_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            user_input = input("\nYou: ").strip()
            if not user_input or user_input.lower() in ("exit", "quit", "bye", "done"):
                print("\nSetup session ended. Run this script again any time.\n")
                break
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": user_input})


if __name__ == "__main__":
    main()
