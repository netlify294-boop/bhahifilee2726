import os, sys, time, asyncio, glob, shutil
from datetime import datetime, timedelta, timezone
import pytz

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from database import *
from config import *
from helper import *

IST = pytz.timezone("Asia/Kolkata")
now = datetime.now(IST)

# ----------------- Pictures -----------------
ON_PIC = "https://telegra.ph/file/5593d624d11d92bceb48e.jpg"
OFF_PIC = "https://telegra.ph/file/0d9e590f62b63b51d4bf9.jpg"
AUTODEL_CMD_PIC = "https://telegra.ph/file/a64533814021b40057ccd.jpg"

# --- Globals ---
cancel_lock = asyncio.Lock()
is_canceled = False

@Client.on_message(filters.command("admin") & is_admin)
async def admin_cmd(client, message):
    fetching = await message.reply_text("⏳ <b>ғᴇᴛᴄʜɪɴɢ...</b>", parse_mode=ParseMode.HTML)
    s = await get_settings()

    pc, ad, rb = ("✅" if s.get(k, False) else "❌" for k in ("protect_content", "auto_delete_on", "copy_reply_btn"))
    mode_icon = "👥" if s.get("media_send_mode", "group") == "group" else "👤"
    cm, t = s.get("caption_mode", "original"), s.get("auto_delete", 600)
    cap_status = {"original": "📜 ᴏʀɪɢɪɴᴀʟ", "custom": "✏️ ᴄᴜꜱᴛᴏᴍ", "hidden": "🙈 ʜɪᴅᴅᴇɴ"}

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔒 ᴘᴄ: {pc}", callback_data="toggle_protect"),
         InlineKeyboardButton(f"🧹 ᴀᴜᴛᴏ ᴅᴇʟ: {ad}", callback_data="toggle_autodel")],
        [InlineKeyboardButton(f"ᴀᴜᴛᴏ ᴅᴇʟ ɪɴ : {t}s", callback_data="set_autodel")],
        [InlineKeyboardButton(f"💬 ʀᴇᴘʟʏ ʙᴛɴ: {rb}", callback_data="toggle_replybtn"),
         InlineKeyboardButton(f"ᴄᴀᴘᴛɪᴏɴ: {cap_status[cm]}", callback_data="toggle_caption_mode")],
        [InlineKeyboardButton(f"📤 sᴇɴᴅ ᴍᴇᴅɪᴀ ᴍᴏᴅᴇ: {mode_icon}", callback_data="toggle_media_mode")],
        [InlineKeyboardButton("✏️ sᴇᴛ ᴄᴀᴘ", callback_data="set_custom_caption"),
         InlineKeyboardButton("🔗 sᴇᴛ ʙᴛɴ", callback_data="set_custom_btn")],
        [InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data="refresh_panel"),
         InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_stats")]
    ])

    txt = (
        "<b>⚙️ ʙᴏᴛ sᴇᴛᴛɪɴɢs</b>\n\n"
        f"🔒 <b>ᴘʀᴏᴛᴇᴄᴛ:</b> {pc}\n🧹 <b>ᴀᴜᴛᴏ ᴅᴇʟ:</b> {ad} ({t}s)\n"
        f"💬 <b>ʀᴇᴘʟʏ ʙᴛɴ:</b> {rb}\n📝 <b>ᴄᴀᴘᴛɪᴏɴ ᴍᴏᴅᴇ:</b> {cap_status[cm]}\n"
        f"📤 <b>sᴇɴᴅ ᴍᴇᴅɪᴀ:</b> {'👥 ɢʀᴏᴜᴘ' if mode_icon == '👥' else '👤 ɪɴᴅɪᴠɪᴅᴜᴀʟ'}\n\n"
        "<blockquote><b>ɢʀᴏᴜᴘᴇᴅ ᴍᴇᴅɪᴀ ᴅᴏᴇs ɴᴏᴛ sᴜᴘᴘᴏʀᴛ ʀᴇᴘʟʏ ʙᴜᴛᴛᴏɴs.</b></blockquote>"
    )

    await fetching.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

@Client.on_message(filters.command(["pf", "protectfile"]) & is_admin)
async def protect_file_cmd(_, m):
    """Set protect content ON/OFF for a file or batch link."""
    try:
        _, target, mode = m.text.split(maxsplit=2)
        if mode.lower() not in ("on", "off"):
            raise ValueError
        protect = mode.lower() == "on"

        file_ids = []

        # If target is a batch link, decode and fetch all files
        if target.startswith("http") and "start=" in target:
            payload = target.split("start=", 1)[1]
            raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
            if not raw.startswith("b-"):
                return await m.reply_text("❌ Invalid batch link")
            batch = await batches_data.find_one({"_id": ObjectId(raw[2:])})
            if not batch or "files" not in batch:
                return await m.reply_text("❌ Batch not found or empty")
            # Collect all file_ids in the batch
            file_ids = [f["file_id"] for f in batch["files"]]
        else:
            # Single file id
            file_ids = [target]

        # Update each file's protect setting
        update = {f"protect_files.{fid}": protect for fid in file_ids}
        await settings_data.update_one(
            {"_id": "bot_settings"},
            {"$set": update},
            upsert=True
        )

        text = "✅ <b>ғɪʟᴇ ᴘʀᴏᴛᴇᴄᴛ ᴜᴘᴅᴀᴛᴇᴅ</b>\n\n"
        for fid in file_ids:
            text += f"• ɪᴅ : <code>{fid}</code>\n• ᴍᴏᴅᴇ : <code>{'ᴏɴ' if protect else 'ᴏғғ'}</code>\n\n"

        await m.reply_text(text.strip(), parse_mode=ParseMode.HTML)

    except Exception:
        await m.reply_text(
            "❌ <b>ᴜsᴀɢᴇ</b>\n<code>/pf &lt;ғɪʟᴇ_ɪᴅ | ʟɪɴᴋ&gt; ᴏɴ/ᴏғғ</code>",
            parse_mode=ParseMode.HTML
        )

