"""
RoutineBot — Phase 2 (Turso edition)
Morning routine + daily study task tracking with carry-forward.

Storage: Turso (cloud-hosted libSQL, SQLite-compatible).
Data now lives in the cloud, not a local file — Render restarts/
redeploys no longer wipe your history. Same code runs locally and
on Render; only the .env values differ.
"""

import logging
import os
from datetime import time, date, datetime, timedelta
from zoneinfo import ZoneInfo

import libsql
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

# ─────────────────────────────────────────────────────────────
# CONFIG  ← only section you ever edit
# ─────────────────────────────────────────────────────────────
TIMEZONE    = ZoneInfo("Asia/Kolkata")

WAKE_HOUR   = 9      # 9 AM for your break (change back to 6 for college)
WAKE_MINUTE = 0
AFT_HOUR    = 14     # 2 PM afternoon check-in
AFT_MINUTE  = 0
EVE_HOUR    = 21     # 9 PM evening report
EVE_MINUTE  = 0

NORMAL_STEPS = [
    {"name": "Think about your day 🧠",  "minutes": 2},
    {"name": "Exercise 💪",              "minutes": 30},
    {"name": "Fresh up + breakfast 🍳",  "minutes": 10},
]

EXAM_STEPS = [
    {"name": "Think about today's exam 🧠", "minutes": 3},
    {"name": "Quick last-minute review 📖", "minutes": 10},
]

DAILY_STUDY_TASKS = [
    {"name": "DSA Practice 📊",          "minutes": 90},
    {"name": "Agentic AI Framework 🤖",  "minutes": 120},
    {"name": "GenAI Course 🧠",          "minutes": 150},
    {"name": "Evening Exercise 🏃",      "minutes": 20},
]
# ─────────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s  %(levelname)s  %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN       = os.getenv("TELEGRAM_TOKEN")
CHAT_ID     = int(os.getenv("CHAT_ID", "0"))
TURSO_URL   = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")


# ──────────────────────────────────────────────────────
# DATABASE (Turso — one persistent connection for the bot's lifetime)
# ──────────────────────────────────────────────────────
_conn = None


def get_conn():
    """Lazily open (and reuse) the connection to your Turso database."""
    global _conn
    if _conn is None:
        _conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    return _conn


def init_db() -> None:
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            date      TEXT NOT NULL,
            step_name TEXT NOT NULL,
            status    TEXT NOT NULL,
            logged_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date          TEXT NOT NULL,
            task_name     TEXT NOT NULL,
            duration_mins INTEGER NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            original_date TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()


