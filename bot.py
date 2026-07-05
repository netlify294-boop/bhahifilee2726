# +++ Made By Daddy [telegram username: @salesgodx] +++

from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode
import asyncio, time, pyrogram.utils
from datetime import datetime
from config import *
# from plugins.manager import *
from plugins import web_server
from pyromod import listen
# from plugins.scrapper import start_global_listener

START_TIME = time.time()
pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Bot",
            api_hash=API_HASH,
            api_id=API_ID,
            plugins={"root": "plugins"},
            workers=TG_BOT_WORKERS,
            bot_token=BOT_TOKEN
        )
        self.LOGGER = LOGGER
        self.start_time = time.time()

    async def start(self):
        await super().start()
        bot_info = await self.get_me()
        self.name, self.username = bot_info.first_name, bot_info.username
        self.uptime = datetime.now()
        self.set_parse_mode(ParseMode.HTML)
        # asyncio.create_task(start_global_listener(self))

        self.LOGGER(__name__).info(f"Aᴅᴠᴀɴᴄᴇ Fɪʟᴇ-Sʜᴀʀɪɴɢ ʙᴏᴛ Mᴀᴅᴇ Bʏ ➪ @salesgodx")
        self.LOGGER(__name__).info(f"{self.name} Bot Running..! ✅")

        # Notify owner
        try:await self.send_message(OWNER_ID, f"<b><blockquote>🤖 Bᴏᴛ Mᴀᴅᴇ Bʏ @salesgodx</blockquote></b>")
        except Exception as e:self.LOGGER(__name__).warning(f"Failed to send restart message: {e}")

    async def stop(self, *args):await super().stop()