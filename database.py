import motor.motor_asyncio
from config import DB_URI, DB_NAME
from typing import Optional
import time
import random
from datetime import datetime

# ------------------ MongoDB Client ------------------
dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
database = dbclient[DB_NAME]

# ------------------ Collections ------------------
user_data = database['users']
admins_data = database['admins']
transactions = database["transactions"]
settings_data = database['settings']
banned_users_data = database['banned_users']
dump_data = database['dumps']

channel_data = database['channels']  # force-sub channels
rqst_fsub_Channel_data = database['rqst_fsub_channels']  # private join requests
store_reqLink_data = database['store_reqLink']  # invite links
request_forcesub_data = database['force_sub_status']  # toggle for FSub
shorteners_data = database['shorteners']
batches_data = database["batches"]
free_trial_data = database['free_trials']  # MongoDB collection for free trial tracking
claim_links = database["claim_links"]

# ------------------ Default Templates ------------------
default_verify = {
    'is_verified': False,
    'verified_time': 0,
    'verify_token': "",
    'created_time': 0,      # ✅ FIX
    'bypass_warns': 0,      # ✅ FIX
    'link': ""
}

# ------------------ User Functions ------------------
def new_user(user_id: int):
    return {
        '_id': user_id,
        'verify_status': default_verify.copy(),
        'premium': False,
        'premium_expiry': 0,
        'referrals': 0,
        'referral_points': 0,
        'purchased_points': 0,
        'purchased_files': [],
        'free_media_count': 0,
        'joined': int(time.time())
    }

async def add_user(user_id: int):
    if not await user_data.find_one({"_id": user_id}):
        await user_data.insert_one(new_user(user_id))

async def count_users():
    return await user_data.count_documents({})

async def full_userbase() -> list[int]:
    users = await user_data.find({}, {"_id": 1}).to_list(None)
    return [u["_id"] for u in users]

async def del_user(user_id: int):
    await user_data.delete_one({"_id": user_id})
    await banned_users_data.delete_one({"_id": user_id})

# ------------------ Admin Functions ------------------
async def add_admin(user_id: int):
    if not await admins_data.find_one({"_id": user_id}):
        await admins_data.insert_one({"_id": user_id})

async def del_admin(user_id: int):
    await admins_data.delete_one({"_id": user_id})

async def admin_exist(user_id: int) -> bool:
    return bool(await admins_data.find_one({"_id": user_id}))

async def get_all_admins() -> list[int]:
    admins = await admins_data.find({}, {"_id": 1}).to_list(None)
    return [a["_id"] for a in admins]

async def count_admins():
    return await admins_data.count_documents({})

async def is_premium_user(uid: int) -> bool:
    """⚡ ᴄʜᴇᴄᴋ ɪꜰ ᴜꜱᴇʀ ɪꜱ ᴘʀᴇᴍɪᴜᴍ"""
    u = await user_data.find_one({"_id": uid})
    if not u:
        return False

    now_ts = int(datetime.now().timestamp())
    premium_expiry = u.get("premium_expiry", 0)
    is_premium = u.get("premium") and (premium_expiry == 0 or premium_expiry > now_ts)

    # 🕓 ᴀᴜᴛᴏ ᴇxᴘɪʀᴇ ᴏᴜᴛᴅᴀᴛᴇᴅ ᴘʀᴇᴍɪᴜᴍꜱ
    if u.get("premium") and premium_expiry <= now_ts and premium_expiry != 0:
        await user_data.update_one(
            {"_id": uid},
            {"$set": {"premium": False, "premium_expiry": 0}}
        )
        is_premium = False

    return bool(is_premium)

# ------------------ Ban Functions ------------------
async def ban_user(user_id: int):
    if not await banned_users_data.find_one({"_id": user_id}):
        await banned_users_data.insert_one({"_id": user_id})

async def unban_user(user_id: int):
    await banned_users_data.delete_one({"_id": user_id})

async def is_banned(user_id: int) -> bool:
    return bool(await banned_users_data.find_one({"_id": user_id}))

async def count_banned_users():
    return await banned_users_data.count_documents({})

# ------------------ Settings ------------------
async def get_settings():
    settings = await settings_data.find_one({"_id": "bot_settings"})
    if not settings:
        settings = {"protect_content": False, "auto_delete": 0, "auto_delete_on": False}
        await settings_data.insert_one({"_id": "bot_settings", **settings})
    else:
        if "auto_delete_on" not in settings:
            settings["auto_delete_on"] = settings.get("auto_delete", 0) > 0
            await settings_data.update_one(
                {"_id": "bot_settings"}, {"$set": {"auto_delete_on": settings["auto_delete_on"]}}
            )
    return settings

async def update_settings(field, value):
    await settings_data.update_one({"_id": "bot_settings"}, {"$set": {field: value}})

# ------------------ Dump Management ------------------
async def add_dump(chat_id: int):
    if not await dump_data.find_one({"_id": chat_id}):
        await dump_data.insert_one({"_id": chat_id})

async def del_dump(chat_id: int):
    await dump_data.delete_one({"_id": chat_id})

