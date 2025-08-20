# webhooks.py
import time
import asyncio
import logging
from fastapi import FastAPI, Request, HTTPException
from telegram import Bot as TgBot
from sqlalchemy.exc import IntegrityError

from issabel_ami import AMIClient
from database import Session, Mask, Vendor
from utils.crypto import encrypt_text
from config import BOT_TOKEN, DIALICS_WEBHOOK_SECRET  # add DIALICS_WEBHOOK_SECRET into config.py

app = FastAPI()
ami_client = AMIClient()
tg_bot = TgBot(token=BOT_TOKEN)

logger = logging.getLogger("webhook")
logger.setLevel(logging.INFO)

async def write_astdb_mask(code: str, real_number: str):
    # use AMI to write mask and maskts
    ts = int(time.time())
    r1 = await ami_client.send_action({'Action': 'Command', 'Command': f'database put mask {code} {real_number}'})
    r2 = await ami_client.send_action({'Action': 'Command', 'Command': f'database put maskts {code} {ts}'})
    return r1, r2, ts

def generate_code(session, tries=8):
    import random
    for _ in range(tries):
        candidate = "{:04d}".format(random.randint(1000, 9999))
        if not session.query(Mask).filter(Mask.code == candidate).first():
            return candidate
    return None

@app.post("/webhook/dialics")
async def dialics_webhook(request: Request):
    # Basic secret header validation (set DIALICS_WEBHOOK_SECRET in config)
    secret = request.headers.get("X-WEBHOOK-SECRET") or request.headers.get("X-DIALICS-SECRET")
    if not DIALICS_WEBHOOK_SECRET or secret != DIALICS_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await request.json()
    caller = (payload.get("caller_number") or payload.get("caller") or payload.get("from") or "").strip()
    called = (payload.get("called_number") or payload.get("called") or payload.get("to") or "").strip()
    campaign_id = payload.get("campaign_id") or payload.get("campaign") or None
    vendor_name = payload.get("workspace") or payload.get("vendor") or None

    if not caller:
        raise HTTPException(status_code=400, detail="Missing caller_number")

    session = Session()
    try:
        code = generate_code(session)
        if not code:
            raise HTTPException(status_code=500, detail="Failed to generate unique code")

        # write to AstDB via AMI
        try:
            r1, r2, ts = await write_astdb_mask(code, caller)
        except Exception as e:
            logger.exception("AMI write failed")
            raise HTTPException(status_code=500, detail=f"AMI write failed: {e}")

        # mirror to local DB encrypted
        vendor = None
        if vendor_name:
            vendor = session.query(Vendor).filter(Vendor.vendor_name.ilike(vendor_name)).first()
        masked_alias = f"Cust •••{caller[-3:]} [{code}]"
        enc = encrypt_text(caller)
        mask_row = Mask(
            code=code,
            vendor_id=(vendor.id if vendor else None),
            campaign_id=campaign_id,
            real_number_enc=enc,
            masked_alias=masked_alias,
            created_by=None
        )
        session.add(mask_row)
        session.commit()

        # Optional: notify supervisor (set SUPERVISOR_CHAT_ID in config)
        try:
            from config import SUPERVISOR_CHAT_ID
            text = (f"🔐 New mask created\n"
                    f"Code: <code>{code}</code>\n"
                    f"Alias: <b>{masked_alias}</b>\n"
                    f"Called (tracking): <code>{called or '—'}</code>\n"
                    f"Campaign: {campaign_id or '—'}")
            await tg_bot.send_message(chat_id=SUPERVISOR_CHAT_ID, text=text, parse_mode="HTML")
        except Exception:
            logger.exception("Supervisor notify failed (non-fatal)")

        return {"ok": True, "code": code, "alias": masked_alias, "ts": ts}
    finally:
        session.close()
