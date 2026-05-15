# Marketing Bot (`marketingbot.py`)

`marketingbot.py` is a Telegram-controlled marketing automation bot that stores credentials securely, builds instruction-driven content, publishes to multiple platforms, schedules posts, runs campaigns, and tracks local analytics.

## Features

- Telegram command control with chat-level authorization (`TELEGRAM_CHAT_ID`)
- Encrypted credential storage with Fernet
- Per-platform publishing instruction wizard
- Direct posting to Twitter/X, Reddit, Facebook, Instagram, LinkedIn, Telegram channels
- Generic/custom webhook posting fallback
- APScheduler persistent scheduling with restart restore
- Multi-platform campaign definition and execution
- Draft generation + `/approve` or `/edit` publish flow
- Local post analytics and log clearing

## Requirements

- Python 3.10+
- A Telegram bot token from BotFather
- Write permissions for:
  - `/etc/marketingbot/`
  - `/var/log/marketingbot_posts.log`
  - `/var/log/marketingbot.log`

Install dependencies:

```bash
pip install python-telegram-bot>=20 apscheduler cryptography tweepy praw requests
```

## Environment Variables

- `TELEGRAM_BOT_TOKEN` (required): Telegram bot token
- `TELEGRAM_CHAT_ID` (required): only this chat ID can run commands

Example:

```bash
export TELEGRAM_BOT_TOKEN="123456:ABCDEF..."
export TELEGRAM_CHAT_ID="123456789"
```

## Run

```bash
python marketingbot.py
```

On first run, the bot creates:

- `/etc/marketingbot/secret.key` (Fernet key)
- `/etc/marketingbot/credentials.json` (encrypted credentials blob)
- `/etc/marketingbot/instructions.json`
- `/etc/marketingbot/scheduled.json`
- `/etc/marketingbot/campaigns.json`

## Command Reference

- `/start` — Welcome + command list
- `/help` — Full command help
- `/addcredentials <platform> <key> <value>` — Add/update one credential key
- `/listcredentials` — Show platform key names only (values hidden)
- `/removecredentials <platform>` — Remove all credentials for a platform
- `/setinstructions <platform>` — Interactive instruction setup
- `/getinstructions <platform>` — Show saved instruction config
- `/post <platform> <product_or_service>` — Compose and publish now
- `/schedulepost <platform> <product_or_service> <YYYY-MM-DDTHH:MM>` — Schedule one post
- `/listscheduled` — List all scheduled posts
- `/cancelscheduled <job_id>` — Cancel a scheduled post
- `/campaign <campaign_name>` — Interactive campaign setup
- `/runcampaign <campaign_name>` — Execute campaign posts
- `/listcampaigns` — List campaigns and statuses
- `/generatecontent <platform> <product_or_service>` — Generate draft only
- `/approve` — Publish last generated draft
- `/edit <new_text>` — Replace last draft and publish
- `/analytics <platform>` — Show local posting stats for platform
- `/clearlog <platform>` — Remove log entries for one platform
- `/status` — Uptime + stored objects summary

## Credential Model

Credentials are stored per platform. Typical keys:

```json
{
  "twitter": {
    "api_key": "...",
    "api_secret": "...",
    "access_token": "...",
    "access_token_secret": "..."
  },
  "reddit": {
    "client_id": "...",
    "client_secret": "...",
    "username": "...",
    "password": "..."
  },
  "instagram": {
    "access_token": "...",
    "instagram_user_id": "...",
    "image_url": "https://example.com/image.jpg"
  },
  "facebook": {
    "page_id": "...",
    "access_token": "..."
  },
  "linkedin": {
    "access_token": "...",
    "person_urn": "urn:li:person:..."
  },
  "telegram_channel": {
    "channel_id": "-1001234567890"
  },
  "custom_platform": {
    "webhook_url": "https://example.com/webhook"
  }
}
```

## Platform Publishing Notes

- **Twitter/X:** posts with `tweepy.Client.create_tweet`
- **Reddit:** submits to `instructions.subreddits` using `praw` (text or link mode)
- **Facebook:** posts to Graph API `/{page_id}/feed` (or `me/feed`)
- **Instagram:** creates media then publishes via Graph API
- **LinkedIn:** creates shares via `/v2/shares`
- **Telegram Channel:** sends via Telegram bot `send_message`
- **Generic/Custom:** HTTP POST to `webhook_url` with JSON payload `{"text":"..."}`

## Instruction Wizard Defaults

When values are skipped in `/setinstructions`, defaults are applied:

- `tone`: `professional and friendly`
- `hashtags`: `#marketing #promo`
- `max_length`: `280`
- `include_emoji`: `true`
- `target_audience`: `general audience`
- `format`: `short persuasive paragraph + hashtags`
- `subreddits`: `[]`
- `post_type`: `text`

## Scheduling Persistence

Scheduled posts are persisted to `/etc/marketingbot/scheduled.json` with UUID job IDs and restored on startup. Past-due jobs are removed at startup.

## Logging & Analytics

- Post events (success/failure): `/var/log/marketingbot_posts.log` (JSON lines)
- Bot runtime/errors: `/var/log/marketingbot.log`
- `/analytics <platform>` computes:
  - posts sent
  - successful posts
  - last post date
  - platforms seen in local log

## Security Notes

- Unauthorized chats receive `Not authorized.`
- Credential values are never shown in Telegram responses
- Encrypted credential file uses Fernet key at `/etc/marketingbot/secret.key`
- Restrict file permissions for `/etc/marketingbot/*` and `/var/log/marketingbot*.log`
