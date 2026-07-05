import asyncio, random, time, base64
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import *
from helper import *

COOLDOWN, user_locks, user_cooldowns = 2, {}, {}
CUSTOM_CAPTION = '<b>• ʙʏ <a href="https://t.me/bhookibhabhi">@ʙʜᴀʙʜɪ</a> 🔥</b>'

# ---------------- random video ----------------
async def get_random_video():
    # find batches containing videos
    pipeline = [
        {"$unwind": "$files"},
        {"$match": {"files.type": "video"}},
        {"$sample": {"size": 1}}
    ]
    doc = await batches_data.aggregate(pipeline).to_list(1)
    if not doc: return None
    return doc[0]["files"]["file_id"]

@Client.on_message(filters.command("video") | filters.regex(r"(?i)^video(?: 🥵)?$"))
async def random_video(client, m):
    if not m.from_user:
        return
    uid = m.from_user.id

    # ---------------- BANNED CHECK ----------------
    if await banned_users_data.find_one({"_id": uid}):
        return await m.reply_text("⚠️ ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ..!")

    # ---------------- FETCH USER ----------------
    user = await user_data.find_one({"_id": uid})
    now = int(time.time())

    # ---------------- PREMIUM EXPIRY CHECK ----------------
    if user and user.get("premium", False):
        premium_expiry = user.get("premium_expiry", 0)
        if premium_expiry not in (0, None) and premium_expiry <= now:
            # Mark premium as expired
            await user_data.update_one(
                {"_id": uid},
                {"$set": {"premium": False, "premium_expiry": 0}}
            )
            user["premium"] = False  # update local copy

    # ---------------- DENY ACCESS IF NOT PREMIUM ----------------
    if not user or not user.get("premium", False):
        pm_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("• ɢᴇᴛ ᴘʀᴇᴍɪᴜᴍ •", callback_data="buy_premium")]
        ])
        return await m.reply_text(
            "<b>🔓 ᴏɴʟʏ ғᴏʀ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀs.</b>",
            reply_markup=pm_btn
        )

    # ---------------- COOLDOWN ----------------
    if uid in user_cooldowns and time.time() - user_cooldowns[uid] < COOLDOWN:
        return await m.reply_text("<b>⚠️ ᴅᴏɴ'ᴛ sᴘᴀᴍ..!</b>")

    user_cooldowns[uid] = time.time()

    # ---------------- SEND RANDOM VIDEO ----------------
    file_id = await get_random_video()
    if not file_id:
        return await m.reply_text("⚠️ ɴᴏ ᴠɪᴅᴇᴏ ᴀᴠᴀɪʟᴀʙʟᴇ")

    await send_with_caption(file_id, m.chat.id, client, uid, "video")



CUSTOM_CAPTION = '<b>• ʙʏ <a href="https://t.me/bhookibhabhi">@ʙʜᴀʙʜɪ</a> 🔥</b>'

async def send_with_caption(file_id, chat_id, client, uid, media_type="photo"):
    s = await get_settings()
    btn = s.get("custom_btn", {})
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn["text"], url=btn["url"])]]) \
            if s.get("copy_reply_btn") and btn.get("text") else None

    if media_type == "photo":
        sent = await client.send_photo(
            chat_id,
            file_id,
            caption=CUSTOM_CAPTION,
            reply_markup=markup,
            protect_content=s.get("protect_content", False)
        )
    elif media_type == "video":
        sent = await client.send_video(
            chat_id,
            file_id,
            caption=CUSTOM_CAPTION,
            reply_markup=markup,
            protect_content=s.get("protect_content", False)
        )
    else:
        return

    # update stats
    await settings_data.update_one(
        {"_id": "bot_stats"},
        {"$inc": {f"{media_type}s_sent": 1}},
        upsert=True
    )
