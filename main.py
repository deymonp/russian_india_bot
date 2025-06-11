import logging
import asyncio
from datetime import datetime, time, timedelta
import pytz
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# === CONFIGURATION ===
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHANNEL_ID = "@your_channel_username"
TIMEZONE = pytz.timezone("Asia/Kolkata")  # Adjust as needed
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
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logging.info(f"Waiting {wait_seconds:.0f} seconds for next scheduled message at {target}")
        await asyncio.sleep(wait_seconds)

        try:
            await send_scheduled_message(bot)
        except Exception as e:
            logging.error(f"Error sending message: {e}")

# === /start COMMAND HANDLER ===
async def start(update, context):
    await update.message.reply_text("🤖 Hello! I'm your scheduled posting bot.")

# === RUN BOT ===
def run_bot():
    application = Application.builder().token(TOKEN).build()
    bot = application.bot

    application.add_handler(CommandHandler("start", start))

    async def run():
        # Start the background scheduler task
        asyncio.create_task(scheduler(bot))
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logging.info("Bot polling started.")

    # Use existing loop if present
    loop = asyncio.get_event_loop()
    loop.create_task(run())
    loop.run_forever()

# === START POINT ===
if __name__ == "__main__":
    run_bot()
