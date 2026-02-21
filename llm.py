import json
from groq import Groq
import os
import re
from dotenv import load_dotenv
load_dotenv()


client = Groq(api_key=os.getenv("GROQ_KEY"))
  
if not client:
    raise ValueError("GROQ_API not set in .env")
def categorize_expense(message: str):
    prompt = f"""
    You are a financial categorization assistant./

    Return JSON only in this format:
    {{
    "amount": float,
    "category": "Food | Travel | Shopping | Bills | Investment | Entertainment | Health | Other",
    "description": string,
    "is_unnecessary": boolean
    }}

    Expense message: "{message}"
"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    try:
        content = response.choices[0].message.content.strip()
        content = re.sub(r"```json|```", "", content).strip()
        
    except Exception as e:
        print("Invalid LLM Output: ",e)
    return json.loads(content)




def parse_summary_query(message: str):
    prompt = f"""
    You are a query parser for an expense tracking bot.

    Analyze the user's message and determine if it's a request for a summary of expenses.
    - If yes, extract the period and filters.
    - Periods: 'week' (last full week), 'month' (last full month), 'this_month' (current month to date), 'custom' (with dates).
    - For custom, extract YYYY-MM-DD dates; assume 'from start to end' format if present.
    - Unnecessary only if words like 'waste', 'unnecessary', 'non-essential' are mentioned.

    Return JSON only in this format:
    {{
    "is_summary": boolean,
    "period": "this_week | last_week | this_month |last_month | custom",
    "unnecessary_only": boolean,
    "start_date": string (YYYY-MM-DD, null if not custom),
    "end_date": string (YYYY-MM-DD, null if not custom)
    }}

    If not a summary (e.g., expense entry or unrelated), return {{"is_summary": false}}.
    Strictly return json only

    Examples:
    - "Show me my expenses for last month" -> {{"is_summary": true, "period": "last_month", "unnecessary_only": false, "start_date": null, "end_date": null}}
    - "How much did I waste this week?" -> {{"is_summary": true, "period": "this_week", "unnecessary_only": true, "start_date": null, "end_date": null}}
    - "How much did I waste last week?" -> {{"is_summary": true, "period": "last_week", "unnecessary_only": true, "start_date": null, "end_date": null}}
    - "Summary of spends from 2024-01-01 to 2024-01-31" -> {{"is_summary": true, "period": "custom", "unnecessary_only": false, "start_date": "2024-01-01", "end_date": "2024-01-31"}}
    - "What were my unnecessary expenses last month" -> {{"is_summary": true, "period": "last_month", "unnecessary_only": true, "start_date": null, "end_date": null}}
    - "Spent 100 on food" -> {{"is_summary": false}}
    - "Hello" -> {{"is_summary": false}}

    User message: "{message}"
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",  # Or your preferred model
            messages=[{"role": "user", "content": prompt}],
            temperature=0  # Low temp for consistency
        )
        content = response.choices[0].message.content.strip()
        # print(f'THIS IS THE HERE1 {content}')
        content = re.sub(r"```json|```", "", content).strip()
        parsed = json.loads(content)
        print(f"THIS IS THE HERE2 {parsed}")
        # Validate and fallback
        if parsed.get("is_summary") and parsed.get("period") == "custom":
            if not (parsed.get("start_date") and parsed.get("end_date")):
                raise ValueError("Missing dates for custom")
        
        return parsed
    except Exception as e:
        print(f"Query parse error: {e}")
        return {"is_summary": False}