def set_config(key: str, value: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO bot_config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def get_config(key: str, default: str) -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM bot_config WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def log_step(step_name: str, status: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO daily_log (date, step_name, status, logged_at) VALUES (?,?,?,?)",
        (str(date.today()), step_name, status, datetime.now().strftime("%H:%M")),
    )
    conn.commit()


def get_today_log() -> list:
    conn = get_conn()
    return conn.execute(
        "SELECT step_name, status FROM daily_log WHERE date=?",
        (str(date.today()),),
    ).fetchall()


def init_tasks_for_today() -> None:
    today = str(date.today())
    conn = get_conn()
    existing = conn.execute(
        "SELECT COUNT(*) FROM study_tasks WHERE date=?", (today,)
    ).fetchone()[0]
    if existing == 0:
        for task in DAILY_STUDY_TASKS:
            conn.execute(
                "INSERT INTO study_tasks (date, task_name, duration_mins, status, original_date) "
                "VALUES (?,?,?,?,?)",
                (today, task["name"], task["minutes"], "pending", today),
            )
        conn.commit()


def get_today_tasks() -> list:
    conn = get_conn()
    return conn.execute(
        "SELECT id, task_name, duration_mins, status FROM study_tasks WHERE date=? ORDER BY id",
        (str(date.today()),),
    ).fetchall()


def update_task_status(task_id: int, status: str) -> None:
    conn = get_conn()
    conn.execute("UPDATE study_tasks SET status=? WHERE id=?", (status, task_id))
    conn.commit()


def carry_forward_pending() -> int:
    today    = str(date.today())
    tomorrow = str(date.today() + timedelta(days=1))
    carried  = 0
    conn = get_conn()

    pending = conn.execute(
        "SELECT task_name, duration_mins, original_date FROM study_tasks "
        "WHERE date=? AND status IN ('pending', 'not_done')",
        (today,),
    ).fetchall()

    for task_name, duration_mins, original_date in pending:
        already = conn.execute(
            "SELECT COUNT(*) FROM study_tasks WHERE date=? AND task_name=?",
            (tomorrow, task_name),
        ).fetchone()[0]
        if not already:
            conn.execute(
                "INSERT INTO study_tasks (date, task_name, duration_mins, status, original_date) "
                "VALUES (?,?,?,?,?)",
                (tomorrow, task_name, duration_mins, "pending", original_date),
            )
            carried += 1

    conn.commit()
    return carried


def reset_today() -> None:
    """Wipe today's log + tasks so you can re-test cleanly."""
    today = str(date.today())
    conn = get_conn()
    conn.execute("DELETE FROM daily_log WHERE date=?", (today,))
    conn.execute("DELETE FROM study_tasks WHERE date=?", (today,))
    conn.commit()


# ──────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────
async def send_daily_brief(bot) -> None:
    init_tasks_for_today()
    tasks = get_today_tasks()
    total_mins = sum(t[2] for t in tasks)
    lines = [f"📋 *Today's Study Plan*\n", f"Total focus time: {total_mins // 60}h {total_mins % 60}min\n"]
    for i, (tid, name, duration, status) in enumerate(tasks, 1):
        lines.append(f"{i}. {name} — {duration}min")
    lines.append("\n✅ /td 1 2  — mark tasks done")
    lines.append("❌ /tn 2    — mark not done (carries to tomorrow)")
    lines.append("📋 /tasks   — see list anytime")
    await bot.send_message(chat_id=CHAT_ID, text="\n".join(lines), parse_mode="Markdown")


def _kill_jobs(context: ContextTypes.DEFAULT_TYPE, name: str) -> None:
    for job in context.application.job_queue.get_jobs_by_name(name):
        job.schedule_removal()


def _advance(context: ContextTypes.DEFAULT_TYPE, status: str) -> bool:
    if not context.bot_data.get("routine_active"):
        return False
    idx   = context.bot_data.get("current_idx", 0)
    steps = context.bot_data.get("current_steps", [])
    if idx < len(steps):
        log_step(steps[idx]["name"], status)
    _kill_jobs(context, "step_timeout")
    context.application.job_queue.run_once(send_step, when=2, data={"idx": idx + 1, "steps": steps})
    return True


# ──────────────────────────────────────────────────────
# STEP ENGINE
# ──────────────────────────────────────────────────────
async def send_step(context: ContextTypes.DEFAULT_TYPE) -> None:
    idx: int    = context.job.data["idx"]
    steps: list = context.job.data["steps"]

    if idx >= len(steps):
        context.bot_data["routine_active"] = False
        await context.bot.send_message(
            chat_id=CHAT_ID, text="🎯 *Morning routine done!* Here's your day...", parse_mode="Markdown"
        )
        await send_daily_brief(context.bot)
        return

    step = steps[idx]
    context.bot_data.update(routine_active=True, current_idx=idx, current_steps=steps)

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"⏱ *Step {idx+1}/{len(steps)}: {step['name']}*\n⏳ {step['minutes']} min\n\n/done — finished early     /notdone — skip",
        parse_mode="Markdown",
    )

    _kill_jobs(context, "step_timeout")
    context.application.job_queue.run_once(
        step_timeout, when=step["minutes"] * 60, name="step_timeout", data={"idx": idx, "steps": steps}
    )


async def step_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    idx   = context.job.data["idx"]
    steps = context.job.data["steps"]
    log_step(steps[idx]["name"], "done")
    await context.bot.send_message(
        chat_id=CHAT_ID, text=f"⏰ Time's up — *{steps[idx]['name']}* complete! Moving on...", parse_mode="Markdown"
    )
    context.application.job_queue.run_once(send_step, when=3, data={"idx": idx + 1, "steps": steps})


# ──────────────────────────────────────────────────────
# SCHEDULED / TRIGGERABLE LOGIC
# ──────────────────────────────────────────────────────
async def morning_trigger(context: ContextTypes.DEFAULT_TYPE) -> None:
    day_type = get_config("day_type", "normal")

    if day_type == "holiday":
        await context.bot.send_message(chat_id=CHAT_ID, text="🎉 Good morning! Holiday today — no routine. Enjoy! 😊")
        return

    greet = {
        "normal": "🌅 Good morning, Prajwal! Let's start the day.",
        "exam":   "✏️ Good morning! Exam day — short focused routine first.",
    }[day_type]

    await context.bot.send_message(chat_id=CHAT_ID, text=greet)
    steps = EXAM_STEPS if day_type == "exam" else NORMAL_STEPS
    context.application.job_queue.run_once(send_step, when=5, data={"idx": 0, "steps": steps})


