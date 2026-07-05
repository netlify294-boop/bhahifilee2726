import secrets
from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.enums import ChatMemberStatus, ParseMode, ChatAction
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,InputMediaPhoto, InputMediaVideo
from datetime import datetime, timedelta, timezone
import random, string, time, logging, os, re, asyncio, base64, urllib.parse, pytz, json,itertools
from database import *
from config import *
from plugins.route import *
from plugins.FORMAT import *
from shortzy import Shortzy
from config import *
import config
from datetime import datetime, timedelta
import pytz
from bson import ObjectId



# ---------------- COOLDOWN SYSTEM ----------------

user_access_log = {}  # user_id -> set of accessed payloads
IST = pytz.timezone("Asia/Kolkata")

# ---------- Helpers ----------
def encode(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")

def decode(s: str) -> str:
    s = s.strip()
    s += "=" * (-len(s) % 4)  # 🔥 REQUIRED
    return base64.urlsafe_b64decode(s).decode("utf-8")


async def admin_exist(user_id: int) -> bool:
    return bool(await admins_data.find_one({"_id": user_id}))

async def private_channel(client, channel_id: int) -> bool:
    chat = await client.get_chat(channel_id)
    return not chat.username

async def bot_is_admin(client, channel_id: int) -> bool:
    member = await client.get_chat_member(channel_id, client.me.id)
    return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}

async def user_in_channel(client, user_id: int, channel_id: int, req_sub: bool) -> bool:
    try:
        member = await client.get_chat_member(channel_id, user_id)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER}
    except UserNotParticipant:
        if req_sub and await private_channel(client, channel_id):
            return await reqSent_user_exist(channel_id, user_id)
        return False
    except:
        return False

async def is_userJoin(client, user_id: int, channel_id: int, REQFSUB: bool = False):
    try:
        member = await client.get_chat_member(channel_id, user_id)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER}
    except UserNotParticipant:
        return False
    except:
        return False

async def check_admin(_, __, event):
    if isinstance(event, Message) and getattr(event, "from_user", None):
        uid = event.from_user.id
    elif isinstance(event, CallbackQuery) and getattr(event, "from_user", None):
        uid = event.from_user.id
    else:return False
    
    # Returns True if owner/admin or custom function admin_exist(uid) returns True
    return uid == OWNER_ID or uid in ADMINS or await admin_exist(uid)

async def is_subscribed(_, client, m):
    uid = m.from_user.id
    if uid == OWNER_ID or await admin_exist(uid):
        return True

    channels = await get_all_channels()
    req_sub = await get_request_forcesub()

    for cid in channels or []:
        try:
            if not await user_in_channel(client, uid, cid, req_sub):
                return False
        except:
            if req_sub and await private_channel(client, cid):
                if not await reqSent_user_exist(cid, uid):
                    return False
            elif not await bot_is_admin(client, cid):
                return False
            else:
                return False
    return True

# ---------- Short Links ----------
async def get_short_link(long_url: str):
    shortener = await get_random_shortener()
    if not shortener:
        logging.warning("No shorteners set, returning raw link.")
        return long_url

    try:
        shortzy = Shortzy(api_key=shortener["key"], base_site=shortener["api"])
        return await shortzy.convert(long_url)
    except Exception as e:
        logging.error(f"Shortener failed ({shortener['api']}): {e}")
        return long_url

async def generate_verification(user_id: int, bot_username: str):
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    now = int(time.time())

    long_link = f"https://t.me/{bot_username}?start=verify_{token}"
    short_link = await get_short_link(long_link)

    await user_data.update_one(
        {"_id": user_id},
        {"$set": {
            "verify_status.verify_token": token,
            "verify_status.link": long_link,
            "verify_status.is_verified": False,
            "verify_status.verified_time": 0,
            "verify_status.created_time": now,
            "verify_status.bypass_warns": 0
        }},
        upsert=True
    )

    return token, short_link

async def generate_file_verification_link(user_id: int, file_id: str, bot_username: str):
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    now = int(time.time())

    long_link = f"https://t.me/{bot_username}?start=file_{token}"
    short_link = await get_short_link(long_link)

    await user_data.update_one(
        {"_id": user_id},
        {"$set": {
            f"file_verify.{file_id}.verify_token": token,
            f"file_verify.{file_id}.link": long_link,
            f"file_verify.{file_id}.is_verified": False,
            f"file_verify.{file_id}.verified_time": 0,
            f"file_verify.{file_id}.created_time": now,
            f"file_verify.{file_id}.bypass_warns": 0
        }},
        upsert=True
    )

    return token, short_link

