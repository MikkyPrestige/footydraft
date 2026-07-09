"""Telegram command handlers."""
import asyncio
from config.settings import XQUIK_POSTING_ENABLED
from datetime import datetime, timedelta
from sqlalchemy import desc
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.database import SessionLocal
from core.scheduler import fetch_and_draft_leaderboards, nerdy_stats_job
from core.models import Draft, Tweet, Rule, SourceHealth
from core.publishing.xquik import XquikPublishError, publish_tweet
from bot.keyboard import copy_buttons

_start_time = None

def set_bot_start_time(t):
    global _start_time
    _start_time = t


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message and list available commands."""
    await update.message.reply_text(
        "⚽ Welcome to FootyDraft!\n\n"
        "I'll push live match events and keep a queue of normal drafts for you to review.\n\n"
        "Commands:\n"
        "/queue - View pending drafts (all/live/normal, page)\n"
        "/drafts - Browse all drafts (all/pending/held/posted, page)\n"
        "/leaderboard - Get latest top scorers & assists drafts\n"
        "/nerdystats - Nerdy stats of the week drafts\n"
        "/hold <draft_id> - Quarantine a pending draft\n"
        "/release <draft_id> - Return a held draft to queue\n"
        "/posted <draft_id> - Mark a draft as posted & link tweet\n"
        "/postx <draft_id> [variant] - Post an approved draft with Xquik\n"
        "/metrics <tweet_id> <likes> <retweets> <replies> <impressions> - Enter engagement numbers\n"
        "/stats - Top & bottom tweets by likes (or /stats impressions)\n"
        "/impressions - Shortcut for top & bottom tweets by impressions\n"
        "/tweets - List all posted tweets\n"
        "/rules - View / approve style rules\n"
        "/addrule <text> - Add a manual rule\n"
        "/source_status - Check news source health\n"
        "/livecheck - Force check for live matches\n"
        "/clearqueue - Delete all pending normal drafts\n"
        "/uptime - Bot uptime and start time (WAT)\n"
        "/restore - Gated database restore from Dropbox backups\n"
        "/restart - Restart the bot (two-step confirmation)\n"
    )

async def queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paginated queue (10 per page) – each draft gets its own Copy buttons."""
    filter_arg = context.args[0].lower() if context.args else "all"
    page = int(context.args[1]) if len(context.args) > 1 else 0

    if filter_arg not in ("all", "normal", "live"):
        await update.message.reply_text("Usage: /queue [normal|live]")
        return

    with SessionLocal() as session:
        if filter_arg == "normal":
            db_query = session.query(Draft).filter(
                Draft.status == "pending",
                Draft.content_type == "normal"
            )
        elif filter_arg == "live":
            db_query = session.query(Draft).filter(
                Draft.status == "pending_live"
            )
        else:  # all pending
            db_query = session.query(Draft).filter(
                Draft.status.in_(["pending", "pending_live"])
            )

        total = db_query.count()
        drafts = db_query.order_by(Draft.created_at.desc()).offset(page * 10).limit(10).all()

        if not drafts:
            await update.message.reply_text(f"📭 No pending drafts for filter '{filter_arg}'.")
            return

        # Send each draft as a separate message with Copy buttons
        for d in drafts:
            variants = d.text_variants
            content_label = "📡 LIVE" if d.content_type == "live" else "📄 Normal"
            header = f"📰 Draft #{d.id} - [{d.persona}] {content_label}"
            msg = header + "\n\n" + "\n\n".join(
                f"**V{i+1}:** {v}" for i, v in enumerate(variants)
            )
            await update.message.reply_text(
                msg,
                reply_markup=copy_buttons(d.id, variants),
                parse_mode="Markdown"
            )

        # Pagination button at the end
        pages = (total - 1) // 10 + 1
        if page + 1 < pages:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("Older ➡️", callback_data=f"queue_{filter_arg}_{page+1}")
            ]])
            await update.message.reply_text(
                f"📋 Page {page+1}/{pages} – tap Older for more",
                reply_markup=keyboard
            )

