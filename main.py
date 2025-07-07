import asyncio
import os
import sys
from pyrogram import Client, idle
from src.bot import register_handlers
from src.config import API_ID, API_HASH, SESSION_FOLDER
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="DEBUG", format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}")


async def main():
    async with Client(
        name=os.path.join(SESSION_FOLDER, "userbot"),
        api_id=API_ID,
        api_hash=API_HASH
    ) as app:
        register_handlers(app)
        logger.info("Userbot запущен.")
        async for dialog in app.get_dialogs():
            logger.info(dialog.chat.first_name or dialog.chat.title)
        await idle()
    
    logger.info("Userbot остановлен.")

if __name__ == "__main__":
    asyncio.run(main())
