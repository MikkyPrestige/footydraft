"""Telegram bot entry point. Run with: python -m bot.main"""
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import BotCommand
from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from bot.handlers import (
    clearqueue,
    drafts_cmd,
    hold_draft,
    release_draft,
    start, queue_callback, stats, rules, addrule, source_status,
    posted, metrics, button_handler, backup_cmd, livecheck, tweets_cmd, impressions_cmd
)

async def push_live_drafts(context):
    """Background job: push new live drafts to admin chat."""
    from core.database import SessionLocal
    from core.models import Draft
    from bot.keyboard import copy_buttons

    with SessionLocal() as session:
        live_drafts = session.query(Draft).filter(
            Draft.status == "pending_live"
        ).all()

        for draft in live_drafts:
            variants = draft.text_variants
            header = f"📡 LIVE Draft #{draft.id} — [{draft.persona}]"
            msg = header + "\n\n" + "\n\n".join(
                f"**V{i+1}:** {v}" for i, v in enumerate(variants)
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=msg,
                reply_markup=copy_buttons(draft.id, variants),
                parse_mode="Markdown"
            )
            draft.status = "pending"  # after push, it appears in the queue as well
            session.commit()

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register all command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("queue", queue_callback))
    app.add_handler(CommandHandler("drafts", drafts_cmd))
    app.add_handler(CommandHandler("hold", hold_draft))
    app.add_handler(CommandHandler("release", release_draft))
    app.add_handler(CommandHandler("posted", posted))
    app.add_handler(CommandHandler("metrics", metrics))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("addrule", addrule))
    app.add_handler(CommandHandler("source_status", source_status))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("livecheck", livecheck))
    app.add_handler(CommandHandler("tweets", tweets_cmd))
    app.add_handler(CommandHandler("impressions", impressions_cmd))
    app.add_handler(CommandHandler("clearqueue", clearqueue))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Live-draft push job (every 20 seconds)
    app.job_queue.run_repeating(push_live_drafts, interval=20, first=5)

    print("Bot polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
