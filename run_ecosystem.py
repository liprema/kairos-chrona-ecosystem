import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def start_kairos():
    import kairos_bot
    await kairos_bot.main()

async def start_chrona():
    import chrona_bot
    await chrona_bot.main()

async def main():
    print("🚀 Запуск экосистемы Telegram-ботов: Кайрос ⚡️ + Хрона 🌸")
    await asyncio.gather(
        start_kairos(),
        start_chrona()
    )

if __name__ == "__main__":
    asyncio.run(main())
