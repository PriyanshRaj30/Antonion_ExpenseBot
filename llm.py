import json
from groq import Groq
import os
import re
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime


client = Groq(api_key=os.getenv("GROQ_KEY"))
  
if not client:
    raise ValueError("GROQ_API not set in .env")


def categorize_expense(text: str):
    prompt = f"""
    You are a financial assistant. Analyze this message and determine if it's an income or expense.

    Message: "{text}"

    Income examples: "5000 salary", "1200 freelance", "got paid 3000", "received 500"
    Expense examples: "100 on food", "paid 50 for coffee", "spent 200 on groceries"

    Return ONLY valid JSON:
    {{
    "amount": <positive number>,
    "category": "<category>",
    "description": "<short description>",
    "is_unnecessary": <true/false, always false for income>,
    "tx_type": "<income or expense>"
    }}

    For income, use categories like: Salary, Freelance, Business, Investment, Gift, Other Income.
    For expense, use categories like: Food, Transport, Shopping, Bills, Entertainment, Health, Other.
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
    
    decoder = json.JSONDecoder()

    content = content.strip()

    start = content.find('{')
    if start != -1:
        content, index = decoder.raw_decode(content[start:])
        # print(content)
    return content




def parse_summary_query(message: str):
    now = datetime.utcnow()
    current_date = now.date().isoformat()

    prompt = f"""
        You are a query parser for an expense and income tracking bot.

        Current date: {current_date}

        Analyze the user's message and determine if it's a request for a summary.
        If yes, extract the period, filters, and transaction type.

        Rules:
        - Periods: 'this_week', 'last_week', 'this_month', 'last_month', 'custom'
        - For custom, extract YYYY-MM-DD dates from the message
        - unnecessary_only: true if words like 'waste', 'unnecessary', 'non-essential' appear
        - tx_type: 
            - "income"  → if user asks about income, salary, earnings, received, credited
            - "expense" → if user asks about expenses, spending, spent, paid, costs
            - null      → if user asks for full summary (both income and expenses)

        Return JSON only in this exact format:
        {{
        "is_summary": boolean,
        "period": "this_week | last_week | this_month | last_month | custom",
        "unnecessary_only": boolean,
        "tx_type": "income | expense | null",
        "start_date": "YYYY-MM-DD or null",
        "end_date": "YYYY-MM-DD or null"
        }}

        If not a summary request (e.g., expense entry, income entry, or unrelated), return {{"is_summary": false}}.
        Strictly return JSON only. No explanation.

        Examples:
        - "Show me last month expenses"         → {{"is_summary": true, "period": "last_month", "unnecessary_only": false, "tx_type": "expense", "start_date": null, "end_date": null}}
        - "How much did I waste this week?"     → {{"is_summary": true, "period": "this_week",  "unnecessary_only": true,  "tx_type": "expense", "start_date": null, "end_date": null}}
        - "Last week income"                    → {{"is_summary": true, "period": "last_week",  "unnecessary_only": false, "tx_type": "income",  "start_date": null, "end_date": null}}
        - "This month salary"                   → {{"is_summary": true, "period": "this_month", "unnecessary_only": false, "tx_type": "income",  "start_date": null, "end_date": null}}
        - "This month summary"                  → {{"is_summary": true, "period": "this_month", "unnecessary_only": false, "tx_type": null,      "start_date": null, "end_date": null}}
        - "From 2024-01-01 to 2024-01-31"      → {{"is_summary": true, "period": "custom",     "unnecessary_only": false, "tx_type": null,      "start_date": "2024-01-01", "end_date": "2024-01-31"}}
        - "Unnecessary expenses last month"    → {{"is_summary": true, "period": "last_month", "unnecessary_only": true,  "tx_type": "expense", "start_date": null, "end_date": null}}
        - "5000 salary"                         → {{"is_summary": false}}
        - "Spent 100 on food"                   → {{"is_summary": false}}
        - "Hello"                               → {{"is_summary": false}}

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
        # print(f"THIS IS THE HERE2 {parsed}")
        # Validate and fallback
        print("THIS IS THE TEST :", parsed)
        if parsed.get("is_summary") and parsed.get("period") == "custom":
            if not (parsed.get("start_date") and parsed.get("end_date")):
                raise ValueError("Missing dates for custom")
        
        return parsed
    except Exception as e:
        print(f"Query parse error: {e}")
        return {"is_summary": False}