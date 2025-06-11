import logging
import requests
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz
import os
import asyncio

# === CONFIGURATION ===
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7818282877:AAFEuuksW8xjH111cRFOv2iTm8bZjqjpWh4")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "-1002850808376")
SHEET_CSV_URL = 'https://docs.google.com/spreadsheets/d/1LY8Gv6ZTn0XGEiFxmSy5AU9CVv7F6CnArZeTCKIVCh4/export?format=csv&gid=0'
MOSCOW_TIMEZONE = 'Europe/Moscow'
SCHEDULED_TIMES_MOSCOW = [
    (10, 29),
    (10, 30),
    (10, 31),
    (10, 32)
]
SHEET_RELOAD_INTERVAL_HOURS = 6

# === LOGGING SETUP ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === GLOBAL VARIABLES ===
all_messages = []
current_message_index = 0

def convert_drive_link(link):
    if isinstance(link, str) and "drive.google.com" in link:
        parts = link.split('/')
        try:
            file_id_index = parts.index('d') + 1
            file_id = parts[file_id_index]
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        except (ValueError, IndexError):
            logger.warning(f"Could not parse Google Drive link: {link}")
            return None
    return link

def load_messages_from_sheet():
    global all_messages
    global current_message_index
    try:
        df = pd.read_csv(SHEET_CSV_URL, on_bad_lines='skip')
        messages = []
        for _, row in df.iterrows():
            text = str(row['Text']).strip()
            raw_url = str(row['ImageURL']).strip() if 'ImageURL' in row and pd.notna(row['ImageURL']) else None
            image_url = convert_drive_link(raw_url)
            if text:
                messages.append((text, image_url))

        if not messages:
            logger.warning("No messages found in sheet! Bot will not send messages.")
            all_messages = []
        else:
            if all_messages and len(messages) == len(all_messages) and all(messages[i] == all_messages[i] for i in range(len(messages))):
                logger.info("Messages from sheet are unchanged. Keeping current_message_index.")
            else:
                current_message_index = 0
                logger.info("Messages from sheet have changed or are new. Resetting current_message_index to 0.")

            all_messages = messages
            logger.info(f"Successfully loaded {len(all_messages)} messages from Google Sheet.")

    except Exception as e:
        logger.error(f"❌ Failed to read Google Sheet: {e}")
        all_messages = []

async def send_telegram_message(text, image_url=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    try:
        if image_url and image_url.startswith("http"):
            response = requests.post(f"{url}/sendPhoto", data={
                'chat_id': CHANNEL_ID,
                'caption': text,
                'photo': image_url
            })
        else:
            response = requests.post(f"{url}/sendMessage", data={
                'chat_id': CHANNEL_ID,
                'text': text
            })
        response.raise_for_status()
        logger.info(f"✅ Sent message to channel. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Telegram send error: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error sending message: {e}")

async def send_scheduled_message_from_sheet():
    global current_message_index
    if not all_messages:
        logger.warning("No messages loaded to send. Attempting to reload messages from sheet.")
        load_messages_from_sheet()
        if not all_messages:
            logger.error("Still no messages after reload. Skipping sending this time.")
            return
    try:
        text, image_url = all_messages[current_message_index]
        await send_telegram_message(text, image_url)
        current_message_index = (current_message_index + 1) % len(all_messages)
    except IndexError:
        logger.error("Message index out of bounds. Resetting index to 0.")
        current_message_index = 0
    except Exception as e:
        logger.error(f"Error sending scheduled message: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    scheduled_times_str = ", ".join([f"{h:02d}:{m:02d}" for h, m in SCHEDULED_TIMES_MOSCOW])
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I am a bot designed to send daily messages "
        f"at the following Moscow times: <b>{scheduled_times_str}</b> to the configured channel.\n"
        f"I also reload messages from the Google Sheet every <b>{SHEET_RELOAD_INTERVAL_HOURS} hours</b>.\n"
        "Use /check_messages to manually reload messages.\n"
        "Use /current_index to see which message will be sent next."
    )

async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Attempting to reload messages from the Google Sheet...")
    load_messages_from_sheet()
    if all_messages:
        await update.message.reply_text(f"Successfully reloaded {len(all_messages)} messages.")
    else:
        await update.message.reply_text("Failed to reload messages or no messages found.")

async def current_index(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if all_messages:
        await update.message.reply_text(
            f"Currently, the bot will send message number {current_message_index + 1} "
            f"out of {len(all_messages)} total messages."
        )
    else:
        await update.message.reply_text("No messages are currently loaded.")

async def main() -> None:
    load_messages_from_sheet()
    application = Application.builder().token(BOT_TOKEN).build()
    scheduler = AsyncIOScheduler()

    for hour, minute in SCHEDULED_TIMES_MOSCOW:
        job_id = f'daily_message_{hour:02d}_{minute:02d}'
        scheduler.add_job(
            send_scheduled_message_from_sheet,
            CronTrigger(hour=hour, minute=minute, timezone=MOSCOW_TIMEZONE),
            id=job_id,
            name=f'Send message at {hour:02d}:{minute:02d} Moscow time'
        )
        logger.info(f"Scheduled job: {job_id} for {hour:02d}:{minute:02d} {MOSCOW_TIMEZONE}")

    scheduler.add_job(
        load_messages_from_sheet,
        IntervalTrigger(hours=SHEET_RELOAD_INTERVAL_HOURS),
        id='reload_sheet_messages',
        name=f'Reload messages from Google Sheet every {SHEET_RELOAD_INTERVAL_HOURS} hours'
    )
    logger.info(f"Scheduled job: reload_sheet_messages every {SHEET_RELOAD_INTERVAL_HOURS} hours.")

    scheduler.start()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check_messages", check_messages))
    application.add_handler(CommandHandler("current_index", current_index))

    logger.info("Bot started. Press Ctrl+C to stop.")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

    scheduler.shutdown()
    logger.info("Bot stopped.")

# === ENTRY POINT ===
if __name__ == "__main__":
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except RuntimeError as e:
        if str(e).startswith("This event loop is already running"):
            logger.info("Using create_task because loop is already running.")
            asyncio.create_task(main())
        else:
            raise