async def get_all_dumps() -> list[int]:
    dumps = await dump_data.find({}, {"_id": 1}).to_list(None)
    return [d["_id"] for d in dumps]

async def count_dumps():
    return await dump_data.count_documents({})

# ------------------ Force Subscribe Channels ------------------
async def get_all_channels() -> list:
    channel_docs = await channel_data.find().to_list(None)
    return [doc['_id'] for doc in channel_docs if '_id' in doc]

async def channel_exist(channel_id: int) -> bool:
    channel_id = int(channel_id)
    return bool(await channel_data.find_one({'_id': channel_id}))

async def add_channel(channel_id: int):
    channel_id = int(channel_id)  # always store as int
    if not await channel_exist(channel_id):
        await channel_data.insert_one({'_id': channel_id})

async def remove_channel(channel_id: int) -> bool:
    channel_id = int(channel_id)
    result = await channel_data.delete_one({'_id': channel_id})
    return result.deleted_count > 0
# ------------------ Request Force Subscribe Toggle ------------------
async def get_request_forcesub() -> bool:
    data = await request_forcesub_data.find_one({"_id": "req_fsub"})
    return data.get('value', False) if data else False

async def set_request_forcesub(value: bool):
    await request_forcesub_data.update_one(
        {"_id": "req_fsub"},
        {"$set": {"value": value}},
        upsert=True
    )

# ------------------ Private Channel Request Management ------------------
async def add_reqChannel(channel_id: int):
    await rqst_fsub_Channel_data.update_one(
        {'_id': channel_id},
        {'$setOnInsert': {'user_ids': []}},
        upsert=True
    )

async def reqChannel_exist(channel_id: int) -> bool:
    return bool(await rqst_fsub_Channel_data.find_one({'_id': channel_id}))

async def del_reqChannel(channel_id: int):
    await rqst_fsub_Channel_data.delete_one({'_id': channel_id})

async def reqSent_user_exist(channel_id: int, user_id: int) -> bool:
    return bool(await rqst_fsub_Channel_data.find_one(
        {'_id': channel_id, 'user_ids': user_id}
    ))

async def reqSent_user(channel_id: int, user_id: int):
    await rqst_fsub_Channel_data.update_one(
        {'_id': channel_id},
        {'$addToSet': {'user_ids': user_id}},
        upsert=True
    )


async def del_reqSent_user(channel_id: int, user_id: int):
    await rqst_fsub_Channel_data.update_one(
        {'_id': channel_id},
        {'$pull': {'user_ids': user_id}}
    )

# ------------------ Invite Links ------------------
async def get_stored_reqLink(channel_id: int) -> Optional[str]:
    data = await store_reqLink_data.find_one({'_id': channel_id})
    return data.get('link') if data else None

async def store_reqLink(channel_id: int, link: str):
    await store_reqLink_data.update_one(
        {'_id': channel_id},
        {'$set': {'link': link}},
        upsert=True
    )

# ------------------ Shortener Management ------------------
async def add_shortener(api: str, key: str):
    await shorteners_data.update_one(
        {"_id": api},
        {"$set": {"api": api, "key": key}},
        upsert=True
    )

async def remove_shortener(api: str):
    await shorteners_data.delete_one({"_id": api})

async def list_shorteners():
    return await shorteners_data.find().to_list(None)

async def get_random_shortener():
    shorteners = await shorteners_data.find().to_list(None)
    if not shorteners:
        return None
    return random.choice(shorteners)

# ------------------ Refer ------------------
async def is_refer_enabled() -> bool:
    s = await settings_data.find_one({"_id": "bot_settings"})
    if not s:
        await settings_data.insert_one({"_id": "bot_settings", "refer_mode": True})
        return True
    return s.get("refer_mode", True)

async def toggle_refer() -> bool:
    current = await is_refer_enabled()
    await settings_data.update_one({"_id": "bot_settings"}, {"$set": {"refer_mode": not current}}, upsert=True)
    return not current

# ------------------ Premium ------------------
async def add_premium(user_id: int, days: int = 0, hours: int = 0):
    user = await user_data.find_one({"_id": user_id})
    now = int(time.time())
    current_expiry = user.get("premium_expiry", 0)
    additional_time = days * 24 * 3600 + hours * 3600
    new_expiry = max(current_expiry, now) + additional_time
    await user_data.update_one({"_id": user_id}, {"$set": {"premium": True, "premium_expiry": new_expiry}})

# ------------------ Transactions ------------------
async def is_transaction_used(txn_id: str) -> bool:
    txn = await transactions.find_one({"txn_id": txn_id})
    return txn is not None

async def mark_transaction_used(user_id: int, txn_id: str, plan: str, amount: float, date: str):
    await transactions.insert_one({
        "user_id": user_id,
        "txn_id": txn_id,
        "plan": plan,
        "amount": amount,
        "date": date,
        "used_at": int(time.time())
    })

async def get_user_transactions(user_id: int):
    cursor = transactions.find({"user_id": user_id}).sort("used_at", -1)
    return await cursor.to_list(length=50)
