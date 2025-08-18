from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown

from config import BOT_TOKEN, ROLES, COMMAND_PERMISSIONS
from database import Session, CommandLog, Vendor
from ami_client import AMIClient
from dialics_client import DialicsClient
import logging
import re

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

ami_client = AMIClient()
def role_required(command_name: str):
    """Decorator to check user roles before executing a command."""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            user_roles = ROLES.get(user_id, [])
            if not isinstance(user_roles, list):
                user_roles = [user_roles]

            allowed_roles = [
                role for role, commands in COMMAND_PERMISSIONS.items()
                if command_name in commands
            ]

            has_access = any(role in allowed_roles for role in user_roles)

            if not allowed_roles:
                logging.error(f"No permissions configured for command: {command_name}")
                await update.message.reply_text("⚠️ System configuration error")
                return

            if not has_access:
                _log_command(user_id, command_name, "unauthorized", user_roles=str(user_roles))
                await update.message.reply_text(
                    f"⛔ Access Denied\n"
                    f"Required roles: {', '.join(allowed_roles)}\n"
                    f"Your roles: {', '.join(user_roles) or 'None'}"
                )
                return

            return await func(update, context)
        return wrapper
    return decorator

# --- Command Handlers ---

@role_required("start")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the main menu with available commands based on the user's roles."""
    user_id = update.effective_user.id
    user_roles = ROLES.get(user_id, [])
    
    permissions = set()
    for role in user_roles:
        permissions.update(COMMAND_PERMISSIONS.get(role, []))

    command_list = "\n".join([f"  • /{escape_markdown(cmd)}" for cmd in sorted(permissions)])
    response = (
        f"🚀 *ChaturBot SIP Monitor*\n\n"
        f"Here are your available commands:\n"
        f"{command_list}"
    )
    
    await update.message.reply_text(response, reply_markup=ReplyKeyboardRemove(), parse_mode="MarkdownV2")
    _log_command(user_id, "start", "success", user_roles=str(user_roles))

@role_required("siptest")
async def siptest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dummy SIP test response."""
    user_id = update.effective_user.id
    # The redundant access check has been removed as the decorator handles it.
    response = "✅ SIP Test Result:\nTrunk: MockTrunk_01\nStatus: REGISTERED\nRTT: 42ms"
    await update.message.reply_text(response)
    _log_command(user_id, "siptest", "mock_ok")

@role_required("mocksip")
async def mock_sip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simulate SIP call with random results"""
    user_id = update.effective_user.id
    
    # Mock SIP metrics
    status = random.choice(["REGISTERED", "TIMEOUT", "AUTH_FAIL"])
    duration_ms = random.randint(50, 500)
    trunk = f"Trunk_{random.choice(['EU','US','ASIA'])}_01"
    
    _log_command(
        user_id=user_id,
        command="mock_sip",
        status=status,
        duration_ms=duration_ms,
        trunk_id=trunk,
        raw_response=f"Code: {random.randint(200, 600)} | RTT: {duration_ms}ms"
    )
    
    await update.message.reply_text(
        f"📞 Mock SIP Result:\n"
        f"Status: {status}\n"
        f"Trunk: {trunk}\n"
        f"Duration: {duration_ms}ms"
    )

# This command is temporary and will be removed later.
@role_required("system")
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

# This command is for debugging roles and is good to keep.
async def myrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the user's roles and permissions."""
    user_id = update.effective_user.id
    user_roles = ROLES.get(user_id, ["unauthorized"])
    
    permissions = set()
    for role in user_roles:
        if role in COMMAND_PERMISSIONS:
            permissions.update(COMMAND_PERMISSIONS[role])
    
    response = (
        f"<b>👤 User ID</b>: <code>{user_id}</code>\n"
        f"<b>🏷️ Your Roles</b>: {', '.join(user_roles) or 'None'}\n"
        f"<b>🔑 Permissions:</b>\n"
    )
    
    for cmd in sorted(permissions):
        response += f"  • /{cmd}\n"
    
    await update.message.reply_text(
        response,
        parse_mode="HTML"
    )
    _log_command(user_id, "myrole", "success")

def _log_command(
    user_id: int,
    command: str,
    status: str,
    duration_ms: int = None, # Made nullable as not all commands have duration
    trunk_id: str = None, # Made nullable as not all commands are for trunks
    error_code: str = None,
    raw_response: str = None,
    user_roles: str = "unauthorized"
):
    """
    Logs a command execution to the database.
    This function has been slightly modified for robustness.
    """
    session = Session()
    try:
        log_entry = CommandLog(
            user_id=user_id,
            user_role = user_roles,
            command=command,
            status=status,
            duration_ms=duration_ms,
            trunk_id=trunk_id,
            error_code=error_code,
            raw_response=str(raw_response)[:1000]
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
    application.add_handler(CommandHandler("mocksip", mock_sip))
    application.add_handler(CommandHandler("myrole", myrole))

    # Start bot
    application.run_polling()

if __name__ == "__main__":
    main()
