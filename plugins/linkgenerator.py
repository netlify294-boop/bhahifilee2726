import base64, asyncio, re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import *
from config import *
from helper import *

_temp, _batch_tasks, _batch_session = {}, {}, {}
_batch_links = {}   # <-- stores batch ids


def get_file(m):
    return (m.photo.file_id, "photo") if m.photo else \
           (m.video.file_id, "video") if m.video else \
           (m.document.file_id, "document") if m.document else \
           (m.animation.file_id, "animation") if m.animation else (None, None)


async def parse_msg(m):
    if m.forward_from_chat:
        return m.forward_from_chat.id, m.forward_from_message_id

    if m.text:
        r = re.search(r"t\.me/(?:c/)?([^/]+)/(\d+)", m.text)
        if r:
            cid = int("-100"+r.group(1)) if "/c/" in m.text else r.group(1)
            return cid, int(r.group(2))

    return None, None


async def ask_msg(c, uid, text):
    try:
        m = await c.ask(uid, text, filters=filters.forwarded | filters.text, timeout=60)
        return await parse_msg(m)
    except:
        return None, None


# ---------------- SPECIAL ENCODER ---------------- #

async def encode_batch_points(start_id: int, end_id: int, channel_id: int) -> str:
    data_string = f"{start_id}:{end_id}:{channel_id}"
    return base64.urlsafe_b64encode(data_string.encode()).decode().rstrip("=")


# ---------------- COLLECT FILES ---------------- #

# @Client.on_message(
#     (filters.text | filters.photo | filters.video | filters.document | filters.animation) 
#     & filters.private 
#     & is_admin
#     & ~filters.command(commands)
# )
# async def collect(client, m):
#     uid = m.from_user.id
#     fid, t = get_file(m)

#     if not fid:
#         return

    _temp.setdefault(uid, []).append({"file_id": fid, "type": t})
    _batch_session[uid] = _batch_session.get(uid, 0) + 1
    session = _batch_session[uid]

    if uid in _batch_tasks:
        _batch_tasks[uid].cancel()

    _batch_tasks[uid] = asyncio.create_task(
        _finalize_batch(client, m, uid, session)
    )


async def _finalize_batch(client, m, uid, session):
    try:
        await asyncio.sleep(1)
        if _batch_session.get(uid) != session:
            return

        files = _temp.pop(uid, [])
        if not files:
            return

        sent = []

        for f in files:
            try:
                msg = await getattr(client, f"send_{f['type']}")(CHANNEL_ID, f["file_id"])
                sent.append(msg.id)
                await asyncio.sleep(2)
            except:
                continue

        if not sent:
            return

        _batch_links[uid] = (sent[0], sent[-1])

        await m.reply(
            "<b>✅ ғɪʟᴇs ᴜᴘʟᴏᴀᴅᴇᴅ\n\n⚡ sᴇʟᴇᴄᴛ ʟɪɴᴋ ᴛʏᴘᴇ</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚡ ɴᴏʀᴍᴀʟ", callback_data=f"gen_normal:{uid}"),
                InlineKeyboardButton("🔥 sᴘᴇᴄɪᴀʟ", callback_data=f"gen_special:{uid}")
            ]])
        )

    except asyncio.CancelledError:
        pass
    finally:
        _batch_tasks.pop(uid, None)

