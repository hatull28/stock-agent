import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")
hook = os.getenv("DISCORD_WEBHOOK_URL")

print("OpenRouter key found:", "YES" if key else "NO — MISSING")
if key:
    print("  starts with:", key[:7])   # shows 'sk-or-' if correct, hides the rest
print("Discord webhook found:", "YES" if hook else "NO — MISSING")