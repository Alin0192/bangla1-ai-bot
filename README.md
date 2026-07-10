# Bangla/Banglish Group Guardian Bot

Free Telegram moderation + notes + AI Q&A bot, built for groups that chat in
Banglish ("tomi kemon acho", "ki korish", mixed with English/Bangla script).

## What it does
- **Notes**: `/savenote`, `/note`, `/notes`, `/delnote`
- **AI Q&A**: `/ask <question>` — understands Banglish, answers in kind
- **Spam removal**: deletes link-flood / mention-spam messages and message-flooding
- **Bad word warnings**: detects Banglish/Bangla profanity (even obfuscated,
  like `c##`), deletes the message, warns the user, bans after repeated warnings
- **Media moderation**: sends photos/videos to Gemini Vision to check for
  nudity/gore; deletes flagged media automatically
- **Repeat spammer bans**: auto-bans after a configurable number of spam strikes

## 1. Create the bot
1. In Telegram, message **@BotFather** → `/newbot` → follow the prompts.
2. Copy the token it gives you (looks like `123456:ABC-DEF...`).
3. Still in BotFather: `/mybots` → your bot → **Bot Settings → Group Privacy →
   Turn off**. This lets the bot read all group messages (needed to catch
   spam/bad words), not just commands.
4. Add the bot to your group and **promote it to Admin** with at least:
   Delete messages, Ban users.

## 2. Get a free Gemini API key (for AI Q&A + photo moderation)
1. Go to https://aistudio.google.com/apikey
2. Sign in with Google, click **Create API key**. It's free for personal-scale use.

## 3. Configure your bad-words list
Open `bad_words.txt` and add your own group's slang, one root word per line,
plain lowercase (no symbols needed — the bot catches obfuscated spellings
automatically). This file ships empty on purpose since you know your
community's language better than a generic list would.

## 4. Deploy for free on Render
1. Push this folder to a new GitHub repo.
2. On https://render.com → **New → Web Service** → connect the repo.
   (Render will detect `render.yaml` automatically — or set Build Command
   `pip install -r requirements.txt` and Start Command `python bot.py`.)
3. Add environment variables in the Render dashboard:
   - `BOT_TOKEN` — from BotFather
   - `GEMINI_API_KEY` — from AI Studio
   - `WEBHOOK_URL` — `https://<your-service-name>.onrender.com` (Render shows
     you this URL after the first deploy; add the variable and redeploy once
     you know it)
4. Deploy. The bot switches to webhook mode automatically once `WEBHOOK_URL` is set.

**Important — free tier sleep:** Render's free web services sleep after 15
minutes of no incoming HTTP traffic, which would delay the bot's replies.
Fix it with a free uptime pinger: create a free account at
https://uptimerobot.com and add an HTTP monitor that pings
`https://<your-service-name>.onrender.com` every 5 minutes. That keeps the
service (and the bot) awake continuously at no cost.

Alternative hosts if you'd rather avoid the keep-alive trick: a free-tier VPS
you already have, or your own always-on PC/Raspberry Pi running
`python bot.py` in polling mode (just don't set `WEBHOOK_URL` — no domain needed).

## 5. Tune the moderation strictness (optional)
Environment variables:
- `SPAM_BAN_THRESHOLD` (default `3`) — spam strikes before an auto-ban
- `BADWORD_WARN_LIMIT` (default `3`) — profanity warnings before an auto-ban

## Notes on accuracy
- The Banglish profanity filter is regex-based and catches your listed root
  words plus common symbol-obfuscated spellings. It won't catch every
  possible creative misspelling — extend `bad_words.txt` as new ones appear.
- Photo/video moderation uses Gemini Vision (`is_image_unsafe` in `ai.py`).
  For videos it currently checks the thumbnail frame only (checking every
  frame of a video isn't free-tier friendly); this catches most cases but
  isn't foolproof.
- The bot never moderates group admins.
