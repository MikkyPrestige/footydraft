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
    """Push only fresh live drafts (created within 90s)."""
    from core.database import SessionLocal
    from core.models import Draft
    from bot.keyboard import copy_buttons
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(seconds=90)

    with SessionLocal() as session:
        live_drafts = session.query(Draft).filter(
            Draft.status == "pending_live",
            Draft.created_at >= cutoff
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
            draft.status = "pending"
            session.commit()