# ----------------- Free Mode -----------------
@Client.on_message(filters.command("free") & is_admin)
async def toggle_free_mode(client, message):
    settings = await settings_data.find_one({"_id": "bot_settings"}) or {"free_mode": False}
    if not settings.get("_id"): await settings_data.insert_one({"_id": "bot_settings", **settings})
    new_mode = not settings.get("free_mode", False)
    await settings_data.update_one({"_id": "bot_settings"}, {"$set": {"free_mode": new_mode}})
    await message.reply_text(f"<b>⚡ ғʀᴇᴇ ᴍᴏᴅᴇ {'ᴇɴᴀʙʟᴇᴅ' if new_mode else 'ᴅɪsᴀʙʟᴇᴅ'}!</b>", parse_mode=ParseMode.HTML)

# ----------------- Admin Management -----------------
@Client.on_message(filters.command("addadmin") & is_admin)
async def add_admin(client, message):
    try:
        user_id = int(message.text.split()[1])
        if await admins_data.find_one({"_id": user_id}):
            return await message.reply_text("<b>⚠ ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴀɴ ᴀᴅᴍɪɴ</b>", parse_mode=ParseMode.HTML)
        await admins_data.insert_one({"_id": user_id})
        await message.reply_text("<b>✅ ᴀᴅᴍɪɴ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ</b>", parse_mode=ParseMode.HTML)
    except: await message.reply_text("<b>❌ ᴜsᴀɢᴇ: /addadmin user_id</b>", parse_mode=ParseMode.HTML)

# ----------------- Ban Management -----------------
@Client.on_message(filters.command(["banlist","listban"]) & is_admin)
async def banlist(c, m):
    u = await banned_users_data.find().to_list(100)
    if not u: return await m.reply("<b>✅ ɴᴏ ʙᴀɴɴᴇᴅ ᴜsᴇʀs</b>")

    l=[]
    for x in u:
        try: y=await c.get_users(x["_id"]); l.append(f"• {y.mention} | <code>{x['_id']}</code>")
        except: l.append(f"• Dᴇʟᴇᴛᴇᴅ Aᴄᴄᴏᴜɴᴛ | <code>{x['_id']}</code>")

    await m.reply("<b>🚫 ʙᴀɴɴᴇᴅ ᴜsᴇʀs ʟɪsᴛ</b>\n\n<blockquote><b>"+"\n".join(l)+"</b></blockquote>")


@Client.on_message(filters.command("listadmin") & is_admin)
async def list_admins(client, message):
    admins = await admins_data.find().to_list(length=100)
    if not admins: return await message.reply_text("<b>⚠ ɴᴏ ᴀᴅᴍɪɴs ғᴏᴜɴᴅ.</b>", parse_mode=ParseMode.HTML)
    text = "<b>👮 Aᴅᴍɪɴs Lɪsᴛ:</b>\n\n"
    for a in admins:
        try: user = await client.get_users(a["_id"]); text += f"<blockquote><b>• {user.mention} | <code>{a['_id']}</code></b></blockquote>\n"
        except: text += f"<code>{a['_id']}</code>\n"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@Client.on_message(filters.command("deladmin") & is_admin)
async def del_admin(client, message):
    try: user_id = int(message.text.split()[1]); await admins_data.delete_one({"_id": user_id})
    except: return await message.reply_text("<b>❌ ᴜsᴀɢᴇ: /deladmin user_id</b>", parse_mode=ParseMode.HTML)
    await message.reply_text("<b>✅ ᴀᴅᴍɪɴ ʀᴇᴍᴏᴠᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ</b>", parse_mode=ParseMode.HTML)

