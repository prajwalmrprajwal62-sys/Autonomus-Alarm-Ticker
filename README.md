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


## UPDATED TO PHASE 2

# RoutineBot — Phase 2 (Turso edition)

Telegram bot for morning routine + daily study tasks with carry-forward.
Data lives in a free Turso cloud database — survives Render restarts.

---

## One-time setup

### 1. Telegram bot token
- Telegram → search `@BotFather` → `/newbot` → copy the token

### 2. Turso database (free)
- Go to turso.tech → sign up (GitHub login works)
- Create a new database from the dashboard (any name, e.g. `routine-bot`)
- Once created, find:
  - **Database URL** — looks like `libsql://routine-bot-yourname.turso.io`
  - **Auth token** — generate one from the database's "Create Token" option
- Copy both — you'll need them in step 4

### 3. Project setup
```bash
cd routine-bot
pip install -r requirements.txt
cp .env.example .env
```

### 4. Fill in `.env`
```
TELEGRAM_TOKEN=123456:ABCdef...
CHAT_ID=0                                    ← leave as 0 for now
TURSO_DATABASE_URL=libsql://routine-bot-yourname.turso.io
TURSO_AUTH_TOKEN=paste_the_long_token_here
```

### 5. First run — get your Chat ID
```bash
python bot.py
```
Send `/start` to your bot in Telegram → it replies with your Chat ID.
Paste that into `.env` as `CHAT_ID`, then restart:
```bash
python bot.py
```
Bot is live, and every write is now going to your cloud database.

---

## Daily commands

| Command | What it does |
|---|---|
| `/setday normal` | Normal day (full routine) |
| `/setday exam` | Exam day (short routine) |
| `/setday holiday` | Holiday (no routine) |
| `/done` / `/notdone` | Control the active routine step |
| `/tasks` | See today's study tasks |
| `/td 1 2` | Mark tasks 1, 2 done |
| `/tn 2` | Mark task 2 not done — carries to tomorrow |
| `/report` | Today's summary |
| `/testevening` | Fire the evening report right now (for testing) |
| `/resetday` | Wipe today's data, start clean |

---

## Why Turso

Render's free tier wipes local files on every restart/redeploy. Turso stores
your data in the cloud instead of a local `.db` file, so nothing is lost when
Render sleeps, restarts, or redeploys. Free tier covers this project many
times over — no cost.

## Deploying to Render (next step)

1. Push this project to GitHub (`.gitignore` already excludes `.env`)
2. On Render → New Web Service → connect your repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python bot.py`
5. Add all 4 values from your `.env` under Render's **Environment** tab
   (Render never sees your local `.env` file — you re-enter them there)
6. Deploy. Bot now runs 24/7, data safe in Turso regardless of restarts.