import time, io, qrcode, aiohttp, datetime as dl, pytz as pt,asyncio as asn
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, CallbackQuery,Message
from config import *
from database import *
from plugins.FORMAT import *
from helper import is_admin
from plugins.admin import *
from collections import defaultdict

# ---------------- Settings ----------------
async def get_settings():
    s = await settings_data.find_one({"_id": "bot_settings"})
    if not s:
        s = {"protect_content": False, "auto_delete": 600,
             "auto_delete_on": False, "caption_mode": "original",
             "custom_caption": "", "custom_btn": {"text": "", "url": ""}}
        await settings_data.insert_one({"_id": "bot_settings", **s})
    for k, v in {"premium_protect": False, "custom_btn": {"text": "", "url": ""}}.items():
        if k not in s: s[k] = v; await settings_data.update_one({"_id": "bot_settings"}, {"$set": {k: v}})
    return s

async def update_settings(field, value):
    await settings_data.update_one({"_id": "bot_settings"}, {"$set": {field: value}})

# ---------------- Callback ----------------
@Client.on_callback_query(filters.regex("^toggle_premium_protect$"))
async def toggle_premium_protect_cb(client, query):
    s = await get_settings()
    v = not s.get("premium_protect", False)
    await update_settings("premium_protect", v)
    await query.answer(f"ᴘʀᴇᴍᴘᴄ {'ᴇɴᴀʙʟᴇᴅ ✅' if v else 'ᴅɪꜱᴀʙʟᴇᴅ ❌'}", show_alert=True)
    await refresh_panel(client, query.message.chat.id, query.message.id)

# ---------------- ʀᴇꜰʀᴇꜱʜ ᴘᴀɴᴇʟ ----------------
async def refresh_panel(client, chat_id, msg_id=None):
    s = await get_settings()

    pc, ad, rb = ("✅" if s.get(k, False) else "❌" for k in ("protect_content", "auto_delete_on", "copy_reply_btn"))
    sec = s.get("auto_delete", 600)
    cm = s.get("caption_mode", "original")
    mode_icon = "👥" if s.get("media_send_mode", "group") == "group" else "👤"
    cap_map = {"original": "📜 ᴏʀɪɢɪɴᴀʟ", "custom": "✏️ ᴄᴜꜱᴛᴏᴍ", "hidden": "🙈 ʜɪᴅᴅᴇɴ"}

    cap = s.get("custom_caption", "ɴᴏ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ")
    btn = s.get("custom_btn", {"text": "", "url": ""})
    btn_txt = btn.get("text") or "ɴᴏ ʙᴜᴛᴛᴏɴ"

    txt = (
        "<b>⚙️ ʙᴏᴛ sᴇᴛᴛɪɴɢs</b>\n\n"
        f"🔒 <b>ᴘʀᴏᴛᴇᴄᴛ:</b> {pc}\n"
        f"🧹 <b>ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ:</b> {ad} ({sec}s)\n"
        f"💬 <b>ʀᴇᴘʟʏ ʙᴛɴ:</b> {rb}\n"
        f"📝 <b>ᴄᴀᴘᴛɪᴏɴ ᴍᴏᴅᴇ:</b> {cap_map[cm]}\n"
        f"🗒️ <b>ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ:</b> <code>{cap}</code>\n"
        f"🔗 <b>ᴄᴜꜱᴛᴏᴍ ʙᴜᴛᴛᴏɴ:</b> {btn_txt}\n"
        f"📤 <b>ꜱᴇɴᴅ ᴍᴏᴅᴇ:</b> {'👥 ɢʀᴏᴜᴘ' if mode_icon == '👥' else '👤 ɪɴᴅɪᴠɪᴅᴜᴀʟ'}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔒 ᴘᴄ: {pc}", callback_data="toggle_protect"),
         InlineKeyboardButton(f"🧹 ᴀᴅ: {ad}", callback_data="toggle_autodel")],
        [InlineKeyboardButton(f"⏱ {sec}s", callback_data="set_autodel")],
        [InlineKeyboardButton(f"💬 ʀᴇᴘʟʏ ʙᴛɴ: {rb}", callback_data="toggle_replybtn"),
         InlineKeyboardButton(f"📝 ᴄᴀᴘ: {cap_map[cm]}", callback_data="toggle_caption_mode")],
        [InlineKeyboardButton(f"📤 ᴍᴏᴅᴇ: {mode_icon}", callback_data="toggle_media_mode")],
        [InlineKeyboardButton("✏️ sᴇᴛ ᴄᴀᴘ", callback_data="set_custom_caption"),
         InlineKeyboardButton("🔗 sᴇᴛ ʙᴛɴ", callback_data="set_custom_btn")],
        [InlineKeyboardButton("🔄 ʀᴇꜰʀᴇꜱʜ", callback_data="refresh_panel"),
         InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="close_stats")]
    ])

    if msg_id:
        await client.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
    else:
        await client.send_message(chat_id, txt, reply_markup=kb)

