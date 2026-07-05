from bot import Bot
from database import *
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatMemberUpdated

# ✅ When a member leaves or is removed from a chat
@Bot.on_chat_member_updated()
async def handle_chat_members(client, update: ChatMemberUpdated):
    chat_id = update.chat.id

    if await reqChannel_exist(chat_id):
        old_member = update.old_chat_member
        if not old_member or old_member.status != ChatMemberStatus.MEMBER:return

        user_id = old_member.user.id
        if await reqSent_user_exist(chat_id, user_id):await del_reqSent_user(chat_id, user_id)

# ✅ When a user sends a join request to a channel/group
@Bot.on_chat_join_request()
async def handle_join_request(client, request):
    chat_id = request.chat.id
    user_id = request.from_user.id

    if await reqChannel_exist(chat_id):
        if not await reqSent_user_exist(chat_id, user_id):await reqSent_user(chat_id, user_id)