async def handle_file_verification(client, message, payload: str):
    try:
        uid = message.from_user.id
        user = await user_data.find_one({"_id": uid}) or {}
        file_verify = user.get("file_verify", {})

        try:
            _, token = payload.split("_", 1)
        except:
            return await message.reply("❗ Invalid verification link.")

        matched_file = None
        for fid, data in file_verify.items():
            if data.get("verify_token") == token:
                matched_file = fid
                break

        if not matched_file:
            return await message.reply("⚠️ Token expired or invalid.")

        fv = file_verify[matched_file]
        now = int(time.time())

        created_time = fv.get("created_time")
        if not isinstance(created_time, int) or created_time <= 0:
            created_time = now
            await user_data.update_one(
                {"_id": uid},
                {"$set": {
                    f"file_verify.{matched_file}.created_time": created_time,
                    f"file_verify.{matched_file}.bypass_warns": fv.get("bypass_warns", 0)
                }}
            )

        if now > created_time + VERIFY_EXPIRE:
            return await message.reply("⚠️ Verification link expired.")

        await user_data.update_one(
            {"_id": uid},
            {"$set": {
                f"file_verify.{matched_file}.is_verified": True,
                f"file_verify.{matched_file}.verified_time": now
            }}
        )

        batch = await batches_data.find_one({"files.file_id": matched_file})
        if not batch:
            return await message.reply("❌ File not found.")

        s = await get_settings()
        protect = s.get("protect_content") and not await is_premium_user(uid)

        f_data = next(f for f in batch["files"] if f["file_id"] == matched_file)

        if f_data["type"] == "photo":
            await client.send_photo(message.chat.id, f_data["file_id"], protect_content=protect)
        elif f_data["type"] == "video":
            await client.send_video(message.chat.id, f_data["file_id"], protect_content=protect)
        else:
            await client.send_document(message.chat.id, f_data["file_id"], protect_content=protect)

    except Exception as e:
        print(f"[FILE VERIFY ERROR] {e}")
        await message.reply("❌ Something went wrong.")

async def handle_token_verification(client, message):
    uid = message.from_user.id
    user = await user_data.find_one({"_id": uid})

    if not user or "verify_status" not in user:
        return await message.reply("<b>❗ Start verification first · /start</b>")

    try:
        token = message.text.split("_", 1)[1]
    except:
        return await message.reply("<b>❗ Invalid format</b>")

    vs = user["verify_status"]
    now = int(time.time())

    # -------- AUTO FIX OLD USERS --------
    created_time = vs.get("created_time")
    if not isinstance(created_time, int) or created_time <= 0:
        created_time = now
        await user_data.update_one(
            {"_id": uid},
            {"$set": {
                "verify_status.created_time": created_time,
                "verify_status.bypass_warns": vs.get("bypass_warns", 0)
            }}
        )
        vs["created_time"] = created_time

    # -------- EXPIRY CHECK --------
    if now > created_time + VERIFY_EXPIRE:
        return await message.reply("<b>⚠️ Token expired · /start again</b>")

    # -------- TOKEN MATCH --------
    if not secrets.compare_digest(vs.get("verify_token", ""), token):
        return await message.reply("<b>⚠️ Token mismatch</b>")

    # -------- BYPASS CHECK --------
    time_diff = now - created_time
    if time_diff < 150:
        warns = vs.get("bypass_warns", 0) + 1
        await user_data.update_one(
            {"_id": uid},
            {"$set": {"verify_status.bypass_warns": warns}}
        )

        if warns >= BYPASS_LIMIT:
            await banned_users_data.update_one({"_id": uid},{"$set": {"banned": True}},upsert=True)
            return await message.reply(
                "<b>🚫 ʙʏᴘᴀss ᴅᴇᴛᴇᴄᴛᴇᴅ\n"
                "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ</b>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📩 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ", url="https://t.me/UserHelpRobot")
                ]])
            )

        return await message.reply(
            f"<b>🚨 ʙʏᴘᴀss ᴅᴇᴛᴇᴄᴛᴇᴅ\n"
            f"ᴡᴀʀɴɪɴɢ {warns}/{BYPASS_LIMIT}</b>"
        )

    # -------- SUCCESS --------
    await user_data.update_one(
        {"_id": uid},
        {"$set": {
            "verify_status.is_verified": True,
            "verify_status.verify_token": None,
            "verify_status.verified_time": now
        }}
    )

    exp = datetime.fromtimestamp(
        now + VERIFY_EXPIRE,
        tz=pytz.timezone("Asia/Kolkata")
    ).strftime("%d-%b-%Y %I:%M %p")

    await message.reply(
        f"<b>✅ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ\n"
        f"⏳ ᴠᴀʟɪᴅ ᴛɪʟʟ: <code>{exp}</code></b>"
    )

