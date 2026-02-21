import os
from fastapi import FastAPI, Request
from sqlmodel import Session, select
from datetime import datetime, timedelta
import requests
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
            is_unnecessary=data["is_unnecessary"]
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
    return any(char.isdigit() for char in text)


def get_summary(user_id, period='month', unnecessary_only=False, start_date=None, end_date=None):
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
        
        results = session.exec(statement).all()
        total = sum(tx.amount for tx in results)
        category_breakdown = {}
        for tx in results:
            category_breakdown[tx.category] = category_breakdown.get(tx.category, 0) + tx.amount
        
        # Add insights: average daily spend, top category
        days_in_period = (date_filter_end - date_filter_start).days
        avg_daily = total / days_in_period if days_in_period > 0 else 0
        top_category = max(category_breakdown, key=category_breakdown.get) if category_breakdown else None
        
        return {
            'total': total,
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
    print(f"text : {text}")
    chat_id = message["chat"]["id"]
    user_id = str(message["from"]["id"])

    if text == '/start':
        print("PRINTPRINT")
        reply = "Welcome! Track expenses by texting like '100 on food'. Ask summaries like 'last month expenses'. Use /help for more."
        send_message(chat_id, reply)
        return {"status": "start"}
    elif text == '/help':
        reply = "Commands:\n- /start: Welcome\n- /week: Last week summary\n...\nOr just chat naturally!"
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


    # EXPENSE ENTRY
    if is_expense_message(text):
        try:
            parsed = categorize_expense(text)
            tx = save_transaction(user_id, parsed)
            reply = (
                f"✅ ₹{tx.amount} added under {tx.category}\n"
                f"Marked as {'Unnecessary' if tx.is_unnecessary else 'Essential'}"
            )
            send_message(chat_id, reply)

        except Exception as e:
            print("Error predicting if it is a expense : ",e)
            send_message(chat_id, "❌ Could not understand expense. Try again.")
        return {"status": "expense recorded"}

    # QUERY SECTION
    text_lower = text.lower()
    print("THIS IS THE LOWER TEXT", text_lower)

    # if "last week" in text_lower:
    #     total, breakdown = get_summary(user_id, days=7)
    #     reply = f"📊 Last Week Total: ₹{total}\n"
    #     for cat, amt in breakdown.items():
    #         reply += f"- {cat}: ₹{amt}\n"
    #     send_message(chat_id, reply)
    #     return {"status": "summary sent"}

    # if "this month" in text_lower:
    #     total, breakdown = get_summary(user_id, days=30)
    #     reply = f"📊 This Month Total: ₹{total}\n"
    #     for cat, amt in breakdown.items():
    #         reply += f"- {cat}: ₹{amt}\n"
    #     send_message(chat_id, reply)
    #     return {"status": "summary sent"}

    # if "waste" in text_lower:
    #     total, breakdown = get_summary(user_id, days=30, unnecessary_only=True)
    #     reply = f"💸 Wasted This Month: ₹{total}\n"
    #     for cat, amt in breakdown.items():
    #         reply += f"- {cat}: ₹{amt}\n"
    #     send_message(chat_id, reply)
    #     return {"status": "waste summary"}


    try:
        parsed = parse_summary_query(text)
        if parsed.get("is_summary"):
            period_type = parsed.get("period")
            unnecessary_only = parsed.get("unnecessary_only", False)
            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")
            
            print(f"THIS IS THE PERIOD : {period_type}")
            
            if period_type == 'custom' and (start_date is None or end_date is None):
                raise ValueError("Missing dates for custom period")
            print("THIS WILL GET PRINT ")
            summary = get_summary(
                user_id, 
                period=period_type, 
                unnecessary_only=unnecessary_only, 
                start_date=start_date if period_type == 'custom' else None,
                end_date=end_date if period_type == 'custom' else None
            )
            print("THIS WILL NOT")
            
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
        print("ERROR HERE")
        print(e)

        send_message(chat_id, "❌ Could not generate summary. Try clearer phrasing like 'last month expenses' or check /help.")
        return {"status": "error"}

    # FALLBACK (after try-except)
    send_message(chat_id, "Send an expense or ask about last week / this month / waste.")
    return {"status": "default"}