"""Turn a day of analytics into a plain-English executive summary via an LLM.

Uses Groq (fast/free tier) if GROQ_API_KEY is set, else OpenAI, else prints raw
numbers. Both use the OpenAI-compatible chat completions API via httpx.
"""

import json
import os
from datetime import UTC, datetime

import httpx

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")


def fetch_summary() -> dict:
    email = os.getenv("FIRST_ADMIN_EMAIL", "admin@retail.local")
    password = os.getenv("FIRST_ADMIN_PASSWORD", "admin12345")
    token = httpx.post(
        f"{BACKEND}/api/v1/auth/login", data={"username": email, "password": password}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    return {
        "date": datetime.now(UTC).date().isoformat(),
        "overview": httpx.get(f"{BACKEND}/api/v1/analytics/overview", headers=h).json(),
        "peak_hours": httpx.get(f"{BACKEND}/api/v1/analytics/peak-hours", headers=h).json(),
        "dwell": httpx.get(f"{BACKEND}/api/v1/analytics/dwell", headers=h).json(),
    }


def narrate(summary: dict) -> str:
    groq, openai = os.getenv("GROQ_API_KEY"), os.getenv("OPENAI_API_KEY")
    if groq:
        url, key = "https://api.groq.com/openai/v1/chat/completions", groq
        model = "llama-3.3-70b-versatile"
    elif openai:
        url, key, model = "https://api.openai.com/v1/chat/completions", openai, "gpt-4o-mini"
    else:
        return "No LLM key set. Raw summary:\n" + json.dumps(summary, indent=2)
    resp = httpx.post(
        url,
        timeout=60,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a retail operations analyst. Write a crisp daily "
                    "briefing (<=150 words) from store CV analytics: traffic, "
                    "dwell, queues, alerts, and one actionable recommendation.",
                },
                {"role": "user", "content": json.dumps(summary)},
            ],
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


if __name__ == "__main__":
    print(narrate(fetch_summary()))
