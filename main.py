import os
from fastapi import FastAPI, Request
from sqlmodel import Session, select
from datetime import datetime, timedelta
import requests
import re
from models import Transaction
from database import engine, create_db
from llm import categorize_expense, parse_summary_query
from utils import send_message, build_summary_reply, get_summary
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import calendar


load_dotenv()

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set in .env")


create_db()


# ----------------------
# Helper: Send Telegram Reply
# ----------------------




# ----------------------
# Save Transaction
# ----------------------
def save_transaction(user_id, data):
    with Session(engine) as session:
        tx = Transaction(
            user_id=user_id,
            amount=data["amount"],
            category=data["category"],
            description=data["description"],
            is_unnecessary=data["is_unnecessary"],
            tx_type=data.get("tx_type", "expense")  
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return tx


def delete_last_transaction(user_id):
    with Session(engine) as session:
        statement = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.date.desc())
        )

        last_tx = session.exec(statement).first()

        if not last_tx:
            return None

        session.delete(last_tx)
        session.commit()

        return last_tx
# ----------------------
# Detect if message is expense
# ----------------------
def is_expense_message(text):
    text_lower = text.lower()
    
    # Detect digits (e.g., "20", "100.50")
    if re.search(r'\d+(\.\d+)?', text):
        return True
    
    # Detect spelled-out numbers (basic list; expand as needed)
    number_words = [
        'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
        'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen',
        'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety',
        'hundred', 'thousand', 'million', 'billion'
    ]
    # Check for number words, allowing compounds like "twenty five"
    words = re.findall(r'\b\w+\b', text_lower)
    if any(word in number_words for word in words):
        return True
    
    # Detect currency symbols or words (e.g., "₹", "rupees", "$")
    currency_indicators = ['₹', 'rs', 'rupee', 'rupees', 'dollar', 'dollars', '$', 'euro', 'euros', '£', 'pound', 'pounds']
    if any(ind in text_lower for ind in currency_indicators):
        return True
    
    # Exclude if it looks like a summary query (to avoid false positives)
    summary_keywords = ['summary', 'report', 'show', 'waste', 'month', 'week', 'expenses', 'spent last']
    if any(keyword in text_lower for keyword in summary_keywords):
        return False
    
    return False


def get_summary(user_id, period='month', unnecessary_only=False, start_date=None, end_date=None, tx_type=None):
    """Fetch expense summary for a period."""
    now = datetime.utcnow()
    
    if start_date and end_date:
        # Custom range
        date_filter_start = datetime.fromisoformat(start_date)
        date_filter_end = datetime.fromisoformat(end_date) + timedelta(days=1)  # Include end day
    
    elif period == 'last_week':
        # Last full week: Monday to Sunday
        last_monday = now - timedelta(days=now.weekday())
        date_filter_start = last_monday - timedelta(days=7)
        date_filter_end = last_monday
    elif period == 'this_week':
        # This week to date: Current Monday to now
        current_monday = now - timedelta(days=now.weekday())
        date_filter_start = current_monday
        date_filter_end = now + timedelta(days=1)
    elif period == 'last_month':
        # Last full month
        first_of_month = now.replace(day=1)
        date_filter_start = first_of_month - relativedelta(months=1)  # Last month
        _, last_day = calendar.monthrange(date_filter_start.year, date_filter_start.month)
        date_filter_end = date_filter_start.replace(day=last_day) + timedelta(days=1)
    elif period == 'this_month':
        # This month to date
        date_filter_start = now.replace(day=1)
        date_filter_end = now + timedelta(days=1)
    else:
        raise ValueError("Invalid period")

    with Session(engine) as session:
        statement = select(Transaction).where(Transaction.user_id == user_id)
        statement = statement.where(Transaction.date >= date_filter_start)
        statement = statement.where(Transaction.date < date_filter_end)

        if unnecessary_only:
            statement = statement.where(Transaction.is_unnecessary == True)
        if tx_type:
            statement = statement.where(Transaction.tx_type == tx_type)  # ← filter

        results = session.exec(statement).all()

        expenses = sum(tx.amount for tx in results if tx.tx_type == "expense")
        income   = sum(tx.amount for tx in results if tx.tx_type == "income")
        total    = sum(tx.amount for tx in results)

        category_breakdown = {}
        for tx in results:
            category_breakdown[tx.category] = category_breakdown.get(tx.category, 0) + tx.amount

        days_in_period = (date_filter_end - date_filter_start).days
        avg_daily = expenses / days_in_period if days_in_period > 0 else 0
        top_category = max(
            (k for k in category_breakdown),
            key=category_breakdown.get
        ) if category_breakdown else None

        return {
            'total': total,
            'expenses': expenses,       
            'income': income,           
            'net': income - expenses,   
            'breakdown': category_breakdown,
            'avg_daily': avg_daily,
            'top_category': top_category,
            'start_date': date_filter_start.date(),
            'end_date': (date_filter_end - timedelta(days=1)).date()
        }

