from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS
from database import Session, CommandLog
import logging

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized access")
        return

    await update.message.reply_text(
        "🚀 SIP Monitor Active\n"
        "Commands:\n"
        "/start - Show this menu\n"
        "/siptest - Test SIP connectivity",
        reply_markup=ReplyKeyboardRemove()
    )
    _log_command(user_id, "start", "success")

async def siptest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return

    # Dummy SIP test response
    response = "✅ SIP Test Result:\nTrunk: MockTrunk_01\nStatus: REGISTERED\nRTT: 42ms"
    await update.message.reply_text(response)
    _log_command(user_id, "siptest", "mock_ok")

async def testlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Temporary test command for logging"""
    _log_command(
        user_id=update.effective_user.id,
        command="testlog",
        status="success",
        duration_ms=150,
        trunk_id="Trunk_US_02",
        raw_response={"mock": "data", "rtt": 47}
    )
    await update.message.reply_text("✅ Test log written")

def _log_command(
    user_id: int,
    command: str,
    status: str,
    duration_ms: int = 0,
    trunk_id: str = "MOCK_TRUNK",
    error_code: str = None,
    raw_response: str = None
):
    session = Session()
    try:
        log_entry = CommandLog(
            user_id=user_id,
            command=command,
            status=status,
            duration_ms=duration_ms,
            trunk_id=trunk_id,
            error_code=error_code,
            raw_response=str(raw_response)[:1000]  # Truncate to prevent overflow
        )
        session.add(log_entry)
        session.commit()
    except Exception as e:
        logging.error(f"DB Write Failed: {str(e)}")
    finally:
        session.close()

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("siptest", siptest))
    application.add_handler(CommandHandler("testlog", testlog))

    # Start bot
    application.run_polling()

if __name__ == "__main__":
    main()