# ----------------- Ban Management -----------------
@Client.on_message(filters.command("ban") & is_admin)
async def ban_user(client, message):
    try:
        user_id = int(message.text.split()[1])
        if await banned_users_data.find_one({"_id": user_id}):
            return await message.reply_text("<b>⚠ ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ʙᴀɴɴᴇᴅ</b>", parse_mode=ParseMode.HTML)
        await banned_users_data.insert_one({"_id": user_id})
        await message.reply_text("<b>✅ ᴜsᴇʀ ʙᴀɴɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ</b>", parse_mode=ParseMode.HTML)
    except: await message.reply_text("<b>❌ ᴜsᴀɢᴇ: /ban user_id</b>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.command("unban") & is_admin)
async def unban_user(client, message):
    try: user_id = int(message.text.split()[1]); await banned_users_data.delete_one({"_id": user_id})
    except: return await message.reply_text("<b>❌ ᴜsᴀɢᴇ: /unban user_id</b>", parse_mode=ParseMode.HTML)
    await message.reply_text("<b>✅ ᴜsᴇʀ ᴜɴʙᴀɴɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ</b>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.command("usep") & is_admin)
async def toggle_usep(c, m):
    s = await settings_data.find_one({"_id": "bot_settings"}) or {}
    new = not s.get("usep_mode", False)
    await settings_data.update_one({"_id": "bot_settings"}, {"$set": {"usep_mode": new}}, upsert=True)
    await m.reply_text(f"<b>ᴜsᴇᴘ ᴍᴏᴅᴇ {'✅ ᴇɴᴀʙʟᴇᴅ' if new else '❌ ᴅɪsᴀʙʟᴇᴅ'}</b>", parse_mode=ParseMode.HTML)

# ----------------- Forced Subscription -----------------


# --- Cancel Command ---
@Client.on_message(filters.command('cancel') & filters.private & is_admin)
async def cancel_broadcast(client, message):
    global is_canceled
    async with cancel_lock:
        is_canceled = True
    await message.reply_text("❌ ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ᴄᴀɴᴄᴇʟᴇᴅ.")

async def safe_copy(message, client, chat_id, mode="copy", silent=False):
    try:
        if mode == "forward":
            await message.forward(chat_id, disable_notification=silent)
        elif mode == "pin":
            sent = await message.copy(chat_id, disable_notification=silent)
            await client.pin_chat_message(chat_id, sent.id, both_sides=True)
        else:await message.copy(chat_id, disable_notification=silent)
        return True
    except FloodWait as e:
        await asyncio.sleep(e.x)
        try:
            if mode == "forward":
                await message.forward(chat_id, disable_notification=silent)
            elif mode == "pin":
                sent = await message.copy(chat_id, disable_notification=silent)
                await client.pin_chat_message(chat_id, sent.id, both_sides=True)
            else:
                await message.copy(chat_id, disable_notification=silent)
            return True
        except:
            return False
    except (UserIsBlocked, InputUserDeactivated):
        return False
    except Exception:
        return False


# --- Main Broadcast ---
@Client.on_message(filters.command('broadcast') & filters.private & is_admin)
async def send_text(client, message):
    global is_canceled
    async with cancel_lock: is_canceled = False

    mode, silent, broad_mode = "copy", False, ""
    args = message.text.split()[1:]
    if args:
        if args[0].lower() == "silent": silent, broad_mode = True, 'sɪʟᴇɴᴛ '
        elif args[0].lower() == "forward": mode, broad_mode = "forward", 'ғᴏʀᴡᴀʀᴅ '
        elif args[0].lower() == "pin": mode, broad_mode = "pin", 'ᴘɪɴ '

    if not message.reply_to_message:
        msg = await message.reply("<b>⚠ Rᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ sᴛᴀʀᴛ ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ.</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(5); return await msg.delete()

    broadcast_msg = message.reply_to_message
    query = await full_userbase()
    skip_list = set(await get_all_admins()) | {int(client.me.id)}
    filtered_query = [u for u in query if u not in skip_list]

    total, successful, blocked, deleted, unsuccessful, skipped = len(filtered_query), 0, 0, 0, 0, len(query) - len(filtered_query)
    pls_wait = await message.reply("<i>ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ... ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ.</i>", parse_mode=ParseMode.HTML)

    bar_length, final_progress_bar, complete_msg = 10, "●"*10, f"🤖 {broad_mode} ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ✅"
    progress_bar, last_update_percentage, update_interval = "", 0, 0.05

    for i, chat_id in enumerate(filtered_query, start=1):
        async with cancel_lock:
            if is_canceled: complete_msg = f"🤖 {broad_mode} ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ᴄᴀɴᴄᴇʟᴇᴅ ❌"; break
        try:
            if mode == "forward": await broadcast_msg.forward(chat_id, disable_notification=silent)
            elif mode == "pin": sent = await broadcast_msg.copy(chat_id, disable_notification=silent); await client.pin_chat_message(chat_id, sent.id, both_sides=True)
            else: await broadcast_msg.copy(chat_id, disable_notification=silent)
            successful += 1
        except FloodWait as e: await asyncio.sleep(e.x); successful += 1 if await safe_copy(broadcast_msg, client, chat_id, mode, silent) else unsuccessful+1
        except UserIsBlocked: await del_user(chat_id); blocked += 1
        except InputUserDeactivated: await del_user(chat_id); deleted += 1
        except: unsuccessful += 1

        percent_complete = i / total
        if percent_complete - last_update_percentage >= update_interval or last_update_percentage == 0:
            num_blocks = int(percent_complete*bar_length)
            progress_bar = "●"*num_blocks + "○"*(bar_length-num_blocks)
            status = f"""<b>🤖 {broad_mode}ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ...
<blockquote>⏳:</b> [{progress_bar}] <code>{percent_complete:.0%}</code></blockquote>
<b>🚻 ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: <code>{len(query)}</code>
👥 ꜱᴋɪᴘᴘᴇᴅ: <code>{skipped}</code>
📤 ᴛᴀʀɢᴇᴛ: <code>{total}</code>
✅ ꜱᴜᴄᴄᴇꜱꜱ: <code>{successful}</code>
🚫 ʙʟᴏᴄᴋᴇᴅ: <code>{blocked}</code>
⚠️ ᴅᴇʟᴇᴛᴇᴅ: <code>{deleted}</code>
❌ ꜰᴀɪʟᴇᴅ: <code>{unsuccessful}</code></b>
<i>➪ To cancel: <b>/cancel</b></i>"""
            await pls_wait.edit(status); last_update_percentage = percent_complete

    final_status = f"""<b>{complete_msg}
<blockquote>Final:</b> [{final_progress_bar}] {percent_complete:.0%}</blockquote>
<b>🚻 ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: <code>{len(query)}</code>
👥 ꜱᴋɪᴘᴘᴇᴅ: <code>{skipped}</code>
📤 ᴛᴀʀɢᴇᴛ: <code>{total}</code>
✅ ꜱᴜᴄᴄᴇꜱꜱ: <code>{successful}</code>
🚫 ʙʟᴏᴄᴋᴇᴅ: <code>{blocked}</code>
⚠️ ᴅᴇʟᴇᴛᴇᴅ: <code>{deleted}</code>
❌ ꜰᴀɪʟᴇᴅ: <code>{unsuccessful}</code></b>"""
    await pls_wait.edit(final_status)

# --- Delete Broadcast ---
@Client.on_message(filters.command('dbroadcast') & filters.private & is_admin)
async def delete_broadcast(client, message):
    global is_canceled
    async with cancel_lock: is_canceled = False

    if not message.reply_to_message:
        msg = await message.reply("⚠️ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴡɪᴛʜ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ.\nᴜsᴀɢᴇ: /dbroadcast <seconds>")
        await asyncio.sleep(8)
        return await msg.delete()

    try:
        duration = int(message.command[1])
    except:
        return await message.reply("⚠️ ɪɴᴠᴀʟɪᴅ ᴅᴜʀᴀᴛɪᴏɴ.\nᴜsᴀɢᴇ: <code>/dbroadcast 10</code>", parse_mode=ParseMode.HTML)

    query, total, successful, blocked, deleted, unsuccessful = await full_userbase(), 0,0,0,0,0
    pls_wait = await message.reply("<i>ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ᴡɪᴛʜ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ...</i>")

    for i, chat_id in enumerate(query, start=1):
        async with cancel_lock:
            if is_canceled:
                return await pls_wait.edit(f"❌ ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ᴄᴀɴᴄᴇʟᴇᴅ ᴀꜰᴛᴇʀ {i-1} ᴜꜱᴇʀꜱ.")

        try:
            sent_msg = await message.reply_to_message.copy(chat_id)
            await asyncio.sleep(duration)
            await sent_msg.delete()
            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            successful += 1 if await safe_copy(message.reply_to_message, client, chat_id, "copy") else unsuccessful + 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except:
            unsuccessful += 1

    await pls_wait.edit(f"""<b><u>📤 ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴡɪᴛʜ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</u></b>
🚻 ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: <code>{len(query)}</code>
✅ sᴜᴄᴄᴇꜱꜱғᴜʟ: <code>{successful}</code>
🚫 ʙʟᴏᴄᴋᴇᴅ: <code>{blocked}</code>
⚠️ ᴅᴇʟᴇᴛᴇᴅ: <code>{deleted}</code>
❌ ғᴀɪʟᴇᴅ: <code>{unsuccessful}</code>""", parse_mode=ParseMode.HTML)

@Client.on_message(filters.command("addfsub") & is_admin)
async def add_fsub(client: Client, message: Message):
    pro = await message.reply("<b><i>🔄 Pʀᴏᴄᴇssɪɴɢ...</i></b>", quote=True)
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Cʟᴏsᴇ ✖️", callback_data="close")]])

    if len(message.command) < 2:
        return await pro.edit(
            "<b>❗ Uꜱᴀɢᴇ:</b>\n<blockquote><code>/addfsub @channel_username</code></blockquote>",
            parse_mode=ParseMode.HTML, reply_markup=btn
        )

    raw = message.command[1]
    chat_input = raw if raw.startswith("@") else int(raw)

    try:
        member = await client.get_chat_member(chat_input, client.me.id)
        if member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}:
            return await pro.edit(
                "<b>❌ I'ᴍ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴀᴛ ᴄʜᴀɴɴᴇʟ.</b>\n"
                "<blockquote>➤ Pʟᴇᴀsᴇ ᴘʀᴏᴍᴏᴛᴇ ᴍᴇ ᴀs <b>ᴀᴅᴍɪɴ</b> ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.</blockquote>",
                parse_mode=ParseMode.HTML, reply_markup=btn
            )

        chat = await client.get_chat(chat_input)
        real_id = int(chat.id)  # ✅ always use resolved int ID
        link = chat.invite_link or await client.export_chat_invite_link(real_id)

        await add_channel(real_id)  # ✅ store correct int ID

        await pro.edit(
            f"<b>✅ Fᴏʀᴄᴇ-Sᴜʙ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ</b>\n\n"
            f"<blockquote><b>📌 Nᴀᴍᴇ:</b> <a href='{link}'>{chat.title}</a>\n"
            f"<b>🆔 Iᴅ:</b> <code>{real_id}</code></blockquote>",
            parse_mode=ParseMode.HTML, reply_markup=btn, disable_web_page_preview=True
        )
    except Exception as e:
        await pro.edit(
            f"<b>❌ Fᴀɪʟᴇᴅ ᴛᴏ ᴀᴅᴅ ғᴏʀᴄᴇ-sᴜʙ ᴄʜᴀɴɴᴇʟ.</b>\n\n"
            f"<blockquote><code>{e}</code></blockquote>\n"
            f"<i>➤ Pʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ/ID ᴀɴᴅ ʙᴏᴛ ᴘᴇʀᴍɪssɪᴏɴs.</i>",
            parse_mode=ParseMode.HTML, reply_markup=btn
        )


@Client.on_message(filters.command("listfsub") & is_admin)
async def list_fsub(client, message):
    channels = await get_all_channels()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("ᴄʟᴏsᴇ ✖️", callback_data="close")]])

    if not channels:
        return await message.reply("<b>❌ ɴᴏ ғᴏʀᴄᴇ-sᴜʙ ᴄʜᴀɴɴᴇʟs ꜱᴇᴛ.</b>", reply_markup=kb)

    text = "<b>📋 ғᴏʀᴄᴇ-sᴜʙ ᴄʜᴀɴɴᴇʟs:</b>\n\n"

    for chat_id in channels:
        try:
            chat = await client.get_chat(int(chat_id))
            link = chat.invite_link or await client.export_chat_invite_link(int(chat_id))
            text += (
                f"<b><blockquote>"
                f"ɴᴀᴍᴇ: <a href='{link}'>{chat.title}</a>\n"
                f"(ɪᴅ: <code>{chat.id}</code>)"
                f"</blockquote></b>\n\n"
            )
        except:
            text += (
                f"<b><blockquote>"
                f"ɪᴅ: <code>{chat_id}</code>\n"
                f"<i>ᴜɴᴀʙʟᴇ ᴛᴏ ʟᴏᴀᴅ ᴅᴇᴛᴀɪʟs.</i>"
                f"</blockquote></b>\n\n"
            )

    await message.reply(text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@Client.on_message(filters.command("delfsub") & is_admin)
async def delete_fsub(client, message):
    if len(message.command) < 2:
        return await message.reply("<b>❌ Uꜱᴀɢᴇ: <code>/delfsub [ɪᴅ / @ᴜꜱᴇʀɴᴀᴍᴇ]</code></b>")

    x = message.command[1].strip()

    # Parse input into chat_id
    try:
        chat_input = x if x.startswith("@") else int(x)
    except ValueError:
        return await message.reply("<b>❌ Iɴᴠᴀʟɪᴅ ɪᴅ / ᴜꜱᴇʀɴᴀᴍᴇ.</b>")

    # Try to resolve chat details, but don't fail if bot isn't a member
    chat_id = None
    title = str(chat_input)
    try:
        chat = await client.get_chat(chat_input)
        chat_id = int(chat.id)
        title = chat.title
    except Exception:
        # Bot may not be in the channel — use raw ID directly
        if isinstance(chat_input, int):
            chat_id = chat_input
        else:
            return await message.reply("<b>❌ Cᴏᴜʟᴅɴ'ᴛ ʀᴇꜱᴏʟᴠᴇ ᴜꜱᴇʀɴᴀᴍᴇ. ᴛʀʏ ᴜꜱɪɴɢ ᴛʜᴇ ɴᴜᴍᴇʀɪᴄ ɪᴅ.</b>")

    try:
        deleted = await remove_channel(chat_id)
    except Exception as e:
        return await message.reply(f"<b>❌ Eʀʀᴏʀ: {e}</b>")

    if deleted:
        return await message.reply(f"<b>✅ Rᴇᴍᴏᴠᴇᴅ: {title} (<code>{chat_id}</code>)</b>", parse_mode=ParseMode.HTML)

    return await message.reply("<b>❌ Nᴏᴛ ғᴏᴜɴᴅ ɪɴ ʟɪꜱᴛ.</b>")
# --- Shortener Commands ---
@Client.on_message(filters.command("add_shortner") & is_admin)
async def add_shortener_cmd(client, message):
    try:
        _, api, key = message.text.split(" ", 2)
    except ValueError:
        return await message.reply("<b>⚠️ ᴜsᴀɢᴇ:</b>\n<code>/add_shortner api_url api_key</code>", parse_mode=ParseMode.HTML)
    await add_shortener(api, key)
    await message.reply(f"✅ sʜᴏʀᴛᴇɴᴇʀ <code>{api}</code> ᴀᴅᴅᴇᴅ.", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("del_shortner") & is_admin)
async def del_shortener_cmd(client, message):
    try:
        _, api = message.text.split(" ", 1)
    except ValueError:
        return await message.reply("<b>⚠️ ᴜsᴀɢᴇ:</b>\n<code>/del_shortner api_url</code>", parse_mode=ParseMode.HTML)
    await remove_shortener(api)
    await message.reply(f"🗑️ sʜᴏʀᴛᴇɴᴇʀ <code>{api}</code> ʀᴇᴍᴏᴠᴇᴅ.", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("list_shortner") & is_admin)
async def list_shortener_cmd(client, message):
    shorteners = await list_shorteners()
    if not shorteners:
        return await message.reply("❌ ɴᴏ sʜᴏʀᴛᴇɴᴇʀs ᴄᴏɴꜰɪɢᴜʀᴇᴅ.", parse_mode=ParseMode.HTML)

    text = "<b>📌 ᴀᴠᴀɪʟᴀʙʟᴇ sʜᴏʀᴛᴇɴᴇʀs:</b>\n\n" + "\n".join([f"🔗 <code>{s['api']}</code>" for s in shorteners])
    await message.reply(text, parse_mode=ParseMode.HTML)

# ---------------- ᴛᴏᴋᴇɴ sᴛᴀᴛs ----------------
@Client.on_message(filters.command("token") & is_admin)
async def token_stats_cmd(client, message):
    loading = await message.reply_text("<b>⏳ ғᴇᴛᴄʜɪɴɢ ᴛᴏᴋᴇɴ sᴛᴀᴛs...</b>")
    txt, kb = await build_token_panel()
    await loading.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

# ---------------- ʙᴜɪʟᴅ ᴛᴏᴋᴇɴ ᴘᴀɴᴇʟ ----------------
async def build_token_panel():
    s = await get_settings()
    tutorial_url = s.get("tutorial_url", "https://t.me/BotzGarage/10")
    shorteners = await list_shorteners()
    total_tokens = len(shorteners)

    txt = (
        "<b>🔐 ᴛᴏᴋᴇɴ sᴛᴀᴛs</b>\n\n"
        f"🧮 <b>ᴛᴏᴛᴀʟ ᴀᴘɪs:</b> {total_tokens}\n"
        f"🎓 <b>ᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ:</b> <code>{tutorial_url}</code>\n\n"
        "<blockquote>➪ Use below buttons to manage tutorial URL & APIs.</blockquote>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ᴀᴅᴅ sʜᴏʀᴛɴᴇʀ", callback_data="add_api_key"),InlineKeyboardButton("🗑 ᴅᴇʟ sʜᴏʀᴛɴᴇʀ", callback_data="delete_api")],
        [InlineKeyboardButton("🎓 sᴇᴛ ᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ", callback_data="set_tutorial_url")],
        [
            InlineKeyboardButton("♻️ ʀᴇꜰʀᴇꜱʜ", callback_data="refresh_token_stats"),
            InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_token_stats")
        ]
    ])

    return txt, kb

