import httpx
import json
import time
import os
import logging
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)
logging.getLogger("httpx").setLevel(logging.WARNING)

VALID_CATEGORIES = [
    "Food", "Shopping", "Travel", "Transport",
    "Utilities", "Cash Withdrawal", "Entertainment", "Other"
]

MERCHANT_CATEGORY_HINTS = {
    "swiggy": "Food",
    "zomato": "Food",
    "flipkart": "Shopping",
    "amazon": "Shopping",
    "irctc": "Travel",
    "makemytrip": "Travel",
    "ola": "Transport",
    "jio recharge": "Utilities",
    "hdfc atm": "Cash Withdrawal",
    "bookmyshow": "Entertainment",
}


def fallback_category(transaction: dict) -> str:
    merchant = str(transaction.get("merchant") or "").lower()
    notes = str(transaction.get("notes") or "").lower()
    haystack = f"{merchant} {notes}"

    for hint, category in MERCHANT_CATEGORY_HINTS.items():
        if hint in haystack:
            return category
    return "Other"


def fallback_summary(stats: dict) -> dict:
    total_inr = float(stats.get("total_inr", 0) or 0)
    total_usd = float(stats.get("total_usd", 0) or 0)
    anomaly_count = int(stats.get("anomaly_count", 0) or 0)
    top_merchants = stats.get("top_merchants", []) or []

    if anomaly_count >= 5:
        risk_level = "high"
    elif anomaly_count > 0:
        risk_level = "medium"
    else:
        risk_level = "low"

    merchant_text = ", ".join(top_merchants) if top_merchants else "no dominant merchants"
    narrative = (
        f"Total spend was INR {total_inr:.2f} and USD {total_usd:.2f}. "
        f"The most frequent merchants were {merchant_text}. "
        f"{anomaly_count} transactions were flagged for review, giving this job a {risk_level} risk level."
    )

    return {
        "total_spend_inr": total_inr,
        "total_spend_usd": total_usd,
        "top_merchants": top_merchants,
        "anomaly_count": anomaly_count,
        "narrative": narrative,
        "risk_level": risk_level,
    }


def call_gemini(prompt: str, retries: int = 3) -> str | None:
    """Call Gemini API with exponential backoff retry."""
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY is not configured; skipping Gemini call.")
        return None

    for attempt in range(retries):
        try:
            response = httpx.post(
                GEMINI_URL,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            reason = f"HTTP {status}" if status else e.__class__.__name__
            print(f"Gemini attempt {attempt + 1} failed: {reason}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s, 4s
    return None


def classify_transactions(transactions: list[dict]) -> list[dict]:
    """Batch classify uncategorised transactions using LLM."""

    if not transactions:
        return []

    # Build batch prompt
    txn_list = "\n".join([
        f"- txn_id: {t['txn_id']}, merchant: {t['merchant']}, amount: {t['amount']}, notes: {t.get('notes', '')}"
        for t in transactions
    ])

    prompt = f"""You are a financial transaction classifier.
Classify each transaction into exactly one of these categories:
{', '.join(VALID_CATEGORIES)}

Transactions:
{txn_list}

Respond ONLY with a valid JSON array like this, no explanation:
[{{"txn_id": "...", "category": "..."}}]
"""

    result = call_gemini(prompt)

    if result is None:
        # Mark all as llm_failed
        for t in transactions:
            t['llm_category'] = fallback_category(t)
            t['llm_failed'] = True
        return transactions

    try:
        # Clean response and parse JSON
        clean = result.strip().replace('```json', '').replace('```', '').strip()
        classified = json.loads(clean)

        # Map results back
        category_map = {item['txn_id']: item['category'] for item in classified}
        for t in transactions:
            t['llm_category'] = category_map.get(t['txn_id'], 'Other')
            t['llm_raw_response'] = result
            t['llm_failed'] = False

    except Exception as e:
        print(f"Failed to parse LLM classification response: {e}")
        for t in transactions:
            t['llm_category'] = fallback_category(t)
            t['llm_raw_response'] = result
            t['llm_failed'] = True

    return transactions


def generate_narrative_summary(stats: dict) -> dict | None:
    """Generate a narrative summary of the transactions."""

    prompt = f"""You are a financial analyst. Based on these transaction statistics:

Total INR spend: {stats.get('total_inr', 0)}
Total USD spend: {stats.get('total_usd', 0)}
Top merchants: {stats.get('top_merchants', [])}
Anomaly count: {stats.get('anomaly_count', 0)}
Category breakdown: {stats.get('category_breakdown', {})}

Respond ONLY with a valid JSON object, no explanation:
{{
  "total_spend_inr": <number>,
  "total_spend_usd": <number>,
  "top_merchants": [<top 3 merchant names>],
  "anomaly_count": <number>,
  "narrative": "<2-3 sentence spending summary>",
  "risk_level": "<low|medium|high>"
}}
"""

    result = call_gemini(prompt)

    if result is None:
        return fallback_summary(stats)

    try:
        clean = result.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(clean)
    except Exception as e:
        print(f"Failed to parse narrative summary: {e}")
        return fallback_summary(stats)