def parse_time_string(time_str: str) -> timedelta:
    days = hours = minutes = 0
    match = re.findall(r"(\d+)([dhm])", time_str.lower())
    for value, unit in match:
        value = int(value)
        if unit == "d": days += value
        elif unit == "h": hours += value
        elif unit == "m": minutes += value
    return timedelta(days=days, hours=hours, minutes=minutes)

# ---------- Referral ----------
async def handle_referral(user_id, cmd):
    if not await is_refer_enabled():
        return "<b>❌ ʀᴇғᴇʀʀᴀʟ ɪs ᴅɪsᴀʙʟᴇᴅ.</b>"
    
    ref_id = int(cmd.split("_")[1])
    if ref_id == user_id:return "<b>❌ ʏᴏᴜ ᴄᴀɴ'ᴛ ʀᴇғᴇʀ ʏᴏᴜʀsᴇʟғ.</b>"
    
    existing = await user_data.find_one({"_id": user_id})
    if existing:return "<b>❌ ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴛʜᴇ sʏsᴛᴇᴍ. ʀᴇғᴇʀʀᴀʟ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ.</b>"

    await user_data.insert_one({"_id": user_id, "referred_by": ref_id})
    s = await settings_data.find_one({"_id": "bot_settings"}) or {}
    reward = s.get("referral_reward", "1d")  # default to 1 day if not set
    await user_data.update_one({"_id": ref_id}, {"$inc": {"referrals": 1}})
    await add_premium(ref_id, delta=parse_time_string(reward))
    return "<b>✅ ʀᴇғᴇʀʀᴀʟ sᴜᴄᴄᴇssꜰᴜʟ..!</b>"

async def check_free_access(uid, client, message, mention, file_id=None):
    """Check if user can access: premium, normal verification, file-specific, or free quota."""
    try:
        s = await settings_data.find_one({"_id": "bot_settings"}) or {}
        free_mode, free_limit, usep_mode = s.get("free_mode", False), s.get("free_limit", 3), s.get("usep_mode", False)
        if free_mode:
            return True

        # Fetch or create user
        u = await user_data.find_one({"_id": uid}) or new_user(uid)
        if "_id" not in u: await user_data.insert_one(u)

        # Daily reset
        day = datetime.fromtimestamp(int(time.time()) + 19800).day
        if u.get("last_reset_day") != day:
            await user_data.update_one({"_id": uid}, {"$set": {"free_media_count": 0, "last_reset_day": day}})
            u["free_media_count"] = 0

        now = int(time.time())

        # Premium
        if u.get("premium") and (u.get("premium_expiry", 0) in (0, None) or u.get("premium_expiry", 0) > now):
            return True
        elif u.get("premium") and u.get("premium_expiry", 0) <= now:
            await user_data.update_one({"_id": uid}, {"$set": {"premium": False, "premium_expiry": 0}})

        # File-specific verification
        fv = u.get("file_verify", {}).get(file_id, {}) if usep_mode and file_id else {}
        if fv.get("is_verified") and fv.get("verified_time", 0) + VERIFY_EXPIRE > now:
            return True
        elif fv.get("is_verified"):
            await user_data.update_one({"_id": uid}, {"$unset": {f"file_verify.{file_id}": ""}})

        # Normal verification
        v = u.get("verify_status", {})
        if v.get("is_verified") and v.get("verified_time", 0) + VERIFY_EXPIRE > now:
            return True
        elif v.get("is_verified"):
            await user_data.update_one({"_id": uid}, {"$set": {"verify_status.is_verified": False, "verify_status.verified_time": 0}})

        # Free limit
        if u.get("free_media_count", 0) >= free_limit:
            wait_msg = await message.reply_text("» <b>ᴡᴀɪᴛ ᴀ sᴇᴄᴏɴᴅ ~×</b>", parse_mode=ParseMode.HTML)
            token, link = (await generate_file_verification_link(uid, file_id, client.username) if usep_mode and file_id
                           else await generate_verification(uid, client.username))
            tutorial_url = s.get("tutorial_url", "https://t.me/BotzGarage/10")
            buttons = [[InlineKeyboardButton("• ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ •", callback_data="buy_premium")]]
            if s.get("referral_mode", True):
                ref_link = f"https://t.me/{client.username}?start=refer"
                buttons.append([InlineKeyboardButton("💸 ɢᴇᴛ ᴘʀᴇᴍɪᴜᴍ ʙʏ ʀᴇꜰᴇʀʀɪɴɢ •", url=f"https://t.me/{client.username}?start=refer")])
            await wait_msg.edit_text(PREM_MSG.format(mention=mention), reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
            return False
        return True

    except Exception as e:
        print(f"[ERROR] check_free_access: {e}")
        return False


# ---------------- UTILITIES ----------------
def format_time(s: int) -> str:
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return f"{h}ʜ {m}ᴍ {s}s" if h else f"{m}ᴍ {s}s" if m else f"{s}s"


def convert_time(seconds: int) -> str:
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h}ʜ {m}ᴍ {s}s" if h else f"{m}ᴍ {s}s" if m else f"{s}s"