# ------------------ Verified Users Stats ------------------
@Client.on_message(filters.command("verification") & is_admin)
async def verified_stats(client, message):
    await send_verified_stats(client, message.chat.id)

async def send_verified_stats(client, chat_id, message_id=None):
    now_ist = datetime.now(IST)
    today_midnight = datetime(now_ist.year, now_ist.month, now_ist.day, tzinfo=IST)
    yesterday_midnight = today_midnight - timedelta(days=1)
    tomorrow_midnight = today_midnight + timedelta(days=1)

    week_start = today_midnight - timedelta(days=today_midnight.weekday())
    next_week_start = week_start + timedelta(days=7)

    month_start = datetime(now_ist.year, now_ist.month, 1, tzinfo=IST)
    next_month_start = datetime(now_ist.year + 1 if now_ist.month == 12 else now_ist.year,
                                1 if now_ist.month == 12 else now_ist.month + 1, 1, tzinfo=IST)

    def to_utc_ts(dt): return int(dt.astimezone(timezone.utc).timestamp())

    today_start = to_utc_ts(today_midnight)
    yesterday_start = to_utc_ts(yesterday_midnight)
    tomorrow_start = to_utc_ts(tomorrow_midnight)
    week_start_ts = to_utc_ts(week_start)
    next_week_start_ts = to_utc_ts(next_week_start)
    month_start_ts = to_utc_ts(month_start)
    next_month_start_ts = to_utc_ts(next_month_start)
    now_ts = int(datetime.now(timezone.utc).timestamp())

    total_verified = await user_data.count_documents({
        "verify_status.is_verified": True,
        "$expr": {"$gt": [{"$add": ["$verify_status.verified_time", VERIFY_EXPIRE]}, now_ts]}
    })
    today_verified = await user_data.count_documents({
        "verify_status.is_verified": True,
        "verify_status.verified_time": {"$gte": today_start, "$lt": tomorrow_start}
    })
    yesterday_verified = await user_data.count_documents({
        "verify_status.is_verified": True,
        "verify_status.verified_time": {"$gte": yesterday_start, "$lt": today_start}
    })
    week_verified = await user_data.count_documents({
        "verify_status.is_verified": True,
        "verify_status.verified_time": {"$gte": week_start_ts, "$lt": next_week_start_ts}
    })
    month_verified = await user_data.count_documents({
        "verify_status.is_verified": True,
        "verify_status.verified_time": {"$gte": month_start_ts, "$lt": next_month_start_ts}
    })

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴛᴏᴛᴀʟ ᴠᴇʀɪғɪᴇᴅ", callback_data="noop"),InlineKeyboardButton(str(total_verified), callback_data="noop")],
        [InlineKeyboardButton("ᴛᴏᴅᴀʏ", callback_data="noop"),InlineKeyboardButton(str(today_verified), callback_data="noop")],
        [InlineKeyboardButton("ʏᴇsᴛᴇʀᴅᴀʏ", callback_data="noop"),InlineKeyboardButton(str(yesterday_verified), callback_data="noop")],
        [InlineKeyboardButton("ᴛʜɪs ᴡᴇᴇᴋ", callback_data="noop"),InlineKeyboardButton(str(week_verified), callback_data="noop")],
        [InlineKeyboardButton("ᴛʜɪs ᴍᴏɴᴛʜ", callback_data="noop"),InlineKeyboardButton(str(month_verified), callback_data="noop")],
        [InlineKeyboardButton("🔄 ʀᴇꜰʀᴇꜱʜ", callback_data="refresh_verification_stats")]
    ])

    if message_id:await client.edit_message_text(chat_id, message_id, "<blockquote>✅ <b>Vᴇʀɪғɪᴇᴅ Usᴇʀs Sᴛᴀᴛs</b></blockquote>",
                                       reply_markup=keyboard)
    else:await client.send_message(chat_id, "<blockquote>✅ <b>Vᴇʀɪғɪᴇᴅ Usᴇʀs Sᴛᴀᴛs</b></blockquote>",
                                  reply_markup=keyboard)