@Client.on_callback_query(filters.regex("set_custom_btn") & is_admin)
async def set_custom_btn_cb(client, q: CallbackQuery):
    await q.answer()

    # Ask for button text
    await client.send_message(q.from_user.id, "✏️ ᴇɴᴛᴇʀ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ᴛᴇxᴛ:")
    try:
        btn_text_msg: Message = await client.listen(q.from_user.id, timeout=120)
    except asyncio.TimeoutError:
        return await client.send_message(q.from_user.id, "⏰ ᴛɪᴍᴇᴅ ᴏᴜᴛ. ɴᴏ ʙᴜᴛᴛᴏɴ ᴛᴇxᴛ ᴘʀᴏᴠɪᴅᴇᴅ.")

    # Ask for button URL
    await client.send_message(q.from_user.id, "🔗 ᴇɴᴛᴇʀ ᴛʜᴇ ᴜʀʟ ᴏʀ ᴛᴇʟᴇɢʀᴀᴍ ʟɪɴᴋ:")
    try:
        btn_url_msg: Message = await client.listen(q.from_user.id, timeout=120)
    except asyncio.TimeoutError:
        return await client.send_message(q.from_user.id, "⏰ ᴛɪᴍᴇᴅ ᴏᴜᴛ. ɴᴏ ᴜʀʟ ᴘʀᴏᴠɪᴅᴇᴅ.")

    # Save button
    s = await get_settings()
    s["custom_btn"] = {"text": btn_text_msg.text, "url": btn_url_msg.text}
    await update_settings("custom_btn", s["custom_btn"])

    await client.send_message(
        q.from_user.id,
        f"✅ ᴄᴜꜱᴛᴏᴍ ʙᴜᴛᴛᴏɴ ᴜᴘᴅᴀᴛᴇᴅ:\n<b>{btn_text_msg.text}</b> → <code>{btn_url_msg.text}</code>",
        parse_mode=ParseMode.HTML
    )

    await refresh_panel(client, q.message.chat.id, q.message.id)


# ---------------- Callback Queries ----------------
@Client.on_callback_query(filters.regex("toggle_caption_mode") & is_admin)
async def toggle_caption_mode_cb(client, q: CallbackQuery):
    s = await get_settings()
    modes = ["original", "custom", "hidden"]
    current = s.get("caption_mode", "original")
    next_mode = modes[(modes.index(current) + 1) % len(modes)]
    await update_settings("caption_mode", next_mode)
    await refresh_panel(client, q.message.chat.id, q.message.id)
    await q.answer(f"ᴄᴀᴘ ᴍᴏᴅᴇ: {next_mode}", show_alert=True)


@Client.on_callback_query(filters.regex("set_custom_caption") & is_admin)
async def set_custom_caption_cb(client, q: CallbackQuery):
    await q.answer()  # acknowledge click
    try:
        reply = await client.ask(
            chat_id=q.from_user.id,
            text="✏️ ᴇɴᴛᴇʀ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ:",
            filters=filters.text,
            timeout=120
        )
    except asyncio.TimeoutError:
        return await client.send_message(q.from_user.id, "⏰ ᴛɪᴍᴇᴅ ᴏᴜᴛ. ɴᴏ ᴄᴀᴘ ᴄᴇᴛ.")

    await update_settings("custom_caption", reply.text)
    await update_settings("caption_mode", "custom")  # auto switch to custom
    await refresh_panel(client, q.message.chat.id, q.message.id)
    await client.send_message(q.from_user.id, "✅ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘ ᴜᴘᴅᴀᴛᴇᴅ.")

# ---------------- Callback Queries ----------------
@Client.on_callback_query(filters.regex("refresh_panel") & is_admin)
async def refresh_panel_cb(client, q):
    try:
        await client.edit_message_text(
            q.message.chat.id, q.message.id, "🔄 <b>ʀᴇꜰʀᴇꜱʜɪɴɢ...</b>", parse_mode=ParseMode.HTML
        )
    except:pass
    await refresh_panel(client, q.message.chat.id, q.message.id)
    await q.answer("ʀᴇꜰʀᴇꜱʜᴇᴅ ✅")

@Client.on_callback_query(filters.regex("close_stats") & is_admin)
async def close_stats(client, q):
    await q.message.delete()

@Client.on_callback_query(filters.regex("close"))
async def close_msg_callback(_, cq):
    await cq.message.delete()
    await cq.answer()

@Client.on_callback_query(filters.regex("toggle_protect") & is_admin)
async def toggle_protect_cb(client, q):
    settings = await get_settings()
    current_val = settings.get("protect_content", False)  # fallback
    new_val = not current_val

    await update_settings("protect_content", new_val)
    await refresh_panel(client, q.message.chat.id, q.message.id)

    await q.answer(f"🔒 ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ {'ᴏɴ' if new_val else 'ᴏꜰꜰ'}",show_alert=True)