async def safe_delete(msg):
    try:await msg.delete()
    except:pass


# ---------------- AUTO DELETE MESSAGE ----------------
DEL_MSG = (
    "<b>⚠️ Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ Nᴏᴛɪᴄᴇ\n\n"
    "<blockquote>🕐 Tʜᴇsᴇ ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ "
    "<a href=\"https://t.me/{username}\"><b>{time}</b></a>\n\n"
    "💾 Sᴀᴠᴇ ᴛʜᴇᴍ ɴᴏᴡ ʙᴇғᴏʀᴇ ᴛʜᴇʏ'ʀᴇ ɢᴏɴᴇ !</blockquote></b>"
)


async def auto_delete(msgs, delay=600, warn=None):
    await asyncio.sleep(delay)
    for m in msgs if isinstance(msgs, (list, tuple)) else [msgs]:
        try: await safe_delete(m)
        except: pass

    if warn:
        try:
            await warn.edit("<b>✅ ᴍᴇᴅɪᴀ ᴅᴇʟᴇᴛᴇᴅ</b>")
            await asyncio.sleep(2)
            await safe_delete(warn)
        except: pass


async def auto_del_notification(bot, msg, delay, token=None):
    try:
        note = await msg.reply_text(
            DEL_MSG.format(username=bot, time=convert_time(delay)),
            disable_web_page_preview=True
        )
        await asyncio.sleep(delay)

        if token:
            link = f"https://t.me/{bot}?start={token}"
            btns = [[
                InlineKeyboardButton("♻️ Cʟɪᴄᴋ Hᴇʀᴇ", url=link),
                InlineKeyboardButton("✖️ Cʟᴏsᴇ", callback_data="close")
            ]]
            await note.edit_text(
                f"<b>Pʀᴇᴠɪᴏᴜs Mᴇssᴀɢᴇ ᴡᴀs Dᴇʟᴇᴛᴇᴅ 🗑\n<blockquote>Iғ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ɢᴇᴛ ᴛʜᴇ ғɪʟᴇs ᴀɢᴀɪɴ, ᴛʜᴇɴ <a href='{link}'>[ ♻️ Cʟɪᴄᴋ Hᴇʀᴇ ] </a> ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴇʟsᴇ ᴄʟᴏsᴇ ᴛʜɪs ᴍᴇssᴀɢᴇ.</blockquote></b>",
                reply_markup=InlineKeyboardMarkup(btns),
                disable_web_page_preview=True
            )
        else:
            await note.edit_text("<b><blockquote>🗑 Pʀᴇᴠɪᴏᴜs Mᴇssᴀɢᴇ ᴡᴀs Dᴇʟᴇᴛᴇᴅ</blockquote></b>")

        await safe_delete(msg)
    except: 
        await safe_delete(msg)

def decode_special(token: str):
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()

        start, end, channel_id = decoded.split(":")
        return int(start), int(end), int(channel_id)

    except:
        return None, None, None


async def delete_message(msg, delay_time):
    try:
        await asyncio.sleep(delay_time)
        await safe_delete(msg)
    except:pass