async def ruser(client, x):
    try:
        if x.startswith("@"): return (await client.get_users(x)).id
        return int(x)
    except: return None

@Client.on_message(filters.command("addpaid") & is_admin)
async def add_paid(client, m):
    a = m.text.split()
    if len(a) < 3: 
        return await m.reply("Usage: /addpaid <id/@user> <time>")
    uid = await ruser(client, a[1])
    if not uid: return await m.reply("❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ")

    exp = datetime.now(IST) + parse_time_string(a[2])
    await user_data.update_one({"_id": uid},
        {"$set": {"premium": True, "premium_expiry": int(exp.timestamp())}}, upsert=True)

    await m.reply(f"✅ ᴀᴅᴅᴇᴅ ᴘʀᴇᴍɪᴜᴍ ᴛɪʟʟ <b>{exp:%d-%b-%Y %I:%M %p}</b>")

@Client.on_message(filters.command("envelope") & is_admin)
async def make_claim_link(c,m):
    cid=str((await claim_links.insert_one({
        "max_claims":10,
        "claimed_users":[],
        "duration":604800
    })).inserted_id)

    await m.reply(
        f"<b>ᴘʀᴇᴍɪᴜᴍ ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ</b>\n"
        f"👥 ғɪʀsᴛ 10 ᴜsᴇʀs • ⏳ 7 ᴅᴀʏs\n\n"
        f"<blockquote><b>https://t.me/{c.me.username}?start=claim_{cid}</b></blockquote>",
        parse_mode=ParseMode.HTML
    )