async def posted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually mark a draft as posted and link it to a tweet ID or URL."""
    if not context.args:
        await update.message.reply_text("Usage: /posted <draft_id> [tweet_url_or_id]")
        return

    draft_id = int(context.args[0])
    tweet_ref = context.args[1] if len(context.args) > 1 else f"manual_{draft_id}"

    with SessionLocal() as session:
        draft = session.get(Draft, draft_id)
        if not draft:
            await update.message.reply_text("Draft not found.")
            return

        tweet = Tweet(
            id=tweet_ref,
            draft_id=draft.id,
            text=draft.text_variants[0],
            posted_at=datetime.utcnow(),
            likes=0,
            retweets=0,
            replies=0,
            impressions=0,
        )
        session.add(tweet)
        draft.status = "posted"
        draft.selected_variant = 0
        session.commit()

    await update.message.reply_text(
        f"✅ Draft #{draft_id} marked as posted and linked to tweet `{tweet_ref}`.\n"
        "Later, use `/metrics {tweet_ref} <likes> <retweets> <replies> <impressions>` to add engagement."
    )

async def postx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Post a draft via Xquik and record the tweet ID."""
    if not XQUIK_POSTING_ENABLED:
        await update.message.reply_text("❌ Xquik posting is not enabled. Set XQUIK_POSTING_ENABLED=1 to use this feature.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /postx <draft_id> [variant]")
        return

    try:
        draft_id = int(context.args[0])
        variant_idx = int(context.args[1]) - 1 if len(context.args) > 1 else 0
    except ValueError:
        await update.message.reply_text("Draft ID and variant must be numbers.")
        return

    with SessionLocal() as session:
        draft = session.get(Draft, draft_id)
        if not draft:
            await update.message.reply_text("Draft not found.")
            return
        if draft.status == "posted":
            await update.message.reply_text(f"Draft #{draft_id} is already posted.")
            return
        if draft.status not in ("pending", "pending_live"):
            await update.message.reply_text(f"Draft #{draft_id} is not pending (status: {draft.status}).")
            return
        if variant_idx < 0 or variant_idx >= len(draft.text_variants):
            await update.message.reply_text(f"Variant must be between 1 and {len(draft.text_variants)}.")
            return
        text = draft.text_variants[variant_idx]

    try:
        tweet_ref = publish_tweet(text)
    except XquikPublishError as e:
        await update.message.reply_text(f"Xquik post failed: {e}")
        return

    with SessionLocal() as session:
        draft = session.get(Draft, draft_id)
        if not draft or draft.status == "posted":
            await update.message.reply_text(f"Posted with Xquik as `{tweet_ref}`, but draft status changed.")
            return

        tweet = Tweet(
            id=tweet_ref,
            draft_id=draft.id,
            text=text,
            posted_at=datetime.utcnow(),
            likes=0,
            retweets=0,
            replies=0,
            impressions=0,
        )
        session.add(tweet)
        draft.status = "posted"
        draft.selected_variant = variant_idx
        session.commit()

    await update.message.reply_text(
        f"✅ Draft #{draft_id} posted with Xquik as `{tweet_ref}`.\n"
        f"Later, use `/metrics {tweet_ref} <likes> <retweets> <replies> <impressions>` to add engagement."
    )