async def afternoon_checkin(context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = get_today_tasks()
    if not tasks:
        return

    incomplete = [(i, t) for i, t in enumerate(tasks, 1) if t[3] in ("pending", "not_done")]
    done       = [t for t in tasks if t[3] == "done"]

    if not incomplete:
        await context.bot.send_message(
            chat_id=CHAT_ID, text="☀️ *Afternoon check-in*\n\n✅ All tasks done already! Solid work.", parse_mode="Markdown"
        )
        return

    lines = [f"☀️ *Afternoon Check-in*\n", f"Done: {len(done)}/{len(tasks)}\n", "Still pending:"]
    for num, (tid, name, duration, status) in incomplete:
        marker = " (marked not-done)" if status == "not_done" else ""
        lines.append(f"  {num}. {name} ({duration}min){marker}")
    lines.append("\n/td 1 2 — mark done     /tn 2 — carry tomorrow")

    await context.bot.send_message(chat_id=CHAT_ID, text="\n".join(lines), parse_mode="Markdown")


async def evening_report_trigger(context: ContextTypes.DEFAULT_TYPE) -> None:
    logs  = get_today_log()
    tasks = get_today_tasks()
    lines = [f"🌙 *Evening Report — {date.today().strftime('%B %d')}*\n"]

    if logs:
        done_r = sum(1 for _, s in logs if s == "done")
        lines.append(f"*Morning Routine ({int(done_r/len(logs)*100)}%)*")
        for name, status in logs:
            lines.append(f"{'✅' if status == 'done' else '❌'} {name}")
    else:
        lines.append("*Morning Routine* — no data today")

    lines.append("")

    if tasks:
        done_t = sum(1 for t in tasks if t[3] == "done")
        lines.append(f"*Study Tasks ({int(done_t/len(tasks)*100)}%)*")
        for _, name, duration, status in tasks:
            icon = "✅" if status == "done" else "❌" if status == "not_done" else "⬜"
            lines.append(f"{icon} {name}")
        carried = carry_forward_pending()
        if carried:
            lines.append(f"\n↩️ {carried} task(s) carried to tomorrow.")
    else:
        lines.append("*Study Tasks* — no data today")

    all_routine_done = bool(logs) and all(s == "done" for _, s in logs)
    all_tasks_done   = bool(tasks) and all(t[3] == "done" for t in tasks)
    any_task_done    = bool(tasks) and any(t[3] == "done" for t in tasks)
    lines.append(
        "\n🔥 Perfect day!"           if (all_routine_done and all_tasks_done) else
        "\n💪 Good progress today."   if any_task_done else
        "\n⚡ Rough one. Reset tomorrow — one day at a time."
    )
    lines.append("_/setday to update tomorrow's type._")

    await context.bot.send_message(chat_id=CHAT_ID, text="\n".join(lines), parse_mode="Markdown")


# ──────────────────────────────────────────────────────
# COMMAND HANDLERS
# ──────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"👋 *Routine Bot — Phase 2 (Turso edition)*\n\n"
        f"Your Chat ID: `{update.effective_chat.id}`\n\n"
        f"*Routine:*\n`/setday normal|exam|holiday`\n`/done` `/notdone`\n`/startmorning` — test now\n\n"
        f"*Study Tasks:*\n`/tasks` `/td 1 2` `/tn 2`\n\n"
        f"*Reports:*\n`/report` `/status`\n\n"
        f"*Testing tools:*\n`/testevening` — fire evening report right now\n`/resetday` — wipe today's data, start clean",
        parse_mode="Markdown",
    )


async def cmd_setday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    valid = ("normal", "exam", "holiday")
    arg   = (context.args or [""])[0].lower()
    if arg not in valid:
        await update.message.reply_text("Usage: /setday normal|exam|holiday")
        return
    set_config("day_type", arg)
    emoji = {"normal": "📚", "exam": "✏️", "holiday": "🎉"}[arg]
    await update.message.reply_text(f"{emoji} Day type → *{arg.upper()}* (saved to cloud DB)", parse_mode="Markdown")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _advance(context, "done"):
        await update.message.reply_text("✅ Done! Moving to next step.")
    else:
        await update.message.reply_text("No active routine right now.")


async def cmd_notdone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _advance(context, "not_done"):
        await update.message.reply_text("❌ Logged as missed. Moving on.")
    else:
        await update.message.reply_text("No active routine right now.")


async def cmd_startmorning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await morning_trigger(context)