import pytz as pt

@Client.on_message(filters.command("myplan"))
async def check_plan(client, message):
    user_id = message.from_user.id
    user = await user_data.find_one({"_id": user_id})

    if not user or not user.get("premium"):return await message.reply_text("<b>🔓 ʏᴏᴜ ᴀʀᴇ ᴏɴ ᴛʜᴇ ғʀᴇᴇ ᴘʟᴀɴ. 😂</b>")
    expiry_ts = user.get("premium_expiry")
    if not expiry_ts:return await message.reply_text("⚠️ ᴘʀᴇᴍɪᴜᴍ sᴛᴀᴛᴜs ᴇɴᴀʙʟᴇᴅ, ʙᴜᴛ ɴᴏ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ sᴇᴛ.")

    ist = pt.timezone("Asia/Kolkata")
    expiry_str = datetime.fromtimestamp(expiry_ts, tz=ist).strftime("%d-%b-%Y %I:%M %p")
    await message.reply_text(f"⭐ ʏᴏᴜ ᴀʀᴇ ᴏɴ <b>ᴘʀᴇᴍɪᴜᴍ</b>\n⏳ ᴇxᴘɪʀᴇs ᴏɴ: <b>{expiry_str}</b>")


@Client.on_message(filters.command("removepaid") & is_admin)
async def remove_paid(client, m):
    a = m.text.split()
    if len(a) < 2: return await m.reply("Usage: /removepaid <id/@user>")
    uid = await ruser(client, a[1])
    if not uid: return await m.reply("❌ ɪɴᴠᴀʟɪᴅ")

    await user_data.update_one({"_id": uid}, {"$set": {"premium": False, "premium_expiry": 0}})
    await m.reply(f"❌ ʀᴇᴍᴏᴠᴇᴅ ᴘʀᴇᴍɪᴜᴍ ꜰʀᴏᴍ <code>{uid}</code>")