async def metrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually enter engagement metrics for a posted tweet."""
    if len(context.args) != 5:
        await update.message.reply_text("Usage: /metrics <tweet_ref> <likes> <retweets> <replies> <impressions>")
        return

    tweet_ref = context.args[0]
    likes, retweets, replies, impressions = map(int, context.args[1:])

    with SessionLocal() as session:
        tweet = session.get(Tweet, tweet_ref)
        if not tweet:
            await update.message.reply_text("Tweet not found.")
            return
        tweet.likes = likes
        tweet.retweets = retweets
        tweet.replies = replies
        tweet.impressions = impressions
        tweet.last_metrics_fetch = datetime.utcnow()
        session.commit()

    await update.message.reply_text(
        f"✅ Metrics updated for tweet `{tweet_ref}`: "
        f"❤️ {likes} 🔄 {retweets} 💬 {replies} 👀 {impressions}"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top & bottom tweets by likes or impressions in the last 7 days."""
    option = (context.args[0].lower() if context.args else 'likes')
    with SessionLocal() as session:
        cutoff = datetime.utcnow() - timedelta(days=7)
        if option == 'all':
            tweets = session.query(Tweet).filter(
                Tweet.posted_at >= cutoff
            ).order_by(desc(Tweet.posted_at)).all()
        elif option == 'impressions':
            tweets = session.query(Tweet).filter(
                Tweet.posted_at >= cutoff
            ).order_by(desc(Tweet.impressions)).all()
        else:  # likes (default)
            tweets = session.query(Tweet).filter(
                Tweet.posted_at >= cutoff
            ).order_by(desc(Tweet.likes)).all()

    if not tweets:
        await update.message.reply_text("No tweets recorded in the last 7 days.")
        return

    if option == 'all':
        msg = "📋 **All posted tweets (last 7 days):**\n\n"
        for i, t in enumerate(tweets, 1):
            text_snippet = (t.text[:50] + '...') if len(t.text) > 50 else t.text
            msg += f"{i}. `{t.id}`  {text_snippet}  ❤️{t.likes} 👀{t.impressions}\n"
    else:
        top5 = tweets[:5]
        bottom3 = tweets[-3:] if len(tweets) >= 3 else []
        metric_label = "Likes" if option == "likes" else "Impressions"
        heart = "❤️" if option == "likes" else "👀"

        def val(t):
            return t.likes if option == "likes" else t.impressions

        msg = "📊 **Tweet Performance (last 7 days)**\n\n"
        msg += f"**Top 5 by {metric_label}:**\n"
        for i, t in enumerate(top5, 1):
            msg += f"{i}. {t.text[:60]}...  {heart} {val(t)}\n"

        if bottom3:
            msg += f"\n**Bottom 3 by {metric_label}:**\n"
            for i, t in enumerate(bottom3, 1):
                msg += f"{i}. {t.text[:60]}...  {heart} {val(t)}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger the leaderboard draft and display it.  Errors are caught to prevent bot crash."""
    await update.message.reply_text("📊 Fetching latest leaderboard…")
    try:
        draft = await fetch_and_draft_leaderboards()
    except Exception as e:
        await update.message.reply_text(f"❌ Leaderboard error: {e}")
        return

    if draft and draft.text_variants:
        variants = draft.text_variants
        header = f"📰 Draft #{draft.id} - [{draft.persona}] Leaderboard"
        msg = header + "\n\n" + "\n\n".join(
            f"**V{i+1}:** {v}" for i, v in enumerate(variants)
        )
        await update.message.reply_text(
            msg,
            reply_markup=copy_buttons(draft.id, variants),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Leaderboard draft could not be created")

async def nerdystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger the nerdy stats draft and display it.  Errors are caught to prevent bot crash."""
    await update.message.reply_text("🧠 Crunching nerdy stats…")
    try:
        draft = await nerdy_stats_job()
    except Exception as e:
        await update.message.reply_text(f"❌ Nerdy stats error: {e}")
        return

    if draft and draft.text_variants:
        variants = draft.text_variants
        header = f"📰 Draft #{draft.id} - [{draft.persona}] Nerdy Stats"
        msg = header + "\n\n" + "\n\n".join(
            f"**V{i+1}:** {v}" for i, v in enumerate(variants)
        )
        await update.message.reply_text(
            msg,
            reply_markup=copy_buttons(draft.id, variants),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Nerdy stats draft could not be created")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active rules and suggested rules (auto) with Accept/Reject buttons."""
    with SessionLocal() as session:
        active_rules = session.query(Rule).filter_by(active=True).all()
        suggested = session.query(Rule).filter_by(active=False, source="auto").all()

    msg = "📋 **Active Rules:**\n"
    if active_rules:
        for r in active_rules:
            msg += f"✅ {r.rule_text}\n"
    else:
        msg += "No active rules. Use /addrule to add one.\n"

    if suggested:
        msg += "\n**Suggested Rules (Accept/Reject):**\n"
        for r in suggested:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Accept", callback_data=f"acceptrule_{r.id}"),
                    InlineKeyboardButton("Reject", callback_data=f"rejectrule_{r.id}")
                ]
            ])
            await update.message.reply_text(f"🤖 {r.rule_text}\n", reply_markup=keyboard)

    await update.message.reply_text(msg, parse_mode="Markdown")

