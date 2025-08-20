from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown
from config import DIALICS_API_KEY
from config import BOT_TOKEN, ROLES, COMMAND_PERMISSIONS
from database import Session, CommandLog, Vendor
from ami_client import AMIClient
from dialics_client import DialicsClient
from sqlalchemy import text
import logging
import re


# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Client Initialization ---
ami_client = AMIClient()
dialics_client = DialicsClient()

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

# @role_required("health")
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple health check for AMI + DB"""
    user_id = update.effective_user.id

    # --- Check AMI ---
    ami_status = "❌"
    try:
        result = await ami_client.connect()
        if result:
            ami_status = "✅"
    except Exception as e:
        ami_status = f"❌ ({str(e)})"

    # --- Check DB ---
    db_status = "❌"
    try:
        session = Session()
        session.execute(text("SELECT 1"))
        session.close()
        db_status = "✅"
    except Exception as e:
        db_status = f"❌ ({str(e)})"

    response = (
    f"📊 <b>Health Check</b>\n\n"
    f"AMI: {ami_status}\n"
    f"DB: {db_status}\n"
    )
    await update.message.reply_text(response, parse_mode="HTML")

    _log_command(user_id, "health", "success", raw_response=response)

@role_required("sipstatus")
async def sipstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Performs a live SIP status check for all peers and sorts them."""
    user_id = update.effective_user.id
    await update.message.reply_text("Running live SIP peer status check...")

    # CORRECTED: Directly await the asynchronous function
    raw_response = await ami_client.send_action({'Action': 'SIPpeers'})

    if "Error:" in raw_response:
        error_msg = escape_markdown(raw_response)
        await update.message.reply_text(f"❌ *AMI Connection Failed*\n`{error_msg}`", parse_mode="MarkdownV2")
        _log_command(user_id, "sipstatus", "ami_error", raw_response=raw_response)
        return

    peers = re.findall(r'Event: PeerEntry\s*(.*?)\s*(?=Event: PeerEntry|Event: PeerlistComplete)', raw_response, re.DOTALL)
    
    reg_trunks = []
    unreg_trunks = []
    reg_exts = []
    unreg_exts = []
    
    for peer_data in peers:
        name_match = re.search(r'ObjectName: (\S+)', peer_data)
        status_match = re.search(r'Status: (.*)', peer_data)
        
        if name_match and status_match:
            name_str = name_match.group(1)
            status_str = status_match.group(1).strip()
            
            is_extension = name_str.isdigit()

            if is_extension:
                if "OK" in status_str:
                    reg_exts.append(f"  ✅ `{escape_markdown(name_str)}`")
                else:
                    unreg_exts.append(f"  ❌ `{escape_markdown(name_str)}` \\(Status: {escape_markdown(status_str)}\\)")
            else:
                if "OK" in status_str:
                    reg_trunks.append(f"  ✅ `{escape_markdown(name_str)}`")
                else:
                    unreg_trunks.append(f"  ❌ `{escape_markdown(name_str)}` \\(Status: {escape_markdown(status_str)}\\)")

    response_parts = ["📊 *Live SIP Peer Status*\n"]
    if reg_trunks:
        response_parts.append("*Registered Trunks:*\n" + "\n".join(reg_trunks))
    if unreg_trunks:
        response_parts.append("*Unregistered Trunks:*\n" + "\n".join(unreg_trunks))
    if reg_exts:
        response_parts.append("*Registered Extensions:*\n" + "\n".join(reg_exts))
    if unreg_exts:
        response_parts.append("*Unregistered Extensions:*\n" + "\n".join(unreg_exts))

    if len(response_parts) == 1:
        response_parts.append("No SIP peers found.")

    response_message = "\n\n".join(response_parts)
    
    await update.message.reply_text(response_message, parse_mode="MarkdownV2")
    _log_command(user_id, "sipstatus", "success", raw_response=f"Found {len(peers)} peers.")

