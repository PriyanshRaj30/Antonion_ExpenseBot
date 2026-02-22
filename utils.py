import os
from fastapi import FastAPI, Request
from sqlmodel import Session, select
from datetime import datetime, timedelta
import requests
from models import Transaction
from database import engine, create_db
from llm import categorize_expense, parse_summary_query
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import calendar


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set in .env")


def send_message(chat_id, text):
    requests.post(TELEGRAM_API, json={
        "chat_id": chat_id,
        "text": text
    })

def build_summary_reply(summary, title, unnecessary_only=False):
    lines = [f"📊 *{title} Summary*", f"🗓 {summary['start_date']} → {summary['end_date']}", ""]

    if not unnecessary_only:
        lines.append(f"💰 Income:   ₹{summary['income']:.0f}")
        lines.append(f"💸 Expenses: ₹{summary['expenses']:.0f}")
        net = summary['net']
        net_emoji = "✅" if net >= 0 else "🔴"
        lines.append(f"{net_emoji} Net:      ₹{net:.0f}")
        lines.append("")

    lines.append("📂 *Breakdown:*")
    for cat, amt in summary['breakdown'].items():
        lines.append(f"  • {cat}: ₹{amt:.0f}")

    if summary.get('top_category'):
        lines.append(f"\n🏆 Top category: {summary['top_category']}")
    if not unnecessary_only:
        lines.append(f"📈 Avg daily spend: ₹{summary['avg_daily']:.0f}")

    return "\n".join(lines)

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