@Client.on_callback_query(filters.regex("set_autodel") & is_admin)
async def set_autodel_cb(c, q):
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="settings")]]
    )

    await q.message.edit_text(
        "⏱ Sᴇɴᴅ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇ ɪɴ sᴇᴄs\n(e.g. <code>600</code> = 10 min)",
        reply_markup=kb
    )

    try:
        # Wait for user reply (1 minute max)
        response = await c.listen(q.from_user.id, filters=filters.text, timeout=60)

        if not response.text.strip().isdigit():
            return await response.reply("❌ Iɴᴠᴀʟɪᴅ ɪɴᴘᴜᴛ, ᴘʟᴇᴀsᴇ sᴇɴᴅ ɴᴜᴍʙᴇʀs ᴏɴʟʏ.")

        secs = int(response.text.strip())

        if secs < 0:
            return await response.reply("❌ Tɪᴍᴇ ᴍᴜsᴛ ʙᴇ ᴀ ᴘᴏsɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ.")

        # Save setting
        await update_settings("auto_delete", secs)

        await response.reply(f"✅ Aᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ sᴇᴛ ᴛᴏ <b>{secs}</b> sᴇᴄs")
        await refresh_panel(c, q.message.chat.id, q.message.id)

    except asyncio.TimeoutError:
        await q.message.reply("❌ Tɪᴍᴇᴅ ᴏᴜᴛ — ɴᴏ ɪɴᴘᴜᴛ ʀᴇᴄᴇɪᴠᴇᴅ.")

@Client.on_callback_query(filters.regex("toggle_autodel")& is_admin)
async def toggle_autodel_cb(client, q):

    settings = await get_settings()
    new_val = not settings.get("auto_delete_on", False)
    await update_settings("auto_delete_on", new_val)

    status_text = "ᴏɴ" if new_val else "ᴏꜰꜰ"
    await q.answer(f"⏱ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ {status_text}", show_alert=True)

    # Optional: update the message with current status
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔒 Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ: {'ᴏɴ' if settings.get('protect_content') else 'ᴏꜰꜰ'}", callback_data="toggle_protect")],
        [InlineKeyboardButton(f"⏱ Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ: {status_text}", callback_data="toggle_autodel")],
        [InlineKeyboardButton("✖ Cʟᴏsᴇ", callback_data="close_stats")]
    ])
    await q.message.edit_reply_markup(buttons)

@Client.on_callback_query(filters.regex("about_bot"))
async def about_callback(client, callback_query):
    await callback_query.message.edit_media(InputMediaPhoto("https://i.ibb.co/9kCPFWrb/image.jpg", caption="ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.."))
    await callback_query.message.edit_media(
        InputMediaPhoto("https://i.ibb.co/9kCPFWrb/image.jpg", caption=ABOUT_MSG.format(botname=client.me.first_name)),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="start_back"), InlineKeyboardButton("ᴄʟᴏꜱᴇ •", callback_data="close")]])
    )

@Client.on_callback_query(filters.regex("start_back"))
async def back_to_start(client, callback_query):
    await callback_query.answer()
    user_mention = callback_query.from_user.mention
    await callback_query.message.edit_text(
        START_MSG.format(mention=user_mention),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about_bot"),InlineKeyboardButton("sᴇᴛᴛɪɴɢs •", callback_data="settings")]])
    )

@Client.on_callback_query(filters.regex("settings"))
async def show_settings(client, callback_query):
    await callback_query.answer()
    await callback_query.message.edit_text("<b>⚙ ʟᴏᴀᴅɪɴɢ sᴇᴛᴛɪɴɢs...</b>")

    settings = await settings_data.find_one({"_id": "bot_settings"}) or {}
    get_flag = lambda key: "ᴇɴᴀʙʟᴇᴅ ✅" if settings.get(key) else "ᴅɪsᴀʙʟᴇᴅ ❌"

    # Get referral reward from DB dynamically
    ref_bonus = settings.get("referral_reward", "1d")  # default 1 day
    # Convert to readable format
    readable_bonus = ref_bonus.replace("d", " ᴅᴀʏ").replace("h", " ʜᴏᴜʀ").replace("m", " ᴍɪɴ")

    msg_text = SETTING_TXT.format(
        free_mode=get_flag("free_mode"),
        usep_mode=get_flag("usep_mode"),
        free_limit=settings.get("free_limit", 10),
        autodel_mode=get_flag("auto_delete_on"),
        protect_content=get_flag("protect_content"),
        refer_mode=get_flag("refer_mode"),
        ref_bonus=readable_bonus,
        autopost_mode="ᴇɴᴀʙʟᴇᴅ ✅" if getattr(client, "autopost_enabled", False) else "ᴅɪsᴀʙʟᴇᴅ ❌",
        total_admin=await admins_data.count_documents({}),
        total_ban=await user_data.count_documents({"is_banned": True}),
        total_fsub_channels=await channel_data.count_documents({}),
        total_shortners=await shorteners_data.count_documents({}) if shorteners_data is not None else 0,
        total_dumps=await dump_data.count_documents({}) if dump_data is not None else 0
    )

    await callback_query.message.edit_media(
        InputMediaPhoto(
            media=random.choice(PICS),
            caption=msg_text,
            parse_mode=ParseMode.HTML
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="start_back"),
             InlineKeyboardButton("ᴄʟᴏꜱᴇ •", callback_data="close")]
        ])
    )