@Client.on_callback_query(filters.regex(r"gen_(normal|special):(\d+)"))
async def generate_link_cb(client, cb: CallbackQuery):

    _, uid = cb.data.split(":")
    uid = int(uid)

    if cb.from_user.id != uid:
        return await cb.answer("ɴᴏᴛ ʏᴏᴜʀ ʙᴀᴛᴄʜ", show_alert=True)

    data = _batch_links.pop(uid, None)
    if not data:
        return await cb.answer("ʙᴀᴛᴄʜ ᴇxᴘɪʀᴇᴅ", show_alert=True)

    start, end = data

    # ---- NORMAL TOKEN ----
    normal_token = encode(
        f"get-{start}" if start == end else f"get-{start}-{end}"
    )

    # ---- SPECIAL TOKEN ----
    special_token = await encode_batch_points(start, end, CHANNEL_ID)

    normal_link = f"https://t.me/{client.username}?start={normal_token}"
    special_link = f"https://t.me/{client.username}?start={special_token}"

    await cb.message.edit_text(
        f"""
<b>🔗 ʏᴏᴜʀ ʟɪɴᴋs ᴀʀᴇ ʀᴇᴀᴅʏ</b>

⚡ <b>ɴᴏʀᴍᴀʟ ʟɪɴᴋ</b>
{normal_link}

🔥 <b>sᴘᴇᴄɪᴀʟ ʟɪɴᴋ</b>
{special_link}
""",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ sʜᴀʀᴇ ɴᴏʀᴍᴀʟ", url=f"https://t.me/share/url?url={normal_link}")
            ],
            [
                InlineKeyboardButton("🔥 sʜᴀʀᴇ sᴘᴇᴄɪᴀʟ", url=f"https://t.me/share/url?url={special_link}")
            ]
        ])
    )

    await cb.answer("✅ ʟɪɴᴋs ɢᴇɴᴇʀᴀᴛᴇᴅ")


@Client.on_message(filters.command("genlink") & filters.private)
async def genlink(c, m):
    uid = m.from_user.id

    ask = await c.ask(
        uid,
        "<blockquote><b>📨 sᴇɴᴅ ᴛʜᴇ ᴍᴇssᴀɢᴇ ʟɪɴᴋ ᴏʀ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ᴍsɢ\n\nᴇxᴀᴍᴘʟᴇ: https://t.me/c/3849339538/98721</b></blockquote>",
        filters=filters.text | filters.forwarded,
        timeout=60
    )

    cid, mid = await parse_msg(ask)

    if not cid or not mid:
        return await m.reply("<b>❌ ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ ᴏʀ ᴍᴇssᴀɢᴇ</b>")

    token = encode(f"get-{mid}")
    link = f"https://t.me/{c.username}?start={token}"

    await ask.reply(
        f"<b>𝗣𝗢𝗢𝗞𝗜£ 𝗚 : 🍫\n\n<blockquote>𝖧𝖾𝗋𝖾 𝗂𝗌 𝗒𝗈𝗎𝗋 𝖲𝗍𝗎𝖿𝖿 : ⬇️\n\n{link}</blockquote></b>",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ sʜᴀʀᴇ", url=f"https://t.me/share/url?url={link}")]
        ])
    )

# ---------------- MANUAL BATCH ---------------- #

# @Client.on_message(filters.command("batch") & filters.private & filters.user(ADMINS))
# async def batch(c, m):
#     f = await ask_msg(c, m.from_user.id, "<blockquote><b>sᴇɴᴅ ᴛʜᴇ ғɪʀsᴛ ᴍsɢ</b></blockquote>")
#     l = await ask_msg(c, m.from_user.id, "<blockquote><b>sᴇɴᴅ ᴛʜᴇ ʟᴀsᴛ ᴍsɢ</b></blockquote>")

#     if not f or not l:
#         return

#     cid, first = f
#     _, last = l

#     data = base64.urlsafe_b64encode(f"{cid}:{first}:{last}".encode()).decode().rstrip("=")

#     link = f"https://t.me/{c.username}?start=bhookibhabhi_{data}"

#     await m.reply_text(
#         f"<blockquote><b>ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ\n\n{link}</b></blockquote>",
#         reply_markup=InlineKeyboardMarkup(
#             [[InlineKeyboardButton("🔁 sʜᴀʀᴇ 🔁", url=f"https://t.me/share/url?url={link}")]]
#         ),
#         disable_web_page_preview=True
#     )