async def copy_msg(client, m, payload):
    asyncio.create_task(_copy_msg_worker(client, m, payload))


SEND_LIMIT = asyncio.Semaphore(5)

async def _copy_msg_worker(client, m, payload):
    async with SEND_LIMIT:
        u = m.from_user
        channel_id = CHANNEL_ID

        # -------- decode --------
        try:
            raw = decode(payload)
            if not raw.startswith("get-"):
                raise ValueError
            p = raw[4:].split("-")
            start, end = int(p[0]), int(p[1]) if len(p) > 1 else int(p[0])

        except:
            start, end, ch = decode_special(payload)

            if start is None:
                return await m.reply_text("<b>❌ ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ</b>")

            if not await is_premium_user(u.id):
                return await m.reply_text(
                    ONLY_PREM_MSG.format(mention=u.mention),
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("💎 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ", callback_data="buy_premium")]]
                    )
                )

            channel_id = ch

        if start > end:
            start, end = end, start

        # -------- settings --------
        s = await get_settings()
        premium = await is_premium_user(u.id)
        protect = s.get("protect_content") and not premium
        mode = s.get("media_send_mode", "group")

        # ✅ CHECK FREE ACCESS ONCE PER REQUEST
        if not premium:
            if not await check_free_access(u.id, client, m, u.mention):
                return

            # ✅ Increment free count ONCE
            await user_data.update_one({"_id": u.id},{"$inc": {"free_media_count": 1}})

            user_data_updated = await user_data.find_one({"_id": u.id})
            used = user_data_updated.get("free_media_count", 0)
            free_limit = s.get("free_limit", 3)
            remaining = max(0, free_limit - used)

            # text = f"<b>🆓 ғɪʟᴇ ᴀᴄᴄᴇssᴇᴅ:</b> {used}\n\n"
            text = f"<b>🆓 𝖸𝖮𝖴 𝖧𝖠𝖵𝖤 𝖠𝖢𝖢𝖤𝖲𝖲𝖤𝖣 𝖳𝖧𝖨𝖲 𝖯𝖮𝖲𝖳 𝖥𝖮𝖱 𝖥𝖱𝖤𝖤\n\n</b>"
            buttons = [[InlineKeyboardButton(f"🆓 {used} 𝖥𝖨𝖫𝖤𝖲 𝖠𝖢𝖢𝖤𝖲𝖲𝖤𝖣", callback_data="buy_premium")]]
            await m.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


        btn = s.get("custom_btn", {})
        buttons = []

        if s.get("copy_reply_btn") and btn.get("text"):
            buttons.append([InlineKeyboardButton(btn["text"], url=btn["url"])])
        # if not premium:
        #     buttons.append([InlineKeyboardButton("⬇️ ᴅᴏᴡɴʟᴏᴀᴅ ⬇️", callback_data="buy_premium")])

        markup = InlineKeyboardMarkup(buttons) if buttons else None

        def cap(c):
            if s.get("caption_mode") == "hide":
                return ""
            if s.get("caption_mode") == "custom" and s.get("custom_caption"):
                return s["custom_caption"].format(previouscaption=c or "")
            return c or ""

        sent, album = [], []
        stats = {"photo": 0, "video": 0, "doc": 0}

        async def flush():
            if not album:
                return
            try:
                if mode == "group":
                    media = [
                        (InputMediaPhoto if i["t"] == "photo" else InputMediaVideo)(
                            i["id"],
                            caption=cap(i["c"]) if n == 0 else None
                        )
                        for n, i in enumerate(album)
                    ]

                    sent.extend(await client.send_media_group(
                        m.chat.id,
                        media,
                        protect_content=protect
                    ))
                else:
                    sent.extend(await asyncio.gather(*[
                        getattr(client, f"send_{i['t']}")(
                            m.chat.id,
                            i["id"],
                            caption=cap(i["c"]),
                            protect_content=protect,
                            reply_markup=markup
                        )
                        for i in album
                    ]))

                for i in album:
                    stats[i["t"]] += 1

            except FloodWait as e:
                await asyncio.sleep(e.value)

            album.clear()

        # -------- fetch --------
        msgs = await client.get_messages(channel_id, message_ids=range(start, end + 1))

        if not msgs:
            return await m.reply_text("<b>❌ ɴᴏ ғɪʟᴇs ғᴏᴜɴᴅ</b>")

        for msg in msgs:
            if not msg or not msg.media:
                continue

            try:
                fid = (
                    msg.photo.file_id if msg.photo else
                    msg.video.file_id if msg.video else
                    msg.animation.file_id if msg.animation else
                    msg.document.file_id if msg.document else None
                )

                if not fid:
                    continue

                if msg.photo or msg.video:
                    album.append({
                        "id": fid,
                        "t": "photo" if msg.photo else "video",
                        "c": msg.caption
                    })

                    if len(album) == 10:
                        await flush()

                elif msg.animation:
                    await flush()
                    sent.append(await client.send_animation(
                        m.chat.id,
                        fid,
                        caption=cap(msg.caption),
                        protect_content=protect,
                        reply_markup=markup
                    ))
                    stats["video"] += 1

                else:
                    await flush()
                    sent.append(await client.send_document(
                        m.chat.id,
                        fid,
                        protect_content=protect,
                        reply_markup=markup
                    ))
                    stats["doc"] += 1

            except FloodWait as e:
                await asyncio.sleep(e.value)

        await flush()

        # -------- stats --------
        await asyncio.gather(
            increment_stat("images_downloaded", stats["photo"]),
            increment_stat("videos_downloaded", stats["video"]),
            increment_stat("documents_downloaded", stats["doc"]),
        )

        # -------- auto delete --------
        if not premium and s.get("auto_delete_on") and sent:
            t = s.get("auto_delete", 600)
            asyncio.create_task(auto_delete(sent, t))
            asyncio.create_task(auto_del_notification(client.username, m, t, payload))


