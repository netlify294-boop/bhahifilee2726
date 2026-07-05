from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.group & filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    for member in message.new_chat_members:
        if member.id == client.me.id:
            chat_title = message.chat.title

            welcome_text = (f"<b>» ʜᴇʏ ᴛʜᴀɴᴋs ғᴏʀ ᴀᴅᴅɪɴɢ ᴍᴇ ᴛᴏ ᴛʜᴇ {chat_title}</b>.\n\n")

            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇs •", url="https://t.me/bhookibhabhi")]])

            await client.send_message(chat_id=message.chat.id,text=welcome_text,reply_markup=keyboard,parse_mode=ParseMode.HTML)
