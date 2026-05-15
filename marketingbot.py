#!/usr/bin/env python3
"""Telegram-controlled universal marketing automation bot."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

import requests
import tweepy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from cryptography.fernet import Fernet, InvalidToken
from praw import Reddit
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

BASE_DIR = Path("/etc/marketingbot")
SECRET_KEY_PATH = BASE_DIR / "secret.key"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
INSTRUCTIONS_PATH = BASE_DIR / "instructions.json"
SCHEDULED_PATH = BASE_DIR / "scheduled.json"
CAMPAIGNS_PATH = BASE_DIR / "campaigns.json"
POST_LOG_PATH = Path("/var/log/marketingbot_posts.log")
BOT_LOG_PATH = Path("/var/log/marketingbot.log")

DEFAULT_INSTRUCTIONS: Dict[str, Any] = {
    "tone": "professional and friendly",
    "hashtags": "#marketing #promo",
    "max_length": 280,
    "include_emoji": True,
    "target_audience": "general audience",
    "format": "short persuasive paragraph + hashtags",
    "subreddits": [],
    "post_type": "text",
}

(
    INSTR_TONE,
    INSTR_HASHTAGS,
    INSTR_MAX_LENGTH,
    INSTR_INCLUDE_EMOJI,
    INSTR_TARGET,
    INSTR_FORMAT,
    INSTR_SUBREDDITS,
    INSTR_POST_TYPE,
) = range(8)

(CAMPAIGN_PRODUCT, CAMPAIGN_PLATFORMS) = range(2)

START_TIME = datetime.now(timezone.utc)
scheduler = AsyncIOScheduler()
storage_lock = asyncio.Lock()

logger = logging.getLogger("marketingbot")


@dataclass
class BotConfig:
    token: str
    authorized_chat_id: int


def setup_logging() -> None:
    BOT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(BOT_LOG_PATH, encoding="utf-8"))
    except OSError as exc:
        handlers[0].stream.write(f"Warning: could not open bot log file: {exc}\n")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def read_config() -> BotConfig:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id_raw = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
    if not chat_id_raw:
        raise RuntimeError("Missing TELEGRAM_CHAT_ID environment variable")
    try:
        authorized_chat_id = int(chat_id_raw)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_CHAT_ID must be an integer") from exc
    return BotConfig(token=token, authorized_chat_id=authorized_chat_id)


def ensure_base_dir() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load JSON from %s", path)
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    tmp_path.replace(path)


def get_or_create_fernet() -> Fernet:
    ensure_base_dir()
    if not SECRET_KEY_PATH.exists():
        key = Fernet.generate_key()
        SECRET_KEY_PATH.write_bytes(key)
        try:
            os.chmod(SECRET_KEY_PATH, 0o600)
        except OSError:
            logger.warning("Could not set permissions on %s", SECRET_KEY_PATH)
    key_bytes = SECRET_KEY_PATH.read_bytes()
    return Fernet(key_bytes)


def load_credentials() -> Dict[str, Dict[str, str]]:
    if not CREDENTIALS_PATH.exists():
        return {}
    try:
        encrypted = CREDENTIALS_PATH.read_bytes()
        if not encrypted:
            return {}
        decrypted = get_or_create_fernet().decrypt(encrypted)
        data = json.loads(decrypted.decode("utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, InvalidToken, json.JSONDecodeError):
        logger.exception("Failed to load encrypted credentials")
    return {}


def save_credentials(data: Dict[str, Dict[str, str]]) -> None:
    ensure_base_dir()
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    encrypted = get_or_create_fernet().encrypt(raw)
    CREDENTIALS_PATH.write_bytes(encrypted)
    try:
        os.chmod(CREDENTIALS_PATH, 0o600)
    except OSError:
        logger.warning("Could not set permissions on %s", CREDENTIALS_PATH)


def load_instructions() -> Dict[str, Dict[str, Any]]:
    return load_json(INSTRUCTIONS_PATH, {})


def save_instructions(data: Dict[str, Dict[str, Any]]) -> None:
    save_json(INSTRUCTIONS_PATH, data)


def load_scheduled() -> Dict[str, Dict[str, str]]:
    return load_json(SCHEDULED_PATH, {})


def save_scheduled(data: Dict[str, Dict[str, str]]) -> None:
    save_json(SCHEDULED_PATH, data)


def load_campaigns() -> Dict[str, Dict[str, Any]]:
    return load_json(CAMPAIGNS_PATH, {})


def save_campaigns(data: Dict[str, Dict[str, Any]]) -> None:
    save_json(CAMPAIGNS_PATH, data)


def is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    authorized_chat_id = context.application.bot_data["authorized_chat_id"]
    return chat.id == authorized_chat_id


def authorized_only(
    func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]:
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not is_authorized(update, context):
            if update.effective_chat:
                await update.effective_chat.send_message("Not authorized.")
            return ConversationHandler.END
        try:
            return await func(update, context)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Command failed: %s", func.__name__)
            if update.effective_chat:
                await update.effective_chat.send_message(f"❌ Error: {exc}")
            return ConversationHandler.END

    return wrapper


def build_content(platform: str, product: str, instructions: Dict[str, Any]) -> str:
    merged = {**DEFAULT_INSTRUCTIONS, **instructions}
    tone = merged["tone"]
    fmt = merged["format"]
    target = merged["target_audience"]
    hashtags = merged["hashtags"].strip()
    include_emoji = bool(merged.get("include_emoji", True))
    emoji = " 🚀" if include_emoji else ""

    content = (
        f"Introducing {product}! Crafted for {target} with a {tone} voice. "
        f"Format: {fmt}.{emoji}"
    )
    if hashtags:
        content = f"{content}\n{hashtags}"

    max_length = int(merged.get("max_length", DEFAULT_INSTRUCTIONS["max_length"]))
    if max_length > 0:
        return content[:max_length]
    return content


async def append_post_log(
    platform: str,
    product: str,
    success: bool,
    content: str,
    detail: str,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform,
        "product": product,
        "success": success,
        "detail": detail,
        "content_preview": content[:200],
    }
    try:
        POST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with POST_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("Failed to write post log")


async def publish_to_twitter(credentials: Dict[str, str], content: str) -> str:
    def _post() -> str:
        client = tweepy.Client(
            consumer_key=credentials.get("api_key"),
            consumer_secret=credentials.get("api_secret"),
            access_token=credentials.get("access_token"),
            access_token_secret=credentials.get("access_token_secret"),
        )
        response = client.create_tweet(text=content)
        return f"tweet_id={response.data.get('id')}"

    return await asyncio.to_thread(_post)


async def publish_to_reddit(
    credentials: Dict[str, str], instructions: Dict[str, Any], content: str, product: str
) -> str:
    subreddits = instructions.get("subreddits") or []
    if isinstance(subreddits, str):
        subreddits = [x.strip() for x in subreddits.split(",") if x.strip()]
    if not subreddits:
        raise ValueError("No subreddits configured in instructions")

    post_type = (instructions.get("post_type") or "text").lower()

    def _post() -> str:
        reddit = Reddit(
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
            username=credentials.get("username"),
            password=credentials.get("password"),
            user_agent=credentials.get("user_agent", "marketingbot/1.0"),
        )
        results = []
        for subreddit_name in subreddits:
            subreddit = reddit.subreddit(subreddit_name)
            if post_type == "link":
                url = credentials.get("link_url", "https://example.com")
                submission = subreddit.submit(title=product, url=url)
            else:
                submission = subreddit.submit(title=product, selftext=content)
            results.append(f"{subreddit_name}:{submission.id}")
        return ", ".join(results)

    return await asyncio.to_thread(_post)


async def publish_to_facebook(credentials: Dict[str, str], content: str) -> str:
    token = credentials.get("access_token")
    page_id = credentials.get("page_id", "me")
    if not token:
        raise ValueError("facebook access_token is required")

    def _post() -> str:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        response = requests.post(url, data={"message": content, "access_token": token}, timeout=30)
        response.raise_for_status()
        body = response.json()
        return f"post_id={body.get('id', 'unknown')}"

    return await asyncio.to_thread(_post)


async def publish_to_instagram(credentials: Dict[str, str], content: str) -> str:
    token = credentials.get("access_token")
    user_id = credentials.get("instagram_user_id") or credentials.get("ig_user_id")
    if not token or not user_id:
        raise ValueError("instagram access_token and instagram_user_id are required")

    image_url = credentials.get("image_url")

    def _post() -> str:
        create_url = f"https://graph.facebook.com/v19.0/{user_id}/media"
        payload = {"caption": content, "access_token": token}
        if image_url:
            payload["image_url"] = image_url
        create_resp = requests.post(create_url, data=payload, timeout=30)
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")
        if not creation_id:
            raise ValueError("Instagram media creation failed: no creation ID")

        publish_url = f"https://graph.facebook.com/v19.0/{user_id}/media_publish"
        publish_resp = requests.post(
            publish_url,
            data={"creation_id": creation_id, "access_token": token},
            timeout=30,
        )
        publish_resp.raise_for_status()
        return f"creation_id={creation_id}"

    return await asyncio.to_thread(_post)


async def publish_to_linkedin(credentials: Dict[str, str], content: str) -> str:
    token = credentials.get("access_token")
    owner = credentials.get("person_urn") or credentials.get("organization_urn")
    if not token or not owner:
        raise ValueError("linkedin access_token and person_urn/organization_urn are required")

    def _post() -> str:
        url = "https://api.linkedin.com/v2/shares"
        payload = {
            "owner": owner,
            "text": {"text": content},
            "distribution": {
                "linkedInDistributionTarget": {},
            },
        }
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return "posted"

    return await asyncio.to_thread(_post)


async def publish_to_telegram_channel(
    context: ContextTypes.DEFAULT_TYPE, credentials: Dict[str, str], content: str
) -> str:
    channel_id = credentials.get("channel_id")
    if not channel_id:
        raise ValueError("telegram_channel channel_id is required")
    sent = await context.bot.send_message(chat_id=channel_id, text=content)
    return f"message_id={sent.message_id}"


async def publish_to_webhook(credentials: Dict[str, str], content: str) -> str:
    webhook_url = credentials.get("webhook_url")
    if not webhook_url:
        raise ValueError("Generic/custom platform requires webhook_url credential")

    def _post() -> str:
        response = requests.post(webhook_url, json={"text": content}, timeout=30)
        response.raise_for_status()
        return "webhook_ok"

    return await asyncio.to_thread(_post)


async def publish_post(
    context: ContextTypes.DEFAULT_TYPE,
    platform: str,
    product: str,
    content: Optional[str] = None,
) -> Dict[str, Any]:
    platform_key = platform.lower().strip()
    instructions = load_instructions().get(platform_key, DEFAULT_INSTRUCTIONS)
    credentials_map = load_credentials()
    platform_creds = credentials_map.get(platform_key, {})

    if content is None:
        content = build_content(platform_key, product, instructions)

    try:
        if platform_key in {"twitter", "x"}:
            detail = await publish_to_twitter(platform_creds, content)
        elif platform_key == "reddit":
            detail = await publish_to_reddit(platform_creds, instructions, content, product)
        elif platform_key == "facebook":
            detail = await publish_to_facebook(platform_creds, content)
        elif platform_key == "instagram":
            detail = await publish_to_instagram(platform_creds, content)
        elif platform_key == "linkedin":
            detail = await publish_to_linkedin(platform_creds, content)
        elif platform_key == "telegram_channel":
            detail = await publish_to_telegram_channel(context, platform_creds, content)
        else:
            detail = await publish_to_webhook(platform_creds, content)
        await append_post_log(platform_key, product, True, content, detail)
        return {"success": True, "detail": detail, "content": content}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to publish post to %s", platform_key)
        await append_post_log(platform_key, product, False, content, str(exc))
        return {"success": False, "detail": str(exc), "content": content}


async def scheduled_job_runner(
    application: Application, job_id: str, platform: str, product: str, chat_id: int
) -> None:
    result = await publish_post(application, platform, product)
    message = (
        f"✅ Scheduled post {job_id} sent to {platform}.\nPreview: {result['content'][:100]}"
        if result["success"]
        else f"❌ Scheduled post {job_id} failed on {platform}: {result['detail']}"
    )
    await application.bot.send_message(chat_id=chat_id, text=message)

    async with storage_lock:
        scheduled = load_scheduled()
        if job_id in scheduled:
            del scheduled[job_id]
            save_scheduled(scheduled)


def register_schedule_job(application: Application, job_id: str, payload: Dict[str, str]) -> None:
    run_date = datetime.fromisoformat(payload["scheduled_time"])
    scheduler.add_job(
        scheduled_job_runner,
        "date",
        run_date=run_date,
        id=job_id,
        kwargs={
            "application": application,
            "job_id": job_id,
            "platform": payload["platform"],
            "product": payload["product"],
            "chat_id": int(payload["chat_id"]),
        },
        replace_existing=True,
    )


@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await help_command(update, context)


@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "🤖 Marketing Bot Commands:\n"
        "/start - Welcome + command list\n"
        "/help - Show all commands\n"
        "/addcredentials <platform> <key> <value>\n"
        "/listcredentials\n"
        "/removecredentials <platform>\n"
        "/setinstructions <platform>\n"
        "/getinstructions <platform>\n"
        "/post <platform> <product_or_service>\n"
        "/schedulepost <platform> <product_or_service> <YYYY-MM-DDTHH:MM>\n"
        "/listscheduled\n"
        "/cancelscheduled <job_id>\n"
        "/campaign <campaign_name>\n"
        "/runcampaign <campaign_name>\n"
        "/listcampaigns\n"
        "/generatecontent <platform> <product_or_service>\n"
        "/approve\n"
        "/edit <new_text>\n"
        "/analytics <platform>\n"
        "/clearlog <platform>\n"
        "/status\n\n"
        "Example: /addcredentials twitter api_key ABC123"
    )
    await update.effective_chat.send_message(help_text)


@authorized_only
async def add_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 3:
        await update.effective_chat.send_message(
            "Usage: /addcredentials <platform> <key> <value>"
        )
        return

    platform, key = context.args[0].lower(), context.args[1]
    value = " ".join(context.args[2:])

    async with storage_lock:
        creds = load_credentials()
        platform_data = creds.setdefault(platform, {})
        platform_data[key] = value
        save_credentials(creds)

    await update.effective_chat.send_message(
        f"✅ Credential key '{key}' stored for platform '{platform}'."
    )


@authorized_only
async def list_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    creds = load_credentials()
    if not creds:
        await update.effective_chat.send_message("No credentials stored.")
        return

    lines = []
    for platform, keys in creds.items():
        key_list = ", ".join(sorted(keys.keys())) if isinstance(keys, dict) and keys else "(none)"
        lines.append(f"- {platform}: {key_list}")
    await update.effective_chat.send_message(
        "Stored credential keys (values hidden):\n" + "\n".join(lines)
    )


@authorized_only
async def remove_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /removecredentials <platform>")
        return

    platform = context.args[0].lower()
    async with storage_lock:
        creds = load_credentials()
        if platform not in creds:
            await update.effective_chat.send_message(f"No credentials found for {platform}.")
            return
        del creds[platform]
        save_credentials(creds)

    await update.effective_chat.send_message(f"✅ Removed credentials for {platform}.")


@authorized_only
async def set_instructions_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /setinstructions <platform>")
        return ConversationHandler.END

    platform = context.args[0].lower()
    current = {**DEFAULT_INSTRUCTIONS, **load_instructions().get(platform, {})}
    context.user_data["instr_platform"] = platform
    context.user_data["instr_data"] = current

    await update.effective_chat.send_message(
        f"Setting instructions for {platform}. Reply with tone (or 'skip')."
    )
    return INSTR_TONE


@authorized_only
async def instruction_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text.lower() != "skip":
        context.user_data["instr_data"]["tone"] = text
    await update.effective_chat.send_message("Hashtags? (or 'skip')")
    return INSTR_HASHTAGS


@authorized_only
async def instruction_hashtags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text.lower() != "skip":
        context.user_data["instr_data"]["hashtags"] = text
    await update.effective_chat.send_message("Max length? (number, or 'skip')")
    return INSTR_MAX_LENGTH


@authorized_only
async def instruction_max_length(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text.lower() != "skip":
        try:
            context.user_data["instr_data"]["max_length"] = int(text)
        except ValueError:
            await update.effective_chat.send_message("Invalid number. Keeping existing/default max_length.")
    await update.effective_chat.send_message("Include emoji? (yes/no, or 'skip')")
    return INSTR_INCLUDE_EMOJI


@authorized_only
async def instruction_include_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    if text and text != "skip":
        context.user_data["instr_data"]["include_emoji"] = text in {"yes", "y", "true", "1"}
    await update.effective_chat.send_message("Target audience? (or 'skip')")
    return INSTR_TARGET


@authorized_only
async def instruction_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text.lower() != "skip":
        context.user_data["instr_data"]["target_audience"] = text
    await update.effective_chat.send_message("Format style? (or 'skip')")
    return INSTR_FORMAT


@authorized_only
async def instruction_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text.lower() != "skip":
        context.user_data["instr_data"]["format"] = text
    await update.effective_chat.send_message(
        "Subreddits (comma-separated, for reddit; or 'skip')"
    )
    return INSTR_SUBREDDITS


@authorized_only
async def instruction_subreddits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text.lower() != "skip":
        context.user_data["instr_data"]["subreddits"] = [x.strip() for x in text.split(",") if x.strip()]
    await update.effective_chat.send_message("Post type (text/link, or 'skip')")
    return INSTR_POST_TYPE


@authorized_only
async def instruction_post_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text.lower() != "skip":
        context.user_data["instr_data"]["post_type"] = text.lower()

    platform = context.user_data.get("instr_platform")
    instr_data = context.user_data.get("instr_data", DEFAULT_INSTRUCTIONS)

    async with storage_lock:
        all_instructions = load_instructions()
        all_instructions[platform] = {**DEFAULT_INSTRUCTIONS, **instr_data}
        save_instructions(all_instructions)

    await update.effective_chat.send_message(f"✅ Instructions saved for {platform}.")
    return ConversationHandler.END


@authorized_only
async def get_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /getinstructions <platform>")
        return
    platform = context.args[0].lower()
    instructions = {**DEFAULT_INSTRUCTIONS, **load_instructions().get(platform, {})}
    await update.effective_chat.send_message(
        f"Instructions for {platform}:\n{json.dumps(instructions, indent=2)}",
    )


@authorized_only
async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.effective_chat.send_message("Usage: /post <platform> <product_or_service>")
        return
    platform = context.args[0]
    product = " ".join(context.args[1:])

    result = await publish_post(context, platform, product)
    if result["success"]:
        await update.effective_chat.send_message(
            f"✅ Posted to {platform}. Preview: {result['content'][:100]}"
        )
    else:
        await update.effective_chat.send_message(f"❌ Failed to post to {platform}: {result['detail']}")


@authorized_only
async def schedule_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 3:
        await update.effective_chat.send_message(
            "Usage: /schedulepost <platform> <product_or_service> <YYYY-MM-DDTHH:MM>"
        )
        return

    platform = context.args[0]
    scheduled_time = context.args[-1]
    product = " ".join(context.args[1:-1])

    try:
        run_at = datetime.fromisoformat(scheduled_time)
    except ValueError:
        await update.effective_chat.send_message("Invalid datetime format. Use YYYY-MM-DDTHH:MM")
        return

    if run_at <= datetime.now():
        await update.effective_chat.send_message("Scheduled time must be in the future.")
        return

    job_id = str(uuid.uuid4())
    payload = {
        "platform": platform,
        "product": product,
        "scheduled_time": run_at.isoformat(timespec="minutes"),
        "chat_id": str(update.effective_chat.id),
    }

    async with storage_lock:
        scheduled = load_scheduled()
        scheduled[job_id] = payload
        save_scheduled(scheduled)

    register_schedule_job(context.application, job_id, payload)

    await update.effective_chat.send_message(
        f"✅ Scheduled job {job_id} for {platform} at {payload['scheduled_time']}"
    )


@authorized_only
async def list_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scheduled = load_scheduled()
    if not scheduled:
        await update.effective_chat.send_message("No scheduled posts.")
        return
    lines = [
        f"- {job_id}: {job['platform']} | {job['product']} | {job['scheduled_time']}"
        for job_id, job in scheduled.items()
    ]
    await update.effective_chat.send_message("Scheduled posts:\n" + "\n".join(lines))


@authorized_only
async def cancel_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /cancelscheduled <job_id>")
        return

    job_id = context.args[0]
    removed = False
    try:
        scheduler.remove_job(job_id)
        removed = True
    except Exception:
        logger.info("Scheduled job %s not present in in-memory scheduler", job_id)

    async with storage_lock:
        scheduled = load_scheduled()
        if job_id in scheduled:
            del scheduled[job_id]
            save_scheduled(scheduled)
            removed = True

    if removed:
        await update.effective_chat.send_message(f"✅ Canceled scheduled job {job_id}.")
    else:
        await update.effective_chat.send_message(f"Job {job_id} not found.")


@authorized_only
async def campaign_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /campaign <campaign_name>")
        return ConversationHandler.END

    campaign_name = context.args[0]
    context.user_data["campaign_name"] = campaign_name
    await update.effective_chat.send_message("What product or service is this campaign for?")
    return CAMPAIGN_PRODUCT


@authorized_only
async def campaign_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["campaign_product"] = (update.message.text or "").strip()
    await update.effective_chat.send_message(
        "Which platforms? (comma-separated, e.g.: twitter,reddit,facebook)"
    )
    return CAMPAIGN_PLATFORMS


@authorized_only
async def campaign_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    platforms = [x.strip().lower() for x in (update.message.text or "").split(",") if x.strip()]
    if not platforms:
        await update.effective_chat.send_message("No platforms provided. Campaign canceled.")
        return ConversationHandler.END

    campaign_name = context.user_data["campaign_name"]
    campaign_data = {
        "name": campaign_name,
        "product": context.user_data["campaign_product"],
        "platforms": platforms,
        "status": "pending",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": {},
    }

    async with storage_lock:
        campaigns = load_campaigns()
        campaigns[campaign_name] = campaign_data
        save_campaigns(campaigns)

    await update.effective_chat.send_message(f"✅ Campaign '{campaign_name}' saved.")
    return ConversationHandler.END


@authorized_only
async def run_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /runcampaign <campaign_name>")
        return

    campaign_name = context.args[0]
    async with storage_lock:
        campaigns = load_campaigns()
        campaign = campaigns.get(campaign_name)

    if not campaign:
        await update.effective_chat.send_message(f"Campaign '{campaign_name}' not found.")
        return

    campaign["status"] = "running"
    results: Dict[str, Any] = {}
    for platform in campaign["platforms"]:
        result = await publish_post(context, platform, campaign["product"])
        results[platform] = result

    campaign["results"] = results
    campaign["status"] = "completed" if all(x["success"] for x in results.values()) else "failed"

    async with storage_lock:
        campaigns = load_campaigns()
        campaigns[campaign_name] = campaign
        save_campaigns(campaigns)

    lines = [f"Campaign '{campaign_name}' completed with status: {campaign['status']}"]
    for platform, result in results.items():
        mark = "✅" if result["success"] else "❌"
        lines.append(f"{mark} {platform}: {result['detail']}")
    await update.effective_chat.send_message("\n".join(lines))


@authorized_only
async def list_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    campaigns = load_campaigns()
    if not campaigns:
        await update.effective_chat.send_message("No campaigns saved.")
        return

    lines = []
    for name, data in campaigns.items():
        platforms = ", ".join(data.get("platforms", []))
        lines.append(f"- {name}: [{platforms}] status={data.get('status', 'unknown')}")
    await update.effective_chat.send_message("Campaigns:\n" + "\n".join(lines))


@authorized_only
async def generate_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.effective_chat.send_message(
            "Usage: /generatecontent <platform> <product_or_service>"
        )
        return

    platform = context.args[0].lower()
    product = " ".join(context.args[1:])
    instructions = load_instructions().get(platform, DEFAULT_INSTRUCTIONS)
    content = build_content(platform, product, instructions)
    context.user_data["pending_draft"] = {
        "platform": platform,
        "product": product,
        "content": content,
    }

    await update.effective_chat.send_message(
        f"📝 Draft for {platform}:\n---\n{content}\n---\nSend /approve to publish or /edit <new_text>"
    )


@authorized_only
async def approve_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    draft = context.user_data.get("pending_draft")
    if not draft:
        await update.effective_chat.send_message("No draft pending. Use /generatecontent first.")
        return

    result = await publish_post(
        context,
        platform=draft["platform"],
        product=draft["product"],
        content=draft["content"],
    )
    if result["success"]:
        await update.effective_chat.send_message(
            f"✅ Draft approved and posted to {draft['platform']}. Preview: {result['content'][:100]}"
        )
        context.user_data.pop("pending_draft", None)
    else:
        await update.effective_chat.send_message(f"❌ Failed to publish draft: {result['detail']}")


@authorized_only
async def edit_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    draft = context.user_data.get("pending_draft")
    if not draft:
        await update.effective_chat.send_message("No draft pending. Use /generatecontent first.")
        return

    if not context.args:
        await update.effective_chat.send_message("Usage: /edit <new_text>")
        return

    new_text = " ".join(context.args)
    result = await publish_post(
        context,
        platform=draft["platform"],
        product=draft["product"],
        content=new_text,
    )
    if result["success"]:
        await update.effective_chat.send_message(
            f"✅ Edited draft published to {draft['platform']}. Preview: {new_text[:100]}"
        )
        context.user_data.pop("pending_draft", None)
    else:
        await update.effective_chat.send_message(f"❌ Failed to publish edited draft: {result['detail']}")


@authorized_only
async def analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /analytics <platform>")
        return

    platform = context.args[0].lower()
    if not POST_LOG_PATH.exists():
        await update.effective_chat.send_message("No post log exists yet.")
        return

    posts_sent = 0
    success_count = 0
    last_post_date = None
    platforms_used = set()

    try:
        with POST_LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                platforms_used.add(entry.get("platform"))
                if entry.get("platform") == platform:
                    posts_sent += 1
                    if entry.get("success"):
                        success_count += 1
                    ts = entry.get("timestamp")
                    if ts and (last_post_date is None or ts > last_post_date):
                        last_post_date = ts
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to parse analytics log")
        await update.effective_chat.send_message("Failed to read analytics log.")
        return

    await update.effective_chat.send_message(
        f"Analytics for {platform}:\n"
        f"- Posts sent: {posts_sent}\n"
        f"- Successful posts: {success_count}\n"
        f"- Last post date: {last_post_date or 'N/A'}\n"
        f"- Platforms used in log: {', '.join(sorted(x for x in platforms_used if x)) or 'N/A'}"
    )


@authorized_only
async def clear_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_chat.send_message("Usage: /clearlog <platform>")
        return

    platform = context.args[0].lower()
    if not POST_LOG_PATH.exists():
        await update.effective_chat.send_message("No post log exists yet.")
        return

    kept_lines = []
    removed_count = 0

    try:
        with POST_LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("platform") == platform:
                    removed_count += 1
                else:
                    kept_lines.append(json.dumps(entry, ensure_ascii=False))

        with POST_LOG_PATH.open("w", encoding="utf-8") as handle:
            for line in kept_lines:
                handle.write(line + "\n")
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to clear log for %s", platform)
        await update.effective_chat.send_message("Failed to clear platform log.")
        return

    await update.effective_chat.send_message(
        f"✅ Cleared {removed_count} log entries for platform {platform}."
    )


@authorized_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime_seconds = int((datetime.now(timezone.utc) - START_TIME).total_seconds())
    creds = load_credentials()
    scheduled = load_scheduled()
    campaigns = load_campaigns()

    await update.effective_chat.send_message(
        "Bot status:\n"
        f"- Uptime: {uptime_seconds} seconds\n"
        f"- Credentials stored: {len(creds)} platforms\n"
        f"- Scheduled jobs: {len(scheduled)}\n"
        f"- Campaigns: {len(campaigns)}"
    )


@authorized_only
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_chat.send_message("Conversation canceled.")
    return ConversationHandler.END


async def post_init(application: Application) -> None:
    ensure_base_dir()
    get_or_create_fernet()

    if not scheduler.running:
        scheduler.start()

    now = datetime.now()
    scheduled = load_scheduled()
    dropped = 0
    for job_id, payload in list(scheduled.items()):
        try:
            run_date = datetime.fromisoformat(payload["scheduled_time"])
            if run_date <= now:
                del scheduled[job_id]
                dropped += 1
                continue
            register_schedule_job(application, job_id, payload)
        except Exception:
            logger.exception("Failed to restore scheduled job %s", job_id)
            del scheduled[job_id]
            dropped += 1

    if dropped:
        save_scheduled(scheduled)
    logger.info("Marketing bot started. Restored %d scheduled jobs.", len(scheduled))


def build_application(config: BotConfig) -> Application:
    application = Application.builder().token(config.token).post_init(post_init).build()
    application.bot_data["authorized_chat_id"] = config.authorized_chat_id

    set_instructions_conv = ConversationHandler(
        entry_points=[CommandHandler("setinstructions", set_instructions_start)],
        states={
            INSTR_TONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_tone)],
            INSTR_HASHTAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_hashtags)],
            INSTR_MAX_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_max_length)],
            INSTR_INCLUDE_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_include_emoji)],
            INSTR_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_target)],
            INSTR_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_format)],
            INSTR_SUBREDDITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_subreddits)],
            INSTR_POST_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_post_type)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    campaign_conv = ConversationHandler(
        entry_points=[CommandHandler("campaign", campaign_start)],
        states={
            CAMPAIGN_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_product)],
            CAMPAIGN_PLATFORMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_platforms)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addcredentials", add_credentials))
    application.add_handler(CommandHandler("listcredentials", list_credentials))
    application.add_handler(CommandHandler("removecredentials", remove_credentials))
    application.add_handler(set_instructions_conv)
    application.add_handler(CommandHandler("getinstructions", get_instructions))
    application.add_handler(CommandHandler("post", post_command))
    application.add_handler(CommandHandler("schedulepost", schedule_post))
    application.add_handler(CommandHandler("listscheduled", list_scheduled))
    application.add_handler(CommandHandler("cancelscheduled", cancel_scheduled))
    application.add_handler(campaign_conv)
    application.add_handler(CommandHandler("runcampaign", run_campaign))
    application.add_handler(CommandHandler("listcampaigns", list_campaigns))
    application.add_handler(CommandHandler("generatecontent", generate_content))
    application.add_handler(CommandHandler("approve", approve_draft))
    application.add_handler(CommandHandler("edit", edit_draft))
    application.add_handler(CommandHandler("analytics", analytics))
    application.add_handler(CommandHandler("clearlog", clear_log))
    application.add_handler(CommandHandler("status", status))

    return application


def main() -> None:
    setup_logging()
    try:
        config = read_config()
    except Exception as exc:  # noqa: BLE001
        logger.error("Startup failed: %s", exc)
        raise SystemExit(1) from exc

    app = build_application(config)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