@Client.on_callback_query(filters.regex("refresh_refers") & is_admin)
async def refresh_refers_cb(client, callback):
    await callback.message.edit_text("🔄 <b>ʀᴇꜰʀᴇꜱʜɪɴɢ...</b>")
    await check_refers(client, callback.message, edit=True)
    await callback.answer("✅ ᴜᴘᴅᴀᴛᴇᴅ", show_alert=False)

@Client.on_callback_query(filters.regex("refresh_status") & is_admin)
async def refresh_stats_cb(client, callback_query):
    await callback_query.answer()
    await client.edit_message_text(chat_id=callback_query.message.chat.id,message_id=callback_query.message.id,text="🔄 <b>ʀᴇꜰʀᴇꜱʜɪɴɢ...</b>",parse_mode=ParseMode.HTML)
    await send_bot_stats(client,chat_id=callback_query.message.chat.id,message_id=callback_query.message.id)

@Client.on_callback_query(filters.regex("refresh_verification_stats") & is_admin)
async def refresh_verification_stats_cb(client, callback_query):
    await callback_query.answer("🔄 ᴜᴘᴅᴀᴛɪɴɢ...")
    await client.edit_message_text(callback_query.message.chat.id, callback_query.message.id, "🔄 <b>ʀᴇꜰʀᴇꜱʜɪɴɢ...</b>", parse_mode=ParseMode.HTML)
    await send_verified_stats(client, callback_query.message.chat.id, callback_query.message.id)

async def has_used_free_trial(user_id: int) -> bool:
    """Check if the user already used the free trial."""
    return await free_trial_data.find_one({"user_id": user_id}) is not None

async def mark_free_trial_used(user_id: int):
    """Mark user as having used the free trial."""
    await free_trial_data.insert_one({"user_id": user_id, "used_at": int(time.time())})

active_qr_sessions, user_orders = {}, {}
user_locks = defaultdict(asyncio.Lock)


# ------------------ TOGGLE COMMAND ------------------

@Client.on_message(filters.command("ronak") & filters.private)
async def toggle_payment_account(client: Client, message: Message):
    global ACTIVE_PAYMENT

    if ACTIVE_PAYMENT == "ronak":
        ACTIVE_PAYMENT = "kartik"
    else:
        ACTIVE_PAYMENT = "ronak"

    await message.reply_text(
        f"✅ Payment Account Switched!\n\n"
        f"💳 Now Using: {ACTIVE_PAYMENT.upper()}\n"
        f"🆔 Merchant: {PAYMENT_ACCOUNTS[ACTIVE_PAYMENT]['merchant']}"
    )


async def update_qr_timer(client, msg, order_id: str, user_orders: dict, active_qr_sessions: dict, user_id: int, total_seconds: int = 300):
    expire_at = time.time() + total_seconds

    while True:
        await asyncio.sleep(5)

        order = user_orders.get(order_id)
        if not order or order.get("used"):
            break

        remaining = expire_at - time.time()

        if remaining <= 0:
            try:
                await client.edit_message_reply_markup(
                    msg.chat.id, msg.id,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌ 𝖰𝖱 𝖢𝖮𝖣𝖤 𝖤𝖷𝖯𝖨𝖱𝖤𝖣", callback_data="none")
                    ]])
                )
            except Exception:
                pass
            break

        mins = int(remaining // 60)
        secs = int(remaining % 60)

        try:
            await client.edit_message_reply_markup(
                msg.chat.id, msg.id,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"⏳ 𝖤𝖷𝖯𝖨𝖱𝖤𝖲 𝖨𝖭 {mins:02d}:{secs:02d}", callback_data="none")
                ]])
            )
        except Exception:
            break