async def addrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a manual rule to the database and mark it as active."""
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /addrule <rule text>")
        return
    with SessionLocal() as session:
        rule = Rule(rule_text=text, source="manual", active=True)
        session.add(rule)
        session.commit()
    await update.message.reply_text(f"✅ Rule added and active: {text}")

async def source_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the health status of all news sources."""
    with SessionLocal() as session:
        sources = session.query(SourceHealth).all()
    if not sources:
        await update.message.reply_text("No source health data yet.")
        return
    msg = "📡 **Source Status:**\n"
    for s in sources:
        icon = "🟢" if s.status == "UP" else "🔴"
        msg += f"{icon} {s.source_name} – last success: {s.last_success}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline buttons (queue, drafts, copy, rules)."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("queue_"):
        _, filter_arg, page_str = data.split("_", 2)
        page = int(page_str)
        with SessionLocal() as session:
            if filter_arg == "normal":
                db_query = session.query(Draft).filter(
                    Draft.status == "pending",
                    Draft.content_type == "normal"
                )
            elif filter_arg == "live":
                db_query = session.query(Draft).filter(
                    Draft.status == "pending_live"
                )
            else:  # all pending
                db_query = session.query(Draft).filter(
                    Draft.status.in_(["pending", "pending_live"])
                )
            total = db_query.count()
            drafts = db_query.order_by(Draft.created_at.desc()).offset(page * 10).limit(10).all()
            if not drafts:
                await query.edit_message_text("No more drafts.")
                return
            # Send each draft individually with Copy buttons
            for d in drafts:
                variants = d.text_variants

                content_label = "📡 LIVE" if d.content_type == "live" else "📄 Normal"
                header = f"📰 Draft #{d.id} - [{d.persona}] {content_label}"
                msg = header + "\n\n" + "\n\n".join(
                    f"**V{i+1}:** {v}" for i, v in enumerate(variants)
                )
                await query.message.reply_text(
                    msg,
                    reply_markup=copy_buttons(d.id, variants),
                    parse_mode="Markdown"
                )
            # Pagination button at the end
            pages = (total - 1) // 10 + 1
            if page + 1 < pages:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Older ➡️", callback_data=f"queue_{filter_arg}_{page+1}")
                ]])
                await query.message.reply_text(
                    f"📋 Page {page+1}/{pages} – tap Older for more",
                    reply_markup=keyboard
                )

    elif data.startswith("drafts_"):
        _, filter_arg, page_str = data.split("_", 2)
        page = int(page_str)
        with SessionLocal() as session:
            db_query = session.query(Draft)
            if filter_arg == "pending":
                db_query = db_query.filter(Draft.status == "pending", Draft.content_type == "normal")
            elif filter_arg in ("held", "posted"):
                db_query = db_query.filter(Draft.status == filter_arg)
            total = db_query.count()
            drafts = db_query.order_by(Draft.created_at.desc()).offset(page * 10).limit(10).all()
            if not drafts:
                await query.edit_message_text("No more drafts.")
                return
            pages = (total - 1) // 10 + 1
            msg = f"📋 Drafts ({filter_arg}) – page {page+1}/{pages}\n\n"
            for d in drafts:
                preview = d.text_variants[0][:60] + "..." if d.text_variants[0] and len(d.text_variants[0]) > 60 else d.text_variants[0]
                msg += f"#{d.id} [{d.persona}] {preview}\n"
            keyboard = None
            if page + 1 < pages:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Older ➡️", callback_data=f"drafts_{filter_arg}_{page+1}")
                ]])
            await query.edit_message_text(msg, reply_markup=keyboard)

    elif data.startswith("copy_"):
        _, draft_id, variant_idx = data.split("_")
        draft_id = int(draft_id)
        variant_idx = int(variant_idx)
        with SessionLocal() as session:
            draft = session.get(Draft, draft_id)
            if draft:
                await query.message.reply_text(
                    draft.text_variants[variant_idx]
                )
                await query.message.reply_text(
                    "📋 After posting, use: `/posted {}`".format(draft_id),
                    parse_mode="Markdown"
                )
            else:
                await query.message.reply_text("Draft not found.")

    elif data.startswith("acceptrule_"):
        rule_id = int(data.split("_")[1])
        with SessionLocal() as session:
            rule = session.get(Rule, rule_id)
            if rule:
                rule.active = True
                session.commit()
                await query.edit_message_text(f"✅ Rule accepted: {rule.rule_text}")

    elif data.startswith("rejectrule_"):
        rule_id = int(data.split("_")[1])
        with SessionLocal() as session:
            rule = session.get(Rule, rule_id)
            if rule:
                session.delete(rule)
                session.commit()
                await query.edit_message_text("❌ Rule rejected and removed.")

