import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

response = client.chat.completions.create(
    model="deepseek/deepseek-r1",
    messages=[
        {"role": "user", "content": "Reply with exactly: connection working"}
    ],
)

print(response.choices[0].message.content)