LINK = re.compile(r"https://t\.me/\S+")

async def send_bhooki(c, m, payload, db_channel_id=None):
    uid = m.from_user.id
    try:
        d = base64.urlsafe_b64decode(payload.replace("bhookibhabhi_", "") + "==").decode()
        chat_id, a, b = map(int, d.split(":"))
    except:return await m.reply_text("<b>❌ ɪɴᴠᴀʟɪᴅ ᴏʀ ᴄᴏʀʀᴜᴘᴇᴅ ʟɪɴᴋ · ɪғ ɪssᴜᴇ ᴄᴏɴᴛɪɴᴜᴇ ᴍsɢ <a href='https://t.me/salesgodx'>@salesgodx</a></b>", parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    sent = []

    async def send(mid):
        try:
            src = await c.get_messages(chat_id, mid)
            text = src.text or src.caption or ""
            link = LINK.search(text)

            msg = await c.copy_message(uid, chat_id, mid)

            if link:await msg.edit_reply_markup(InlineKeyboardMarkup([[InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɴᴏᴡ •", url=link.group())]]))

            sent.append(msg)

        except FloodWait as e:await asyncio.sleep(e.value); await send(mid)
        except:pass

    for i in range(a, b + 1, 10):await asyncio.gather(*(send(x) for x in range(i, min(i + 10, b + 1))))

    return len(sent)


async def get_video_info(video_path: str):
    try:
        process = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams",
            video_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await process.communicate()
        if process.returncode == 0:
            data = json.loads(stdout.decode())
            video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
            if video_stream:
                duration = float(data.get('format', {}).get('duration', 0))
                width = int(video_stream.get('width', 0))
                height = int(video_stream.get('height', 0))
                return {'duration': int(duration), 'width': width, 'height': height}
        return {'duration': 0, 'width': 0, 'height': 0}
    except Exception as e:
        logging.error(f"Video info error: {e}")
        return {'duration': 0, 'width': 0, 'height': 0}


async def increment_stat(stat_name, count=1):
    """Increment bot stats for each file type."""
    if count <= 0:
        return

    await settings_data.update_one(
        {"_id": "bot_stats"},
        {"$inc": {stat_name: count}},
        upsert=True
    )


async def check_banUser(_, __, update):
    try:return bool(await banned_users_data.find_one({"_id": update.from_user.id}))
    except:return False
    
# ---------------- Pyrogram Filters ----------------
is_admin = filters.create(check_admin)
subscribed = filters.create(is_subscribed)
is_ban = filters.create(check_banUser)

@Client.on_message(~is_admin & filters.command(ADMIN_CMD))
async def admin_block(client, message):
    await message.reply_text("<blockquote><b>💀 ᴀᴅᴍɪɴ ᴏɴʟʏ..!</b></blockquote>",parse_mode=ParseMode.HTML,message_effect_id=5046589136895476101)