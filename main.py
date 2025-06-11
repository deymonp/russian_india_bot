import logging
import asyncio
from datetime import datetime, time
import pytz
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# === CONFIGURATION ===
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHANNEL_ID = "@your_channel_username"
TIMEZONE = pytz.timezone("Asia/Kolkata")  # Moscow time = Asia/Kolkata + 2h if needed
POST_HOUR = 12
POST_MINUTE = 0

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === SCHEDULED MESSAGE FUNCTION ===
async def send_scheduled_message(bot: Bot):
    message = "🌟 Scheduled message from your Telegram bot!"
    await bot.send_message(chat_id=CHANNEL_ID, text=message)
    logging.info("Scheduled message sent.")

# === SCHEDULER ===
async def scheduler(bot: Bot):
    while True:
        now = datetime.now(TIMEZONE)
        target = datetime.combine(now.date(), time(POST_HOUR, POST_MINUTE, tzinfo=TIMEZONE))
        
        if now >= target:
            target = datetime.combine((now + pytz.timedelta(days=1)).date(), time(POST_HOUR, POST_MINUTE, tzinfo=TIMEZONE))

        wait_time = (target - now).total_seconds()
        logging.info(f"Waiting {wait_time / 60:.2f} minutes for next post at {target}")
        await asyncio.sleep(wait_time)

        try:
            await send_scheduled_message(bot)
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

# === /start COMMAND HANDLER ===
async def start(update, context):
    await update.message.reply_text("🤖 Hello! I'm your scheduled posting bot.")

# === MAIN ENTRY POINT ===
async def main():
    bot = Bot(token=TOKEN)
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    # Start the scheduler task
    asyncio.create_task(scheduler(bot))

    # Start bot polling
    logging.info("Bot started. Press Ctrl+C to stop.")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