# ------------------ CALLBACK HANDLER ------------------
@Client.on_callback_query(filters.regex("buy_premium|plan_|free_trial|retry_"))
async def buy_and_verify_handler(client: Client, query: CallbackQuery):
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # -------- PLAN MENU --------
    if data == "buy_premium":
        rows, row = [], []

        for i, p in enumerate(PLANS):
            row.append(InlineKeyboardButton(
                f"{p['label']} · {p['price']}",
                callback_data=f"plan_{i}"
            ))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        rows.append([InlineKeyboardButton("𝖢𝖮𝖬𝖡𝖮 𝖡𝖮𝖳 𝖲𝖴𝖡𝖲𝖢𝖱𝖨𝖯𝖳𝖨𝖮𝖭 🤖",url="https://t.me/paidwalabot?start=start")])

        return await query.message.edit_text(
            "💳 <b>𝗖𝗛𝗢𝗢𝗦𝗘 𝗔 𝗣𝗟𝗔𝗡\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏦 <b>𝖯𝖠𝖸𝖳𝖬 • 𝖴𝖯𝖨 • 𝖯𝖧𝖮𝖭𝖤𝖯𝖤 • 𝖦𝖯𝖠𝖸</b>\n\n"
            "✦ Pʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛᴇs ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴀғᴛᴇʀ ᴘᴀʏᴍᴇɴᴛ\n"
            "✦ Fᴏʀᴡᴀʀᴅ & Dᴏᴡɴʟᴏᴀᴅ ᴇɴᴀʙʟᴇᴅ ✅\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👇 Sᴇʟᴇᴄᴛ ʏᴏᴜʀ ᴘʟᴀɴ:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows)
        )

    # -------- FREE TRIAL --------
    elif data == "free_trial":
        if await has_used_free_trial(user_id):
            return await query.answer("⚠️ You already used your free trial!", show_alert=True)

        await mark_free_trial_used(user_id)
        await add_premium(user_id, 5 / 1440)

        return await query.message.edit_text(
            "🎉 <b>𝖥𝖱𝖤𝖤 𝖳𝖱𝖨𝖠𝖫 𝖠𝖢𝖳𝖨𝖵𝖠𝖳𝖤𝖣</b>\n\n"
            "⏱ Yᴏᴜ ʜᴀᴠᴇ <b>5 ᴍɪɴᴜᴛᴇs</b> ᴏғ Pʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇss.\n\n"
            "🔥 Eɴᴊᴏʏ ᴀʟʟ ᴘʀᴇᴍɪᴜᴍ ғᴇᴀᴛᴜʀᴇs!",
            parse_mode=ParseMode.HTML
        )

    # -------- RETRY --------
    elif data.startswith("retry_"):
        order = user_orders.get(data.split("_", 1)[1])

        if not order or order["used"]:
            return await query.answer("⚠️ Invalid or already used order!", show_alert=True)

        for i, p in enumerate(PLANS):
            if p["days"] == order["days"]:
                data = f"plan_{i}"
                break

    # -------- GENERATE QR --------
    if data.startswith("plan_"):
        async with user_locks[user_id]:

            if user_id in active_qr_sessions:
                return await query.answer("⚠️ You have a pending payment. Complete it first!", show_alert=True)

            plan = PLANS[int(data.split("_")[1])]
            amount = int(plan["price"].replace("₹", ""))
            order_id = f"WOW-{user_id}_{int(time.time())}"

            account_used = ACTIVE_PAYMENT

            active_qr_sessions[user_id] = order_id
            user_orders[order_id] = {
                "user": user_id,
                "amount": amount,
                "days": plan["days"],
                "used": False,
                "account": account_used
            }

            upi = f"upi://pay?pa={PAYMENT_ACCOUNTS[account_used]['upi']}&pn=Premium&am={amount}&cu=INR&tn={order_id}&tr={order_id}"

            qr = qrcode.make(upi)
            bio = io.BytesIO()
            bio.name = "qr.png"
            qr.save(bio)
            bio.seek(0)

            msg = await client.send_photo(
                query.message.chat.id,
                bio,
                caption=f"✦ <b>𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗣𝗔𝗬𝗠𝗘𝗡𝗧\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"💰 <b>𝖠𝖬𝖮𝖴𝖭𝖳 :</b>  {plan['price']}\n"
                        f"📦 <b>𝖯𝖫𝖠𝖭 :</b>  {plan['label']}\n"
                        f"🧾 <b>𝖮𝖱𝖣𝖤𝖱 :</b>  <code>{order_id}</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📲 <b>Sᴄᴀɴ ᴛʜᴇ QR ᴡɪᴛʜ ᴀɴʏ UPI ᴀᴘᴘ ᴛᴏ ᴘᴀʏ.</b>\n\n"
                        f"<blockquote>⚡ Pʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛᴇs ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴡɪᴛʜɪɴ <b>5 ᴍɪɴᴜᴛᴇs</b> ᴏғ ᴘᴀʏᴍᴇɴᴛ.</blockquote></b>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏳ 𝖤𝖷𝖯𝖨𝖱𝖤𝖲 𝖨𝖭 05:00", callback_data="none")
                ]]),
                parse_mode=ParseMode.HTML
            )

            asyncio.create_task(
                update_qr_timer(client, msg, order_id, user_orders, active_qr_sessions, user_id, total_seconds=300)
            )

            async def check():
                merchant = PAYMENT_ACCOUNTS[user_orders[order_id]["account"]]["merchant"]

                async with aiohttp.ClientSession() as s:
                    for _ in range(60):
                        await asyncio.sleep(5)

                        async with s.get(f"https://pay-rho-seven.vercel.app/?mid={merchant}&oid={order_id}") as r:
                            d = await r.json()

                        if d.get("STATUS") == "TXN_SUCCESS" and int(float(d.get("TXNAMOUNT", 0))) == amount:

                            if user_orders[order_id]["used"]:
                                return

                            user_orders[order_id]["used"] = True
                            active_qr_sessions.pop(user_id, None)

                            await add_premium(user_id, plan["days"])

                            try:
                                await msg.delete()
                            except:
                                pass

                            readable = (
                                dl.datetime.now(pt.timezone("Asia/Kolkata")) +
                                dl.timedelta(days=plan["days"])
                            ).strftime("%d-%b-%Y %I:%M %p")

                            LOG_CHANNELS = {
                                "kartik": -1004296723301,
                                "ronak": -1004296723301
                            }

                            channel_id = LOG_CHANNELS.get(user_orders[order_id]["account"])

                            if channel_id:
                                user = query.from_user
                                mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

                                await client.send_message(
                                    channel_id,
                                    f"💎 <b>𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"👤 <b>Usᴇʀ :</b> {mention}\n"
                                    f"🆔 <b>ID :</b> <code>{user_id}</code>\n"
                                    f"📦 <b>Pʟᴀɴ :</b> {plan['label']} Pʀᴇᴍɪᴜᴍ\n"
                                    f"💰 <b>Aᴍᴏᴜɴᴛ :</b> ₹{amount}\n"
                                    f"🧾 <b>Oʀᴅᴇʀ :</b> <code>{order_id}</code>\n"
                                    f"⏳ <b>Eхᴘɪʀᴇs :</b> {readable}\n"
                                    f"━━━━━━━━━━━━━━━━━━━━",
                                    parse_mode=ParseMode.HTML
                                )

                            return await client.send_message(
                                query.message.chat.id,
                                f"🎉 <b>𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗 !</b>\n\n"
                                f"📦 <b>Pʟᴀɴ :</b> {plan['label']}\n"
                                f"⏳ <b>Eхᴘɪʀᴇs :</b> {readable}\n\n"
                                f"🔥 Eɴᴊᴏʏ ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇss!",
                                parse_mode=ParseMode.HTML
                            )

                active_qr_sessions.pop(user_id, None)

                try:
                    await msg.delete()
                except:
                    pass

                await client.send_message(
                    query.message.chat.id,
                    f"⚠️ <b>𝗤𝗥 𝗘𝗫𝗣𝗜𝗥𝗘𝗗\n\n"
                    f"Yᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴡɪɴᴅᴏᴡ ʜᴀs ᴄʟᴏsᴇᴅ.\n\n"
                    f"🧾 <b>Oʀᴅᴇʀ :</b> <code>{order_id}</code>\n"
                    f"↩️ ᴜsᴇ /verify <code>{order_id}</code> ɪғ ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ᴘᴀɪᴅ.</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 𝖳𝖱𝖸 𝖠𝖦𝖠𝖨𝖭", callback_data=f"retry_{order_id}")],
                        [InlineKeyboardButton("🆘 𝖲𝖴𝖯𝖯𝖮𝖱𝖳", url="https://t.me/DumpAdminBot")]
                    ])
                )

            asyncio.create_task(check())

