"""
bot.py — main entrypoint.

Commands:
  /savenote <name> <text>   (or reply to a message with /savenote <name>)
  /note <name>              show a saved note
  /notes                    list all note names
  /delnote <name>           delete a note
  /ask <question>           ask the AI a question
  /warnings                 (reply to a user) show their warning count
  /resetwarn                (reply to a user) clear their warnings — admin only

Auto-moderation (no command needed):
  - Deletes messages with 3+ links / link+mentions spam pattern
  - Deletes messages flooding the chat (6+ msgs in 10s from one user)
  - Deletes photos/videos flagged unsafe by AI, warns the sender
  - Warns members who use profanity from bad_words.txt; bans after N warnings
  - Bans users after N spam strikes
"""

import logging
import os

from telegram import Update, ChatPermissions
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import db
import moderation
import ai

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SPAM_BAN_THRESHOLD = int(os.environ.get("SPAM_BAN_THRESHOLD", "3"))
BADWORD_WARN_LIMIT = int(os.environ.get("BADWORD_WARN_LIMIT", "3"))


# ---------------- helpers ----------------

async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(
        update.effective_chat.id, update.effective_user.id
    )
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def _ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    chat_id = update.effective_chat.id
    try:
        await context.bot.ban_chat_member(chat_id, user_id)
    except Exception as e:
        logger.warning(f"Could not ban {user_id} in {chat_id}: {e}")


# ---------------- note commands ----------------

async def savenote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /savenote <name> <text> (or reply to a message)")
        return
    name = context.args[0]
    if update.message.reply_to_message and len(context.args) == 1:
        content = update.message.reply_to_message.text or update.message.reply_to_message.caption
    else:
        content = " ".join(context.args[1:])
    if not content:
        await update.message.reply_text("Nothing to save — add text or reply to a message.")
        return
    db.save_note(update.effective_chat.id, name, content, update.effective_user.id)
    await update.message.reply_text(f"Saved note '{name}'.")


async def note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /note <name>")
        return
    content = db.get_note(update.effective_chat.id, context.args[0])
    if content is None:
        await update.message.reply_text("No note with that name.")
    else:
        await update.message.reply_text(content)


async def notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    names = db.list_notes(update.effective_chat.id)
    if not names:
        await update.message.reply_text("No notes saved yet.")
    else:
        await update.message.reply_text("Notes: " + ", ".join(names))


async def delnote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delnote <name>")
        return
    ok = db.delete_note(update.effective_chat.id, context.args[0])
    await update.message.reply_text("Deleted." if ok else "No note with that name.")


# ---------------- AI Q&A ----------------

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args) if context.args else None
    if not question and update.message.reply_to_message:
        question = update.message.reply_to_message.text
    if not question:
        await update.message.reply_text("Usage: /ask <question>")
        return
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    answer = ai.ask_ai(question)
    await update.message.reply_text(answer)


# ---------------- warnings admin ----------------

async def warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message with /warnings")
        return
    uid = update.message.reply_to_message.from_user.id
    bw = db.get_violation_count(update.effective_chat.id, uid, "badword")
    sp = db.get_violation_count(update.effective_chat.id, uid, "spam")
    await update.message.reply_text(f"Bad-word warnings: {bw}\nSpam strikes: {sp}")


async def resetwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message with /resetwarn")
        return
    uid = update.message.reply_to_message.from_user.id
    db.reset_violations(update.effective_chat.id, uid)
    await update.message.reply_text("Warnings reset for that user.")


# ---------------- auto-moderation ----------------

async def moderate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or update.effective_user is None:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Never moderate admins
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return
    except Exception:
        pass

    text = message.text or message.caption or ""

    # 1) Flood / link spam
    db.log_message(chat_id, user_id)
    flood_count = db.recent_message_count(
        chat_id, user_id, moderation.FLOOD_WINDOW_SECONDS
    )
    if flood_count > moderation.FLOOD_MAX_MESSAGES or moderation.is_spammy_text(text):
        try:
            await message.delete()
        except Exception:
            pass
        strikes = db.bump_violation(chat_id, user_id, "spam")
        if strikes >= SPAM_BAN_THRESHOLD:
            await _ban_user(update, context, user_id)
            await context.bot.send_message(
                chat_id, f"🚫 Banned a repeat spammer (user id {user_id})."
            )
        else:
            await context.bot.send_message(
                chat_id,
                f"⚠️ Message removed (spam-like). Strike {strikes}/{SPAM_BAN_THRESHOLD}.",
            )
        return

    # 2) Bad words (Banglish / Bangla profanity)
    matched = moderation.contains_bad_word(text)
    if matched:
        try:
            await message.delete()
        except Exception:
            pass
        warns = db.bump_violation(chat_id, user_id, "badword")
        mention = update.effective_user.mention_html()
        if warns >= BADWORD_WARN_LIMIT:
            await _ban_user(update, context, user_id)
            await context.bot.send_message(
                chat_id,
                f"🚫 {mention} was banned after repeated warnings for inappropriate language.",
                parse_mode="HTML",
            )
        else:
            await context.bot.send_message(
                chat_id,
                f"⚠️ {mention}, please keep the language clean. "
                f"Warning {warns}/{BADWORD_WARN_LIMIT}.",
                parse_mode="HTML",
            )
        return

    # 3) Auto-answer questions (no /ask needed)
    if message.text and moderation.looks_like_question(message.text):
        await context.bot.send_chat_action(chat_id, "typing")
        answer = ai.ask_ai(message.text)
        await message.reply_text(answer)
        return

    # 4) Photos / videos — AI moderation
    if message.photo or message.video:
        file = None
        mime = "image/jpeg"
        if message.photo:
            file = await message.photo[-1].get_file()
        elif message.video and message.video.thumbnail:
            file = await message.video.thumbnail.get_file()
        if file:
            img_bytes = bytes(await file.download_as_bytearray())
            if ai.is_image_unsafe(img_bytes, mime):
                try:
                    await message.delete()
                except Exception:
                    pass
                warns = db.bump_violation(chat_id, user_id, "badword")
                mention = update.effective_user.mention_html()
                await context.bot.send_message(
                    chat_id,
                    f"🚫 Removed inappropriate media from {mention}. "
                    f"Warning {warns}/{BADWORD_WARN_LIMIT}.",
                    parse_mode="HTML",
                )
                if warns >= BADWORD_WARN_LIMIT:
                    await _ban_user(update, context, user_id)


# ---------------- bootstrap ----------------

def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("Set the BOT_TOKEN environment variable (get it from @BotFather).")

    db.init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("savenote", savenote))
    app.add_handler(CommandHandler("note", note))
    app.add_handler(CommandHandler("notes", notes))
    app.add_handler(CommandHandler("delnote", delnote))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("warnings", warnings_cmd))
    app.add_handler(CommandHandler("resetwarn", resetwarn_cmd))

    # Auto-moderation runs on every non-command message (text, photo, video)
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
            moderate_message,
        )
    )

    return app


if __name__ == "__main__":
    application = build_app()

    port = int(os.environ.get("PORT", "8080"))
    webhook_url = os.environ.get("WEBHOOK_URL")  # e.g. https://your-app.onrender.com

    if webhook_url:
        logger.info("Starting in webhook mode on port %s", port)
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=f"{webhook_url.rstrip('/')}/{BOT_TOKEN}",
        )
    else:
        logger.info("Starting in polling mode")
        application.run_polling()
