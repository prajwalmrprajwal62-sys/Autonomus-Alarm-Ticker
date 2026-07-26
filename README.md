# RoutineBot — Phase 1

A Telegram bot that runs your morning routine automatically,
step by step, with an evening summary.

---

## One-time Setup (15 minutes)

### 1. Get a bot token
- Open Telegram → search `@BotFather`
- Send `/newbot` → follow prompts → copy the token it gives you

### 2. Set up the project
```bash
cd routine-bot
pip install -r requirements.txt
cp .env.example .env
```

### 3. Add your token to .env
Open `.env` and paste your token:
```
TELEGRAM_TOKEN=123456:ABCdef...
CHAT_ID=0          ← leave as 0 for now
```

### 4. First run — get your Chat ID
```bash
python bot.py
```
Open Telegram → find your bot → send `/start`
The bot replies with your Chat ID. Copy it.

### 5. Add Chat ID to .env, restart
```
CHAT_ID=123456789
```
```bash
python bot.py
```
Done. Bot is live.

---

## Daily Usage

| Command | What it does |
|---|---|
| `/setday normal` | Normal college day (full routine) |
| `/setday exam` | Exam day (short focused routine) |
| `/setday holiday` | Holiday (no routine, just a greeting) |
| `/done` | Finish current step early, move to next |
| `/notdone` | Skip current step (logged as missed) |
| `/report` | See today's completion summary |
| `/startmorning` | Test the routine right now |
| `/status` | Check day type and active state |

---

## How it works

**Every morning at 6:30 AM (IST)** → bot sends first step automatically.
Each step runs on a timer. When time's up → auto-moves to next step.
You can `/done` early or `/notdone` to skip.

**Every evening at 9:00 PM (IST)** → bot sends a short daily report.

---

## Change your schedule or steps

Open `bot.py` → edit the CONFIG section at the top:

```python
WAKE_HOUR   = 6      # change to your wake time
WAKE_MINUTE = 30
EVE_HOUR    = 21
EVE_MINUTE  = 0

NORMAL_STEPS = [
    {"name": "Think about your day 🧠", "minutes": 2},
    # add / remove / change steps here
]
```

---

## Keep it running (optional)

To keep the bot running in the background on your laptop:
```bash
nohup python bot.py &
```

To deploy free on Render.com later → see Phase 2 notes.

---

## Phase 2 ideas (only after this works for 2 weeks)
- Weather check + umbrella reminder during Pack Bag step
- DSA topic tracker with carry-forward
- Deploy to Render so it runs 24/7 without your laptop