# ------------------ VERIFY COMMAND ------------------

@Client.on_message(filters.command("verify") & filters.private)
async def verify_payment(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) < 2:
        return await message.reply_text("⚠️ Please provide your order ID.")

    order_id = args[1].strip()
    order = user_orders.get(order_id)

    if not order:
        return await message.reply_text("❌ Invalid Order ID.")

    if order["user"] != user_id:
        return await message.reply_text("❌ This order does not belong to you!")

    if order["used"]:
        return await message.reply_text("⚠️ Already verified!")

    merchant = PAYMENT_ACCOUNTS[order["account"]]["merchant"]

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://pay-rho-seven.vercel.app/?mid={merchant}&oid={order_id}") as resp:
            data = await resp.json()

    if data.get("STATUS") == "TXN_SUCCESS" and float(data.get("TXNAMOUNT", 0)) == order["amount"]:

        order["used"] = True
        active_qr_sessions.pop(user_id, None)
        await add_premium(user_id, order["days"])

        readable = (
            dl.datetime.now(pt.timezone("Asia/Kolkata")) +
            dl.timedelta(days=order["days"])
        ).strftime("%d-%b-%Y %I:%M %p")

        # ✅ LOG ONLY IF KARTIK
        if order["account"] == "kartik":
            user = message.from_user
            mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

            await client.send_message(
                -1003821473525,
                f"💎 <b>𝗠𝗔𝗡𝗨𝗔𝗟 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗</b>\n"
                f"👤 {mention}\n"
                f"🆔 <code>{user_id}</code>\n"
                f"💰 ₹{order['amount']}\n"
                f"🧾 <code>{order_id}</code>\n"
                f"⏳ Expires: {readable}",
                parse_mode=ParseMode.HTML
            )

        return await message.reply_text(
            f"🎉 Payment Verified!\n💎 {order['days']} Days Premium Activated\n⏳ Expires: {readable}",
            parse_mode=ParseMode.HTML
        )

    else:
        await message.reply_text("❌ Payment not received yet.")