# # from pyrogram import Client, filters
# # from pyrogram.types import Message
# # from datetime import datetime
# # from config import ADMIN_IDS
# # from database.database import user_data, db  # your new DB module

# from db2 import *

# @Client.on_message(filters.command("migrate"))
# async def migrate_premium_cmd(client: Client, message: Message):
#     """
#     Migrate old premium users to the new user_data collection format.
#     Only active (not expired) users are migrated.
#     """
#     await message.reply("🚀 Starting premium user migration...")

#     # Fetch all old premium users
#     old_users = await db.get_premium_users()
#     now_ts = int(datetime.now().timestamp())
#     migrated_count = 0

#     for u in old_users:
#         expiry_ts = u.get("expiry_time")
#         if not expiry_ts or expiry_ts < now_ts:
#             continue  # skip expired users

#         # New user document in user_data
#         await user_data.update_one(
#             {"_id": u["_id"]},
#             {
#                 "$set": {
#                     "premium": True,
#                     "premium_expiry": expiry_ts
#                 }
#             },
#             upsert=True
#         )
#         migrated_count += 1

#     await message.reply(f"✅ Migration complete!\nTotal users migrated: {migrated_count}")

from datetime import datetime
import pytz

@Client.on_message(filters.command("listpaid") & is_admin)
async def list_paid(client, m):
    now = int(time.time())

    # Expire users automatically
    await user_data.update_many(
        {"premium": True, "premium_expiry": {"$lte": now}},
        {"$set": {"premium": False}}
    )

    users = await user_data.find(
        {"premium": True, "premium_expiry": {"$gt": now}}
    ).to_list(None)

    if not users:
        return await m.reply("❌ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴘᴀɪᴅ ᴜsᴇʀs")
    
    total = len(users)
    header = f"💎 <b>sᴛᴀᴛs • ᴀᴄᴛɪᴠᴇ ᴘᴀɪᴅ ᴜsᴇʀs ( {total} )</b>\n\n<blockquote expandable>"
    footer = "</blockquote>"
    chunk = header

    ist = pytz.timezone("Asia/Kolkata")

    for u in users:
        try:
            usr = await client.get_users(u["_id"])
            name = f"@{usr.username}" if usr.username else usr.first_name
        except:
            name = "❌ Deleted"

        exp_ts = u.get("premium_expiry", 0)

        # Skip invalid timestamps
        if not isinstance(exp_ts, (int, float)) or exp_ts <= 0:
            exp_str = "❌ Invalid date"
        else:
            exp_str = datetime.fromtimestamp(exp_ts, tz=ist).strftime("%d-%b-%Y %I:%M %p")

        line = f"• {name} (<code>{u['_id']}</code>) — <b>{exp_str}</b>\n"

        if len(chunk) + len(line) + len(footer) > 4000:
            await m.reply(chunk + footer, parse_mode=ParseMode.HTML)
            chunk = header

        chunk += line

    await m.reply(chunk + footer, parse_mode=ParseMode.HTML)


# ------------------ Utility ------------------
def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


# ------------------ Bot Status ------------------
@Client.on_message(filters.command("status") & is_admin)
async def bot_status(client, message):
    await send_bot_stats(client, message.chat.id)

async def send_bot_stats(client, chat_id, message_id=None):
    stats_doc = await settings_data.find_one({"_id": "bot_stats"}) or {}

    # Fetch the updated stats for images, videos, and documents
    images_downloaded = stats_doc.get("images_downloaded", 0)
    videos_downloaded = stats_doc.get("videos_downloaded", 0)
    documents_downloaded = stats_doc.get("documents_downloaded", 0)  # New field for document type files
    bandwidth_used = stats_doc.get("bandwidth_used", 0)

    # Formatting the bot status message
    text = (
        f"<b><blockquote>» ʙᴏᴛ sᴛᴀᴛs</blockquote></b>\n\n"
        f"<b>• ɪᴍᴀɢᴇs ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ</b>: <code>{images_downloaded}</code>\n"
        f"<b>• ᴠɪᴅᴇᴏs ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ</b>: <code>{videos_downloaded}</code>\n"
        f"<b>• ᴅᴏᴄᴜᴍᴇɴᴛs ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ</b>: <code>{documents_downloaded}</code>\n"
    )

    # Creating a refresh button to update the stats
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 ʀᴇꜰʀᴇꜱʜ", callback_data="refresh_status")]])

    if message_id:
        await client.edit_message_text(chat_id, message_id, text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


# ------------------ Bot Control ------------------
@Client.on_message(filters.command("restart") & is_admin)
async def restart_bot(client, message):
    msg = await message.reply_text("<b>🔄 Rᴇsᴛᴀʀᴛɪɴɢ ʙᴏᴛ...</b>")
    sys.stdout.flush()
    await msg.edit_text("<b>✅ Rᴇsᴛᴀʀᴛᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ..!</b>")
    os.execv(sys.executable, [sys.executable] + sys.argv)


PROJECT_PATH = "/app"  # Adjust this path as necessary

@Client.on_message(filters.command("update"))
async def update_bot(client, message):
    # if message.from_user.id != OWNER_ID:return await message.reply_text("<b>❌ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴏɴʟʏ..</b>")
    msg = await message.reply_text("<b>📥 ᴜᴘᴅᴀᴛɪɴɢ ᴄᴏᴅᴇ ꜰʀᴏᴍ ɢɪᴛʜᴜʙ...</b>")
    
    # Run git pull in project directory
    git_pull = await run_cmd("git pull", cwd=PROJECT_PATH)
    
    # Filter and format output
    lines = ["✅ Uᴘᴅᴀᴛᴇᴅ:"]
    for l in git_pull.splitlines():
        if not l.startswith(("From ", " * branch")):
            lines.append(l)
    lines += ["", "♻️ Rᴇsᴛᴀʀᴛɪɴɢ ʙᴏᴛ..."]
    
    await msg.edit("<b>{}</b>".format("\n".join(lines)), parse_mode=ParseMode.HTML)
    
    # Restart bot
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)