# ----------------------
# Telegram Webhook
# ----------------------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    message = data.get("message")
    if not message:
        return {"status": "ignored"}

    text = message.get("text", "")
    chat_id = message["chat"]["id"]
    user_id = str(message["from"]["id"])

    if text == '/start':
        reply = (
        "Hey 👋\n\n"
        "Just send your expenses like:\n"
        "100 on food\n"
        "250 petrol\n\n"
        "Or income like:\n"
        "5000 salary\n"
        "2000 freelance\n\n"
        "You can also ask things like:\n"
        "last month expenses\n"
        "this year income\n\n"
        "Type /help if you get stuck."
        )

        send_message(chat_id, reply)
        return {"status": "start"}
    elif text == '/help':
        reply = (
            "🤖 *Money Tracker Bot Help*\n\n"

            "💰 *Add Income*\n"
            "Just type naturally:\n"
            "• 5000 salary\n"
            "• Got 12000 freelance payment\n"
            "• Received 2000 gift\n\n"

            "💸 *Add Expense*\n"
            "Examples:\n"
            "• 200 on food\n"
            "• Spent 150 for petrol\n"
            "• Paid 500 electricity bill\n\n"

            "📊 *View Summaries*\n"
            "• Last week expenses\n"
            "• This month summary\n"
            "• This year income\n"
            "• Last year expenses\n"
            "• From 2026-01-01 to 2026-01-31\n\n"

            "💸 *Unnecessary Spending*\n"
            "• How much did I waste this month?\n"
            "• Unnecessary expenses last year\n\n"

            "↩️ *Other Commands*\n"
            "• /start – Welcome message\n"
            "• /undo – Delete last transaction\n"
            "• /help – Show this help message\n\n"

            "✨ Tip: You can just chat naturally. I understand context!"
        )

        send_message(chat_id, reply)
        return {"status": "help"}
        
    elif text == '/undo':
        last_tx = delete_last_transaction(user_id)

        if not last_tx:
            send_message(chat_id, "⚠️ No transactions to undo.")
            return {"status": "nothing to undo"}

        reply = (
            f"↩️ Undone: ₹{last_tx.amount} "
            f"from {last_tx.category}"
        )

        send_message(chat_id, reply)
        return {"status": "undone"}


    # EXPENSE / INCOME ENTRY
    if is_expense_message(text):
        try:
            parsed = categorize_expense(text)
            tx = save_transaction(user_id, parsed)

            if tx.tx_type == "income":
                reply = (
                    f"💰 ₹{tx.amount} income recorded under {tx.category}\n"
                    f"📝 {tx.description}"
                )
            else:
                reply = (
                    f"✅ ₹{tx.amount} added under {tx.category}\n"
                    f"Marked as {'Unnecessary' if tx.is_unnecessary else 'Essential'}"
                )
            send_message(chat_id, reply)

        except Exception as e:
            send_message(chat_id, "❌ Could not understand. Try again.")
        return {"status": "recorded"}

    # QUERY SECTION
    text_lower = text.lower()


    try:
        parsed = parse_summary_query(text)
        if parsed.get("is_summary"):
            period_type = parsed.get("period")
            unnecessary_only = parsed.get("unnecessary_only", False)
            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")
            
            if period_type == 'custom' and (start_date is None or end_date is None):
                raise ValueError("Missing dates for custom period")
            summary = get_summary(
                user_id, 
                period=period_type, 
                unnecessary_only=unnecessary_only, 
                start_date=start_date if period_type == 'custom' else None,
                end_date=end_date if period_type == 'custom' else None,
                tx_type=parsed.get("tx_type") 
            )
            
            title_base = {
                'last_week': 'Last Week',
                'last_month': 'Last Month',
                'this_month': 'This Month',
                'custom': f'Custom ({start_date} to {end_date})'
            }.get(period_type, 'Summary')
            
            title = f"{title_base} {'Waste' if unnecessary_only else ''}".strip()
            
            reply = build_summary_reply(summary, title, unnecessary_only)
            
            send_message(chat_id, reply)
            return {"status": "summary sent"}
    except Exception as e:
        send_message(chat_id, "❌ Could not generate summary. Try clearer phrasing like 'last month expenses' or check /help.")
        return {"status": "error"}

    # FALLBACK (after try-except)
    send_message(
        chat_id,
        "🤔 I didn't understand that.\n\n"
        "💰 Add income like:\n"
        "• 5000 salary\n"
        "• Received 2000\n\n"
        "💸 Add expense like:\n"
        "• 200 on food\n"
        "• Paid 150 for petrol\n\n"
        "📊 Ask for summary like:\n"
        "• Last week expenses\n"
        "• This month summary\n"
        "• This year income\n"
        "• From 2026-01-01 to 2026-01-31\n\n"
        "Type /help for full guide."
    )
    return {"status": "default"}