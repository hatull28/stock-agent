import os
import requests
from dotenv import load_dotenv

load_dotenv()

webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

message = {"content": "🚀 Stock Agent connected! Test message working."}

response = requests.post(webhook_url, json=message)

if response.status_code == 204:
    print("SUCCESS - check your Discord channel!")
else:
    print(f"Something went wrong: {response.status_code}")
    print(response.text)