async def run_cmd(cmd, cwd=None):
    """Run a shell command asynchronously and return combined stdout+stderr."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    result = out.decode().strip()
    if err:
        result += "\n" + err.decode().strip()
    return result

# ------------------ Referral System ------------------
@Client.on_message(filters.command("toggle_refer") & is_admin)
async def toggle_refer_command(client, message):
    text, kb = await get_referral_panel()
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def get_referral_panel():
    s = await settings_data.find_one({"_id": "bot_settings"}) or {}
    refer_mode = s.get("referral_mode", False)
    reward = s.get("referral_reward", "1d")  # default reward

    status_text = (
        "✅ ʀᴇғᴇʀ ᴍᴏᴅᴇ ᴇɴᴀʙʟᴇᴅ"
        if refer_mode else
        "❌ ʀᴇғᴇʀ ᴍᴏᴅᴇ ᴅɪsᴀʙʟᴇᴅ"
    )
    text = f"<b>{status_text}</b>\n<b>• ʀᴇꜰᴇʀ ʀᴇᴡᴀʀᴅ:</b> <code>{reward}</code>\n\nClick below to manage."

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ᴛᴏɢɢʟᴇ ʀᴇғᴇʀ ᴍᴏᴅᴇ", callback_data="toggle_referral_mode")],
        [InlineKeyboardButton("🎁 sᴇᴛ ʀᴇꜰᴇʀ ʀᴇᴡᴀʀᴅ", callback_data="set_referral_reward")]
    ])
    return text, kb

@Client.on_message(filters.command("set_free_limit") & is_admin)
async def set_free_limit(client, message):
    if not message.from_user: return
    try:
        n = int(message.text.split()[1])
        await settings_data.update_one({"_id":"bot_settings"}, {"$set":{"free_limit":n}}, upsert=True)
        await message.reply_text(f"<b>✅ ᴅᴀɴɢᴇʀ ғʀᴇᴇ ʟɪᴍɪᴛ sᴇᴛ ᴛᴏ {n}</b>")
    except:await message.reply_text("<b>❌ ᴜsᴀɢᴇ: /set_free_limit 10</b>")

@Client.on_message(filters.command("reset_free_count") & is_admin)
async def reset_free_count(client, message):
    if not message.from_user: return
    await user_data.update_many({}, {"$set":{"free_media_count":0}})
    await message.reply_text("<b>✅ ᴅᴀɴɢᴇʀ ᴀʟʟ ᴜsᴇʀ ꜰʀᴇᴇ ᴄᴏᴜɴᴛ ʀᴇsᴇᴛ</b>")


@Client.on_message(filters.command("check_refers") & is_admin)
async def check_refers(client, message_or_callback, edit=False):
    users = await user_data.find({"referrals": {"$gt": 0}}, {"_id": 1, "referrals": 1}).to_list(None)
    if not users:
        text = "❌ ɴᴏ ʀᴇғᴇʀs ʏᴇᴛ."
        if edit: await message_or_callback.edit_text(text)
        else: await message_or_callback.reply_text(text)
        return

    total_referrals = sum(u["referrals"] for u in users)
    users.sort(key=lambda x: x["referrals"], reverse=True)
    header = f"<b>🏆 ᴛᴏᴘ ʀᴇғᴇʀs : ({total_referrals})</b>\n\n"
    text = header

    for u in users:
        try:
            user = await client.get_users(u['_id'])
            name = f"@{user.username}" if user.username else f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        except: name = f"<code>{u['_id']}</code>"

        line = f"• <b>{name}</b> — {u['referrals']} ʀᴇғᴇʀs\n"
        if len(text + line) > 4000:
            if edit: await message_or_callback.edit_text(text, parse_mode=ParseMode.HTML)
            else: await message_or_callback.reply_text(text, parse_mode=ParseMode.HTML)
            text = header
        text += line
    if text != header:
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 ʀᴇꜰʀᴇsʜ", callback_data="refresh_refers")]])
        if edit: await message_or_callback.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        else: await message_or_callback.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

import config

@Client.on_message(filters.command("waiting_timer") & is_admin)
async def cooldown_status(client, message):

    status = "🟢 <b>ᴇɴᴀʙʟᴇᴅ</b>" if config.waiting_timer_status else "🔴 <b>ᴅɪsᴀʙʟᴇᴅ</b>"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔘 ᴛᴏɢɢʟᴇ ᴄᴏᴏʟᴅᴏᴡɴ", callback_data="toggle_cooldown")]]
    )

    await message.reply_text(
        f"<b>ᴄᴏᴏʟᴅᴏᴡɴ sᴛᴀᴛᴜs:</b> {status}",
        reply_markup=keyboard,
    )


@Client.on_callback_query(filters.regex("^toggle_cooldown$"))
async def toggle_cooldown_cb(client, cq):

    config.waiting_timer_status = not config.waiting_timer_status

    status = "🟢 <b>ᴇɴᴀʙʟᴇᴅ</b>" if config.waiting_timer_status else "🔴 <b>ᴅɪsᴀʙʟᴇᴅ</b>"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔘 ᴛᴏɢɢʟᴇ ᴄᴏᴏʟᴅᴏᴡɴ", callback_data="toggle_cooldown")]]
    )

    await cq.message.edit_text(
        f"<b>ᴄᴏᴏʟᴅᴏᴡɴ sᴛᴀᴛᴜs:</b> {status}",
        reply_markup=keyboard,
    )

    await cq.answer("✅ ᴄᴏᴏʟᴅᴏᴡɴ ᴜᴘᴅᴀᴛᴇᴅ")