async def livecheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force a live-match check via API-Football and return results."""
    from core.ingestion.api_football_fetcher import APIFootballFetcher
    from core.classification.event_tagger import classify_item

    await update.message.reply_text("🔄 Checking for live matches...")

    fetcher = APIFootballFetcher()
    items = await fetcher.fetch()

    if not items:
        from datetime import datetime as dt, timedelta
        yesterday = (dt.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%d")
        fetcher2 = APIFootballFetcher(match_date=yesterday)
        items = await fetcher2.fetch()
        await update.message.reply_text(f"Debug: today fetcher returned {len(items)} items")
        if items:
            await update.message.reply_text(f"⚠️ No live matches now, but found {len(items)} events from recent matches:")
        else:
            await update.message.reply_text("ℹ️ No live matches found in the last 2 hours.")
            return

    for item in items[:10]:
        tag = classify_item(item)
        await update.message.reply_text(f"[{tag}] {item.title}")

async def tweets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper around /stats all"""
    context.args = ['all']
    await stats(update, context)

async def impressions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper around /stats impressions"""
    context.args = ['impressions']
    await stats(update, context)

async def clearqueue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete pending drafts. Use /clearqueue live|normal to clear only live or only normal."""
    filter_arg = context.args[0].lower() if context.args else "all"
    with SessionLocal() as session:
        if filter_arg == "live":
            deleted = session.query(Draft).filter(
                Draft.status == "pending_live"
            ).delete()
        elif filter_arg == "normal":
            deleted = session.query(Draft).filter(
                Draft.status == "pending",
                Draft.content_type == "normal"
            ).delete()
        else:
            deleted = session.query(Draft).filter(
                Draft.status.in_(["pending", "pending_live"])
            ).delete()
        session.commit()
    label = filter_arg if filter_arg in ("live", "normal") else "pending"
    await update.message.reply_text(f"🗑️ {deleted} {label} draft(s) cleared.")

async def hold_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Move a pending draft to held status (quarantine)."""
    if not context.args:
        await update.message.reply_text("Usage: /hold <draft_id>")
        return
    draft_id = int(context.args[0])
    with SessionLocal() as session:
        draft = session.get(Draft, draft_id)
        if not draft:
            await update.message.reply_text("Draft not found.")
            return
        if draft.status not in ("pending", "pending_live"):
            await update.message.reply_text(f"Draft #{draft_id} is not pending (status: {draft.status}).")
            return
        draft.status = "held"
        session.commit()
    await update.message.reply_text(f"📥 Draft #{draft_id} moved to held.")

async def release_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Move a held draft back to pending."""
    if not context.args:
        await update.message.reply_text("Usage: /release <draft_id>")
        return
    draft_id = int(context.args[0])
    with SessionLocal() as session:
        draft = session.get(Draft, draft_id)
        if not draft:
            await update.message.reply_text("Draft not found.")
            return
        if draft.status != "held":
            await update.message.reply_text(f"Draft #{draft_id} is not held (status: {draft.status}).")
            return
        draft.status = "pending"
        session.commit()
    await update.message.reply_text(f"📤 Draft #{draft_id} released back to queue.")