@Client.on_callback_query(filters.regex("^toggle_fsub$") & is_admin)
async def toggle_fsub_callback(client: Client, callback_query):
    current = await get_request_forcesub()
    await set_request_forcesub(not current)

    # New state
    updated = not current
    state = "✅ ᴇɴᴀʙʟᴇᴅ" if updated else "❌ ᴅɪsᴀʙʟᴇᴅ"
    btn_text = "❌ ᴅɪsᴀʙʟᴇ" if updated else "✅ ᴇɴᴀʙʟᴇ"

    await callback_query.answer(f"ғᴏʀᴄᴇ sᴜʙ ɪs ɴᴏᴡ {state}", show_alert=True)

    await callback_query.message.edit_text(
        f"<b>📡 ʀᴇǫᴜᴇsᴛ ғᴏʀᴄᴇ sᴜʙ ᴍᴏᴅᴇ</b>\n\nCurrent status: <b>{state}</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(btn_text, callback_data="toggle_fsub")
        ]])
    )

@Client.on_callback_query(filters.regex("^set_tutorial_url$"))
async def cb_set_tutorial_url(client, q):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    
    await q.message.edit_text("🎓 Sᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ᴛᴜᴛᴏʀɪᴀʟ URL:\n(e.g. <code>https://t.me/MyTutorial/5</code>)",reply_markup=kb,parse_mode=ParseMode.HTML)

    try:
        response = await client.listen(q.from_user.id, filters=filters.text, timeout=60)
        url = response.text.strip()
        if not url.startswith("http"):return await response.reply("❌ Iɴᴠᴀʟɪᴅ URL. Please send a valid link starting with <code>http</code>.", parse_mode=ParseMode.HTML)
        await settings_data.update_one({"_id": "bot_settings"}, {"$set": {"tutorial_url": url}}, upsert=True)
        await response.reply(f"✅ ᴛᴜᴛᴏʀɪᴀʟ URL sᴇᴛ ᴛᴏ:\n<code>{url}</code>", parse_mode=ParseMode.HTML)

        await refresh_panel(client, q.message.chat.id, q.message.id)
    except asyncio.TimeoutError:await q.message.reply("❌ Tɪᴍᴇᴅ ᴏᴜᴛ — ɴᴏ ɪɴᴘᴜᴛ ʀᴇᴄᴇɪᴠᴇᴅ.")