@role_required("status")
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dialics vendor status:
    - Resolves vendor from DB (by name arg or single vendor fallback)
    - Pings Dialics via DialicsClient
    - Attempts to fetch campaign KPIs if campaign_id is present (graceful fallback)
    """
    user_id = update.effective_user.id
    session = Session()
    try:
        # Resolve vendor
        args = context.args if hasattr(context, "args") else []
        vendor_arg = args[0] if args else None

        if vendor_arg:
            vendor = session.query(Vendor).filter(Vendor.vendor_name.ilike(vendor_arg)).first()
            if not vendor:
                await update.message.reply_text(
                    f"<b>Vendor not found:</b> {vendor_arg}",
                    parse_mode="HTML",
                )
                _log_command(user_id, "status", "not_found", raw_response=vendor_arg)
                return
        else:
            vendors = session.query(Vendor).all()
            if not vendors:
                await update.message.reply_text(
                    "No vendors found. Use <code>/addvendor</code> to register one.",
                    parse_mode="HTML",
                )
                _log_command(user_id, "status", "no_vendors")
                return
            if len(vendors) > 1:
                listing = "\n".join([f" • {v.vendor_name} (campaign: {v.campaign_id or '—'})" for v in vendors])
                await update.message.reply_text(
                    f"<b>Multiple vendors found.</b>\nUse <code>/status &lt;vendor_name&gt;</code>\n\n{listing}",
                    parse_mode="HTML",
                )
                _log_command(user_id, "status", "ambiguous")
                return
            vendor = vendors[0]

        # Dialics connectivity + KPI (graceful)
        dialics_ok = False
        dialics_note = ""
        kpi_line = "KPI: —"

        try:
            ping_info = await dialics_client.ping()  # should return dict like {"ok": True, "workspaces": N}
            dialics_ok = bool(ping_info and ping_info.get("ok"))
            if dialics_ok and "workspaces" in ping_info:
                dialics_note = f" (workspaces: {ping_info['workspaces']})"
        except Exception as e:
            dialics_note = f" (error: {str(e)})"

        # Attempt KPI pull if campaign_id present (method should be implemented in DialicsClient)
        if getattr(vendor, "campaign_id", None):
            try:
                kpi = await dialics_client.get_campaign_kpis(vendor.campaign_id)
                if kpi:
                    # Expect keys; handle missing keys gracefully
                    asr = kpi.get("asr")
                    acd = kpi.get("acd")
                    leads = kpi.get("leads") or kpi.get("lead_count")
                    parts = []
                    if asr is not None: parts.append(f"ASR {asr}%")
                    if acd is not None: parts.append(f"ACD {acd}s")
                    if leads is not None: parts.append(f"Leads {leads}")
                    if parts:
                        kpi_line = "KPI: " + ", ".join(parts)
            except Exception as e:
                kpi_line = f"KPI: error ({str(e)})"

        # Compose response
        dialics_icon = "✅" if dialics_ok else "❌"
        response = (
            f"📊 <b>Vendor Status</b>\n"
            f"<b>Vendor:</b> {vendor.vendor_name}\n"
            f"<b>Campaign:</b> {vendor.campaign_id or '—'}\n"
            f"<b>Test DID:</b> {vendor.test_did or '—'}\n"
            f"<b>Dialics:</b> {dialics_icon}{dialics_note}\n"
            f"{kpi_line}\n"
        )

        await update.message.reply_text(response, parse_mode="HTML")
        _log_command(user_id, "status", "success", raw_response=response)

    except Exception as e:
        logging.error(f"/status error: {e}")
        await update.message.reply_text(
            f"❌ <b>Status failed:</b> {str(e)}",
            parse_mode="HTML",
        )
        _log_command(user_id, "status", "error", raw_response=str(e))
    finally:
        session.close()
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
    application.add_handler(CommandHandler("sipstatus", sipstatus))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("testlog", testlog))
    # application.add_handler(CommandHandler("mocksip", mock_sip))
    application.add_handler(CommandHandler("myrole", myrole))
    application.add_handler(CommandHandler("health", health))

    # Start bot
    application.run_polling()

if __name__ == "__main__":
    main()