async def drafts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show drafts with optional filter and pagination."""
    filter_arg = context.args[0].lower() if context.args else "all"
    page = int(context.args[1]) if len(context.args) > 1 else 0

    if filter_arg not in ("all", "pending", "held", "posted"):
        await update.message.reply_text("Usage: /drafts [all|pending|held|posted]")
        return

    with SessionLocal() as session:
        db_query = session.query(Draft)
        if filter_arg != "all":
            if filter_arg == "pending":
                db_query = db_query.filter(Draft.status == "pending", Draft.content_type == "normal")
            else:
                db_query = db_query.filter(Draft.status == filter_arg)

        total = db_query.count()
        drafts = db_query.order_by(Draft.created_at.desc()).offset(page * 10).limit(10).all()

        if not drafts:
            await update.message.reply_text(f"No drafts found for filter '{filter_arg}'.")
            return

        pages = (total - 1) // 10 + 1
        msg = f"📋 Drafts ({filter_arg}) – page {page+1}/{pages}\n\n"
        for d in drafts:
            preview = d.text_variants[0][:60] + "..." if d.text_variants[0] and len(d.text_variants[0]) > 60 else d.text_variants[0]
            msg += f"#{d.id} [{d.persona}] {preview}\n"

        keyboard = None
        if page + 1 < pages:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("Older ➡️", callback_data=f"drafts_{filter_arg}_{page+1}")
            ]])

        await update.message.reply_text(msg, reply_markup=keyboard)

async def uptime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot start time and elapsed uptime."""
    from datetime import datetime
    global _start_time
    if _start_time is None:
        await update.message.reply_text("Uptime not available yet.")
        return
    now = datetime.utcnow()
    delta = now - _start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    elapsed = " ".join(parts)
    from datetime import timedelta
    wat = _start_time + timedelta(hours=1)
    started = wat.strftime("%Y-%m-%d %H:%M:%S WAT")
    await update.message.reply_text(
        f"⏱️ Bot uptime: {elapsed}\n"
        f"🟢 Started at: {started}"
    )

# Restore state: one‑time code and expiry
_restore_code = None
_restore_expiry = None
_restore_files = None