# ---------------- ADD API + KEY PANEL ----------------
@Client.on_callback_query(filters.regex("^add_api_key$"))
async def cb_add_api_key(client, q):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel")]])

    await q.message.edit_text(
        "<b>➕ Sᴇɴᴅ ᴛʜᴇ ᴀᴘɪ ᴜʀʟ:\nExample: <code>https://yourdomain.com/api</code></b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

    try:
        api_msg = await client.listen(q.from_user.id, filters=filters.text, timeout=60)
        api = api_msg.text.strip()
        await api_msg.reply("<b>🔑 sᴇɴᴅ ᴀᴘɪ ᴋᴇʏ:</b>")
        key_msg = await client.listen(q.from_user.id, filters=filters.text, timeout=60)
        key = key_msg.text.strip()

        # Save in DB
        await add_shortener(api, key)
        await key_msg.reply(f"<b>✅ ᴀᴘɪ ᴀᴅᴅᴇᴅ..!\n\n🌐 <code>{api}</code>\n🔑 <code>{key}</code></b>", parse_mode=ParseMode.HTML)
        await refresh_panel(client, q.message.chat.id, q.message.id)

    except asyncio.TimeoutError:
        await q.message.reply("<b>❌ Tɪᴍᴇ ᴏᴜᴛ — ɴᴏ ʀᴇᴘʟʏ ʀᴇᴄᴇɪᴠᴇᴅ.</b>")

@Client.on_callback_query(filters.regex("^delete_api$"))
async def show_delete_api_list(client, q):
    shorteners = await list_shorteners()
    if not shorteners:return await q.answer("❌ ɴᴏᴛʜɪɴɢ ᴛʀʏ ᴛᴏ ᴀᴅᴅ ғɪʀsᴛ.", show_alert=True)
    buttons = []
    for s in shorteners:
        api = s["api"]
        _id = str(s["_id"])
        buttons.append([InlineKeyboardButton(api[:40], callback_data=f"del_{_id}")])

    buttons.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel")])

    kb = InlineKeyboardMarkup(buttons)

    await q.message.edit_text(
        "<b>🗑 sᴇʟᴇᴄᴛ ᴀɴ ᴀᴘɪ ᴛᴏ ᴅᴇʟᴇᴛᴇ:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex("^del_"))
async def delete_api(client, q):
    api_id = q.data.replace("del_", "")
    await remove_shortener(api_id)
    await q.answer("✅ ᴀᴘɪ ʀᴇᴍᴏᴠᴇᴅ..!", show_alert=True)
    # Refresh the token panel
    await refresh_panel(client, q.message.chat.id, q.message.id)

@Client.on_callback_query(filters.regex("^refresh_token_stats$"))
async def cb_refresh_token_stats(client, q):
    await q.answer()
    await q.message.edit_caption("<b>ʀᴇғʀᴇsʜɪɴɢ...</b>")  # immediate feedback

    txt, kb = await build_token_panel()
    await q.message.edit_caption(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

@Client.on_callback_query(filters.regex("^toggle_referral_mode$"))
async def cb_toggle_referral_mode(client, q):
    await q.answer()  # acknowledge button

    s = await settings_data.find_one({"_id": "bot_settings"}) or {}
    new_status = not s.get("referral_mode", False)
    await settings_data.update_one({"_id": "bot_settings"}, {"$set": {"referral_mode": new_status}}, upsert=True)

    # Use same helper to rebuild panel
    text, kb = await get_referral_panel()
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@Client.on_callback_query(filters.regex("^set_referral_reward$"))
async def cb_set_referral_reward(client, q):
    await q.answer()

    await q.message.edit_text(
        "⏱ Send referral reward duration (e.g., <code>1d</code> = 1 day, <code>3h</code> = 3 hours, <code>30m</code> = 30 minutes)",
        parse_mode=ParseMode.HTML
    )

    try:
        response = await client.listen(q.from_user.id, filters=filters.text, timeout=60)
        reward_input = response.text.strip().lower()

        # Validate input using your parse_time_string function
        try:
            delta = parse_time_string(reward_input)
            if delta.total_seconds() <= 0:
                return await response.reply("❌ Reward duration must be greater than 0.")
        except:
            return await response.reply("❌ Invalid format. Use like 1d, 3h, 30m.")

        # Save in DB
        await settings_data.update_one(
            {"_id": "bot_settings"},
            {"$set": {"referral_reward": reward_input}},
            upsert=True
        )

        await response.reply(f"✅ Referral reward set to <b>{reward_input}</b> successfully.", parse_mode=ParseMode.HTML)

        # Refresh panel
        text, kb = await get_referral_panel()
        await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    except asyncio.TimeoutError:
        await q.message.reply("❌ Timed out — no input received.")

# ---------------- TOGGLE REPLY BUTTON ----------------
@Client.on_callback_query(filters.regex("^toggle_replybtn$") & is_admin)
async def toggle_reply_btn_cb(client, q: CallbackQuery):
    try:
        s = await get_settings()
        current_status = s.get("copy_reply_btn", True)
        new_status = not current_status

        # ✅ Save updated setting to DB
        await update_settings("copy_reply_btn", new_status)

        # ✅ Notify admin
        await q.answer(
            f"Reply buttons {'enabled ✅' if new_status else 'disabled ❌'}",
            show_alert=True
        )

        # ✅ Refresh panel to reflect change
        await refresh_panel(client, q.message.chat.id, q.message.id)

        # Debug info (optional)
        print(f"[DEBUG] copy_reply_btn updated -> {new_status}")

    except Exception as e:
        print("[ERROR] toggle_reply_btn_cb failed:", e)
        await q.answer("⚠️ Error updating setting!", show_alert=True)


@Client.on_callback_query(filters.regex("^toggle_media_mode$"))
async def toggle_media_mode_cb(client, q):
    s = await get_settings()
    current = s.get("media_send_mode", "group")
    new_mode = "individual" if current == "group" else "group"

    await update_settings("media_send_mode", new_mode)

    await q.answer(f"ᴍᴇᴅɪᴀ sᴡɪᴛᴄʜᴇᴅ ᴛᴏ {'ɪɴᴅɪᴠɪᴅᴜᴀʟ' if new_mode == 'individual' else 'ɢʀᴏᴜᴘ'} ✅", show_alert=True)
    # await admin_cmd(client, q.message)