async def cmd_testevening(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await evening_report_trigger(context)


async def cmd_resetday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reset_today()
    context.bot_data["routine_active"] = False
    await update.message.reply_text("🧹 Today's data wiped. Run /startmorning to test fresh.")


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    init_tasks_for_today()
    tasks      = get_today_tasks()
    total_mins = sum(t[2] for t in tasks)
    lines      = [f"📋 *Today's Study Tasks*\n"]
    for i, (tid, name, duration, status) in enumerate(tasks, 1):
        icon = "✅" if status == "done" else "❌" if status == "not_done" else "⬜"
        lines.append(f"{icon} {i}. {name} ({duration}min)")
    lines.append(f"\n⏱ Total: {total_mins // 60}h {total_mins % 60}min")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_td(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = get_today_tasks()
    if not tasks:
        await update.message.reply_text("No tasks yet. Run /startmorning first.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /td 1 2 3")
        return
    marked = []
    for arg in context.args:
        try:
            num = int(arg)
            if 1 <= num <= len(tasks):
                update_task_status(tasks[num - 1][0], "done")
                marked.append(tasks[num - 1][1])
        except ValueError:
            pass
    if marked:
        await update.message.reply_text("✅ Marked done:\n" + "\n".join(f"• {m}" for m in marked))
    else:
        await update.message.reply_text("Invalid numbers. Use /tasks to see the list.")


async def cmd_tn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = get_today_tasks()
    if not tasks:
        await update.message.reply_text("No tasks yet.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /tn 2")
        return
    marked = []
    for arg in context.args:
        try:
            num = int(arg)
            if 1 <= num <= len(tasks):
                update_task_status(tasks[num - 1][0], "not_done")
                marked.append(tasks[num - 1][1])
        except ValueError:
            pass
    if marked:
        await update.message.reply_text("❌ Marked not done — carries to tomorrow:\n" + "\n".join(f"• {m}" for m in marked))
    else:
        await update.message.reply_text("Invalid numbers. Use /tasks to see the list.")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logs  = get_today_log()
    tasks = get_today_tasks()
    if not logs and not tasks:
        await update.message.reply_text("No data for today yet.")
        return
    lines = [f"📊 *Report — {date.today().strftime('%B %d')}*\n"]
    if logs:
        done_r = sum(1 for _, s in logs if s == "done")
        lines.append(f"*Routine ({int(done_r/len(logs)*100)}%)*")
        for name, status in logs:
            lines.append(f"{'✅' if status == 'done' else '❌'} {name}")
    if tasks:
        done_t = sum(1 for t in tasks if t[3] == "done")
        lines.append(f"\n*Study Tasks ({int(done_t/len(tasks)*100)}%)*")
        for _, name, duration, status in tasks:
            icon = "✅" if status == "done" else "❌" if status == "not_done" else "⬜"
            lines.append(f"{icon} {name}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    day_type = get_config("day_type", "normal")
    active   = context.bot_data.get("routine_active", False)
    idx      = context.bot_data.get("current_idx", 0)
    await update.message.reply_text(
        f"📋 *Status*\n\nDay type: *{day_type.upper()}*\nRoutine active: *{'Yes' if active else 'No'}*\nCurrent step: *{idx + 1 if active else '—'}*",
        parse_mode="Markdown",
    )


# ──────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────
def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_TOKEN not found — check your .env file")
    if not CHAT_ID:
        raise ValueError("CHAT_ID not found — run /start in Telegram first")
    if not TURSO_URL or not TURSO_TOKEN:
        raise ValueError("TURSO_DATABASE_URL / TURSO_AUTH_TOKEN not found — check your .env file")

    init_db()
    app = Application.builder().token(TOKEN).build()

    for cmd, fn in [
        ("start",        cmd_start),
        ("setday",       cmd_setday),
        ("done",         cmd_done),
        ("notdone",      cmd_notdone),
        ("startmorning", cmd_startmorning),
        ("testevening",  cmd_testevening),
        ("resetday",     cmd_resetday),
        ("tasks",        cmd_tasks),
        ("td",           cmd_td),
        ("tn",           cmd_tn),
        ("report",       cmd_report),
        ("status",       cmd_status),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    jq = app.job_queue
    jq.run_daily(morning_trigger,        time=time(hour=WAKE_HOUR, minute=WAKE_MINUTE, tzinfo=TIMEZONE))
    jq.run_daily(afternoon_checkin,      time=time(hour=AFT_HOUR,  minute=AFT_MINUTE,  tzinfo=TIMEZONE))
    jq.run_daily(evening_report_trigger, time=time(hour=EVE_HOUR,  minute=EVE_MINUTE,  tzinfo=TIMEZONE))

    logger.info("🤖 RoutineBot Phase 2 (Turso) running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()