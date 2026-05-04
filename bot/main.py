"""Telegram bot entry point. Run with: python -m bot.main"""
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from config.settings import TELEGRAM_BOT_TOKEN
from bot.handlers import (
    drafts_cmd,
    hold_draft, release_draft,
    clearqueue,
    start, queue_callback, stats, rules, addrule, source_status,
    posted, metrics, button_handler, backup_cmd, livecheck, tweets_cmd, impressions_cmd
)

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("queue", queue_callback))
    app.add_handler(CommandHandler("posted", posted))
    app.add_handler(CommandHandler("metrics", metrics))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("addrule", addrule))
    app.add_handler(CommandHandler("source_status", source_status))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("livecheck", livecheck))
    app.add_handler(CommandHandler("hold", hold_draft))
    app.add_handler(CommandHandler("drafts", drafts_cmd))
    app.add_handler(CommandHandler("release", release_draft))
    app.add_handler(CommandHandler("clearqueue", clearqueue))
    app.add_handler(CommandHandler("tweets", tweets_cmd))
    app.add_handler(CommandHandler("impressions", impressions_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