async def restore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gated database restore: step 1 generates a code, step 2 lists backups, step 3 restores."""
    global _restore_code, _restore_expiry
    from datetime import datetime as dt
    # Step 1 – generate a one‑time code
    if not context.args:
        import random, string
        _restore_code = ''.join(random.choices(string.digits, k=6))
        _restore_expiry = dt.utcnow() + timedelta(minutes=5)
        await update.message.reply_text(
            f"🔐 Restore code: {_restore_code}\n"
            f"⏳ Expires in 5 minutes.\n"
            f"Use `/restore {_restore_code}` to continue."
        )
        return

    arg = context.args[0]
    # If the argument is exactly 6 digits → code verification
    if arg.isdigit() and len(arg) == 6:
        if _restore_code is None or arg != _restore_code:
            await update.message.reply_text("❌ Invalid restore code.")
            return
        if dt.utcnow() > _restore_expiry:
            _restore_code = None
            _restore_expiry = None
            await update.message.reply_text("⏳ Code expired. Use /restore to generate a new one.")
            return
        # Code accepted – mark as used
        _restore_code = None
        _restore_expiry = None
        try:
            import dropbox
            from config.settings import DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN
            dbx = dropbox.Dropbox(
                oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
                app_key=DROPBOX_APP_KEY,
                app_secret=DROPBOX_APP_SECRET,
            )
            result = dbx.files_list_folder("/backups", recursive=False)
            files = result.entries
            while result.has_more:
                result = dbx.files_list_folder_continue(result.cursor)
                files.extend(result.entries)
            # keep only .db.gz files, extract date from name
            backups = []
            for entry in files:
                if entry.name.startswith("agent_backup_") and entry.name.endswith(".db.gz"):
                    try:
                        date_str = entry.name.split("_")[2]
                        file_date = dt.strptime(date_str, "%Y%m%d").date()
                        backups.append({"name": entry.name, "date": file_date})
                    except (IndexError, ValueError):
                        continue
            if not backups:
                await update.message.reply_text("ℹ️ No backup files found in Dropbox.")
                return
            # sort newest first, take last 5
            backups.sort(key=lambda x: x["date"], reverse=True)
            latest = backups[:5]
            global _restore_files
            _restore_files = latest
            msg = "📁 **Last 5 backups:**\n"
            for i, b in enumerate(latest, 1):
                msg += f"{i}. `{b['name']}` – {b['date'].strftime('%d %b %Y')}\n"
            msg += "\nUse `/restore <filename>` to restore one."
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to list backups: {e}")

    # arg is not 6 digits → either a filename or invalid
    elif _restore_files:
        filename = arg
        # verify filename exists in the list
        match = next((b for b in _restore_files if b["name"] == filename), None)
        if not match:
            await update.message.reply_text("❌ Invalid filename. Use the exact name from the list.")
            return

        await update.message.reply_text("⏳ Restoring backup…")
        try:
            import dropbox, gzip, os
            from config.settings import DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN
            dbx = dropbox.Dropbox(
                oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
                app_key=DROPBOX_APP_KEY,
                app_secret=DROPBOX_APP_SECRET,
            )
            # Download .db.gz and decompress directly on the persistent volume
            gz_path = "data/agent_restored.db.gz"
            dbx.files_download_to_file(gz_path, f"/backups/{filename}")
            restored_db = "data/agent_restored.db"
            with gzip.open(gz_path, "rb") as f_in, open(restored_db, "wb") as f_out:
                f_out.write(f_in.read())
            os.remove(gz_path)  # clean up .gz after decompress
            _restore_files = None
            await update.message.reply_text(
                "✅ Restored database staged. "
                "Restart the bot to apply changes."
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Restore failed: {e}")
    else:
        await update.message.reply_text("❌ Invalid restore code.")

_restart_expiry = None

async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Two‑step restart: /restart then /restart confirm within 60s."""
    global _restart_expiry
    from datetime import datetime as dt
    if not context.args:
        _restart_expiry = dt.utcnow() + timedelta(seconds=60)
        await update.message.reply_text(
            "⚠️ Are you sure you want to restart the bot?\n"
            "This will interrupt all operations for about a minute.\n"
            "Use `/restart confirm` within the next 60 seconds to proceed."
        )
        return

    arg = context.args[0].lower()
    if arg == "confirm":
        if _restart_expiry is None or dt.utcnow() > _restart_expiry:
            _restart_expiry = None
            await update.message.reply_text("Restart request expired. Use /restart to try again.")
            return
        _restart_expiry = None
        await update.message.reply_text("🔄 Restarting machine…")
        try:
            import os, requests
            fly_token = os.getenv("FLY_API_TOKEN")
            app_name = os.getenv("FLY_APP_NAME")
            machine_id = os.getenv("FLY_MACHINE_ID")
            if not fly_token or not app_name or not machine_id:
                await update.message.reply_text("❌ Missing required environment variables.")
                return
            resp = requests.post(
                f"https://api.machines.dev/v1/apps/{app_name}/machines/{machine_id}/restart",
                headers={"Authorization": f"Bearer {fly_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                await update.message.reply_text("✅ Machine is restarting. The bot will be back in a moment.")
            else:
                await update.message.reply_text(f"❌ Fly API returned {resp.status_code}: {resp.text}")
        except Exception as e:
            await update.message.reply_text(f"❌ Restart failed: {e}")
    else:
        await update.message.reply_text("Usage: /restart confirm")
