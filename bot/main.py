"""Telegram bot entry point. Run with: python -m bot.main"""
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import sentry_sdk
from config.settings import SENTRY_DSN
sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)

from datetime import datetime
from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, XQUIK_POSTING_ENABLED
from bot.handlers import (
    clearqueue,
    drafts_cmd,
    hold_draft,
    release_draft,
    start, queue_callback, stats, rules, addrule, source_status,
    posted, postx, metrics, button_handler, livecheck, tweets_cmd, impressions_cmd, uptime_cmd, set_bot_start_time
)

async def push_live_drafts(context):
    """Push only fresh live drafts (created within 90s)."""
    from core.database import SessionLocal
    from core.models import Draft
    from bot.keyboard import copy_buttons
    from datetime import datetime, timedelta

    try:
        cutoff = datetime.utcnow() - timedelta(seconds=90)
        with SessionLocal() as session:
            live_drafts = session.query(Draft).filter(
                Draft.status == "pending_live",
                Draft.created_at >= cutoff
            ).all()

            for draft in live_drafts:
                variants = draft.text_variants
                header = f"📡 LIVE Draft #{draft.id} - [{draft.persona}]"
                msg = header + "\n\n" + "\n\n".join(
                    f"**V{i+1}:** {v}" for i, v in enumerate(variants)
                )
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=msg,
                    reply_markup=copy_buttons(draft.id, variants),
                    parse_mode="Markdown"
                )
                draft.status = "pending"
                session.commit()
    except Exception as e:
        print(f"Live-push error: {e}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("queue", queue_callback))
    app.add_handler(CommandHandler("drafts", drafts_cmd))
    app.add_handler(CommandHandler("hold", hold_draft))
    app.add_handler(CommandHandler("release", release_draft))
    app.add_handler(CommandHandler("posted", posted))
    if XQUIK_POSTING_ENABLED:
        app.add_handler(CommandHandler("postx", postx))
    app.add_handler(CommandHandler("metrics", metrics))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("addrule", addrule))
    app.add_handler(CommandHandler("source_status", source_status))
    app.add_handler(CommandHandler("livecheck", livecheck))
    app.add_handler(CommandHandler("tweets", tweets_cmd))
    app.add_handler(CommandHandler("impressions", impressions_cmd))
    app.add_handler(CommandHandler("clearqueue", clearqueue))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Live-draft push job (every 20 seconds, first run after 5 seconds)
    app.add_handler(CommandHandler("uptime", uptime_cmd))
    app.job_queue.run_repeating(push_live_drafts, interval=20, first=5)

    print("Bot polling...")
    set_bot_start_time(datetime.utcnow())
    app.run_polling()

if __name__ == "__main__":
    main()
