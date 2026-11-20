import os
import re
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database import EcosystemDB
from llm_service import LLMService

load_dotenv()

CHRONA_TOKEN = os.getenv("CHRONA_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "/tmp/kairos_chrona/data/ecosystem.db")

db = EcosystemDB(DB_PATH)
llm = LLMService()
dp = Dispatcher()
bot_info: types.User = None

def get_chrona_keyboard():
    kb = [
        [KeyboardButton(text="📅 Мой план на сегодня"), KeyboardButton(text="🗓 План на завтра")],
        [KeyboardButton(text="🎓 Академические дедлайны"), KeyboardButton(text="💼 Бизнес-слоты & Игры")],
        [KeyboardButton(text="📊 Семейный баланс (Я + Муж)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def is_addressed_to_chrona(message: types.Message) -> bool:
    """Проверяет, адресовано ли сообщение Хроне в группе или ЛС"""
    if message.chat.type == "private":
        return True

    # Ответ на сообщение Хроны
    if message.reply_to_message and message.reply_to_message.from_user:
        if bot_info and message.reply_to_message.from_user.id == bot_info.id:
            return True

    text = (message.text or message.caption or "").lower()
    if not text:
        return False

    # Упоминание юзернейма (@chrona_bot)
    if bot_info and bot_info.username and f"@{bot_info.username.lower()}" in text:
        return True

    # Обращение по имени (Хрона, Хроне, Хрону, Хроной и т.д.)
    patterns = [r"\bхрона\b", r"\bхроне\b", r"\bхрону\b", r"\bхроной\b", r"\bchrona\b"]
    for pat in patterns:
        if re.search(pat, text):
            return True

    return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_addressed_to_chrona(message):
        return

    greeting = (
        "🌸 <b>Привет! Я Хрона</b> — хранительница времени и твоего баланса.\n\n"
        "Слежу за академическим расписанием, релизами и дедлайнами, чтобы не было выгорания.\n\n"
        "Синхронизирована с <b>Кайросом</b>: когда берете проект, я сразу ставлю спринты.\n\n"
        "• 📅 <i>Планы на сегодня и завтра</i>\n"
        "• 🎓 <i>Учебные зачёты и дедлайны</i>\n"
        "• 🕹 <i>Игровые спринты и баланс</i>\n\n"
        "<i>На связи! Напиши задачу или выбери кнопку ниже.</i>"
    )
    await message.answer(greeting, reply_markup=get_chrona_keyboard())

@dp.message(F.text == "📅 Мой план на сегодня")
async def plan_today(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    items = db.get_schedule_for_date(today, user_role="polina")
    
    if not items:
        await message.answer("🌿 <b>На сегодня слотов нет.</b> Можно спокойно творить или отдохнуть!")
        return

    text = f"📅 <b>Расписание на сегодня ({today}):</b>\n\n"
    for it in items:
        cat_icon = "🎓" if it["category"] == "academic" else "💼"
        text += f"{cat_icon} <b>{it['title']}</b> (<code>{it['time_slot'] or 'Весь день'}</code>)\n"
    await message.answer(text)

@dp.message(F.text == "🗓 План на завтра")
async def plan_tomorrow(message: types.Message):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    items = db.get_schedule_for_date(tomorrow, user_role="polina")
    
    if not items:
        await message.answer("🌿 <b>На завтра задач пока нет.</b> Напиши, если нужно запланировать!")
        return

    text = f"🗓 <b>Расписание на завтра ({tomorrow}):</b>\n\n"
    for it in items:
        cat_icon = "🎓" if it["category"] == "academic" else "💼"
        text += f"{cat_icon} <b>{it['title']}</b> (<code>{it['time_slot'] or 'Весь день'}</code>)\n"
    await message.answer(text)

@dp.message(F.text == "🎓 Академические дедлайны")
async def view_academic(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schedule_items WHERE category = 'academic' AND scheduled_date >= ? ORDER BY scheduled_date ASC LIMIT 10", (today,))
        items = [dict(r) for r in cursor.fetchall()]

    if not items:
        await message.answer("🎓 <b>Дедлайнов нет!</b> Добавить: <code>/add academic 2026-11-25 Зачет</code>")
        return

    text = "🎓 <b>Академические дедлайны:</b>\n\n"
    for it in items:
        text += f"▫️ <code>{it['scheduled_date']}</code> ▸ <b>{it['title']}</b>\n"
    await message.answer(text)

@dp.message(F.text == "💼 Бизнес-слоты & Игры")
async def view_business(message: types.Message):
    active_projects = db.get_active_projects()
    text = "💼 <b>Проекты в работе:</b>\n\n"
    if not active_projects:
        text += "<i>Пока нет активных проектов.</i>\n"
    else:
        for p in active_projects:
            text += f"▫️ <b>{p['title']}</b> (дедлайн: <code>{p['deadline'] or 'в процессе'}</code>)\n"
            
    await message.answer(text)

@dp.message(F.text == "📊 Семейный баланс (Я + Муж)")
async def view_family_balance(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    p_summary = db.get_user_workload_summary("polina", today, next_week)
    h_summary = db.get_user_workload_summary("husband", today, next_week)
    
    text = (
        "⚖️ <b>Баланс на 7 дней:</b>\n\n"
        f"🌸 <b>Полина:</b> учёба — <code>{p_summary.get('academic', 0)}</code>, Steam/бизнес — <code>{p_summary.get('business', 0)}</code>\n"
        f"⚡️ <b>Муж:</b> Яндекс.Игры — <code>{h_summary.get('business', 0)}</code>, учёба — <code>{h_summary.get('academic', 0)}</code>\n\n"
        "<blockquote>💡 Не забывайте про вечер отдыха без кодинга! ☕️</blockquote>"
    )
    await message.answer(text)

@dp.message(Command("add"))
async def cmd_add_task(message: types.Message):
    if not is_addressed_to_chrona(message):
        return

    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer("⚠️ Формат: <code>/add academic 2026-11-25 Сдать зачёт</code>")
        return
        
    category = parts[1].lower()
    date_str = parts[2]
    title = parts[3]
    
    db.add_schedule_item(
        user_role="polina",
        title=title,
        category=category,
        scheduled_date=date_str,
        user_id=message.from_user.id
    )
    await message.answer(f"✅ <b>Зафиксировала:</b> {title} на <code>{date_str}</code> ({category})")

@dp.message()
async def on_user_message(message: types.Message):
    # В группе отвечает ТОЛЬКО если обращаются к Хроне
    if not is_addressed_to_chrona(message):
        return

    today = datetime.now().strftime("%Y-%m-%d")
    today_items = db.get_schedule_for_date(today)
    sched_summary = f"Событий на сегодня: {len(today_items)}"
    projects = db.get_active_projects()
    proj_summary = ", ".join([p["title"] for p in projects]) or "Нет активных проектов"
    
    reply = llm.generate_chrona_reply(
        user_message=message.text or "",
        current_schedule=sched_summary,
        projects_list=proj_summary
    )
    try:
        await message.answer(reply)
    except Exception:
        await message.answer(reply, parse_mode=None)

async def main():
    global bot_info
    if not CHRONA_TOKEN:
        print("❌ CHRONA_BOT_TOKEN не задан в .env!")
        return
    bot = Bot(token=CHRONA_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot_info = await bot.get_me()
    print(f"🌸 Хрона (@{bot_info.username}) запущена и слушает эфир...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
