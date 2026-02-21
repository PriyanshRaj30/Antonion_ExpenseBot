# 💸 Money Tracker — AI-Powered Expense Telegram Bot

A smart personal finance bot that lives in your Telegram. Just send a message like _"spent 250 on lunch"_ and it automatically categorizes, stores, and lets you query your expenses — all in natural language, powered by an LLM.

---

## ✨ Features

- **Natural language expense logging** — No forms, just chat. E.g. `"200 on Uber"`, `"bought groceries for 500"`
- **AI categorization** — Groq LLM (Llama 4) classifies each expense into: `Food`, `Travel`, `Shopping`, `Bills`, `Investment`, `Entertainment`, `Health`, or `Other`
- **Unnecessary spend detection** — The LLM flags expenses as essential or unnecessary
- **Flexible summaries** — Query by:
  - This week / Last week
  - This month / Last month
  - Custom date range (e.g. `"expenses from 2024-03-01 to 2024-03-15"`)
  - Waste/unnecessary only (e.g. `"how much did I waste last month?"`)
- **Per-user data isolation** — Each Telegram user's data is stored separately
- **Rich summary replies** — Total, average daily spend, top category, and full category breakdown

---

## 🏗️ Architecture

```
Telegram User
     │
     ▼ (message)
Telegram Bot API
     │
     ▼ (POST /webhook)
FastAPI App (main.py)
     │
     ├──► LLM (llm.py)  ◄── Groq API (Llama 4 Scout)
     │         ├── categorize_expense()
     │         └── parse_summary_query()
     │
     ├──► Database (database.py + models.py)
     │         └── SQLite via SQLModel
     │
     └──► Telegram Reply (utils.py)
               └── send_message()
```

---

## 📁 Project Structure

| File | Description |
|------|-------------|
| `main.py` | FastAPI app, webhook handler, core routing logic |
| `llm.py` | Groq LLM calls — expense categorization & query parsing |
| `utils.py` | Telegram messaging helper & summary response builder |
| `models.py` | `Transaction` SQLModel schema |
| `database.py` | SQLite engine setup and DB initialization |
| `summary_parser.py` | Additional summary parsing utilities |
| `requirement.txt` | Python dependencies |
| `expenses.db` | SQLite database (auto-created on first run) |

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+
- A [Telegram Bot Token](https://core.telegram.org/bots/tutorial) (via BotFather)
- A [Groq API Key](https://console.groq.com/)
- [ngrok](https://ngrok.com/) (for local development / webhook tunneling)

### 2. Install Dependencies

```bash
pip install -r requirement.txt
```

> **Tip:** Use a virtual environment: `python -m venv .venv && source .venv/bin/activate`

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
TELEGRAM_TOKEN=your_telegram_bot_token_here
GROQ_KEY=your_groq_api_key_here
```

### 4. Run the Server

```bash
uvicorn main:app --reload
```

### 5. Expose Locally via ngrok

```bash
ngrok http 8000
```

Copy the generated `https://` URL.

### 6. Register Telegram Webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
     -d "url=https://<your-ngrok-url>/webhook"
```

---

## 💬 Usage Examples

| Message | Action |
|---------|--------|
| `"spent 150 on coffee"` | Logs ₹150 under Food, flags as unnecessary |
| `"paid electricity bill 1200"` | Logs ₹1200 under Bills, marks as essential |
| `"show last month expenses"` | Returns full summary for last calendar month |
| `"how much did I waste this week?"` | Returns only unnecessary spends this week |
| `"expenses from 2024-03-01 to 2024-03-15"` | Custom date range summary |
| `/start` | Welcome message |
| `/help` | Lists available commands |

---

## 📊 Expense Categories

| Category | Examples |
|----------|---------|
| 🍕 Food | Restaurants, groceries, coffee |
| 🚗 Travel | Uber, fuel, flights |
| 🛍️ Shopping | Clothes, gadgets, Amazon |
| 📄 Bills | Electricity, rent, subscriptions |
| 📈 Investment | Stocks, SIP, mutual funds |
| 🎬 Entertainment | Movies, streaming, games |
| 🏥 Health | Medicine, gym, doctor |
| 📦 Other | Everything else |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ORM / DB | [SQLModel](https://sqlmodel.tiangolo.com/) + SQLite |
| LLM | [Groq](https://groq.com/) — `meta-llama/llama-4-scout-17b-16e-instruct` |
| Bot Platform | [Telegram Bot API](https://core.telegram.org/bots/api) |
| Tunneling (dev) | [ngrok](https://ngrok.com/) |

---

## 🔮 Roadmap

- [ ] Monthly budget alerts
- [ ] Export to CSV / Google Sheets
- [ ] Multi-currency support
- [ ] Inline charts / spending graphs
- [ ] Recurring expense reminders
