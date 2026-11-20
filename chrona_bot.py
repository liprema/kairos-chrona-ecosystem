import os
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

def get_chrona_keyboard():
    kb = [
        [KeyboardButton(text="📅 Мой план на сегодня"), KeyboardButton(text="🗓 План на завтра")],
        [KeyboardButton(text="🎓 Академические дедлайны"), KeyboardButton(text="💼 Бизнес-слоты & Игры")],
        [KeyboardButton(text="📊 Семейный баланс (Я + Муж)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    greeting = (
        "🌸 <b>Привет! Я Хрона</b> — твоя личная хранительница времени и баланса.\n\n"
        "Я слежу за вашим с мужем академическим и бизнес-расписанием, чтобы дедлайны закрывались легко, "
        "а вайбкодинг не превращался в перегруз и бессонные ночи.\n\n"
        "Мы синхронизированы с <b>Кайросом</b>: когда вы берёте новый проект в работу, "
        "он передаёт мне информацию, и я бронирую под него спринты.\n\n"
        "<b>Что я умею:</b>\n"
        "• 📅 Вести раздельные графики: <i>Учёба / Игры / Проекты</i>\n"
        "• 🕹 Следить за дедлайнами мужа по Яндекс.Играм и твоими по Steam\n"
        "• 💬 Добавлять дела на обычном языке (просто напиши мне дату и задачу)!\n\n"
        "<i>Посмотрим расписание на сегодня?</i>"
    )
    await message.answer(greeting, reply_markup=get_chrona_keyboard())

@dp.message(F.text == "📅 Мой план на сегодня")
async def plan_today(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    items = db.get_schedule_for_date(today, user_role="polina")
    
    if not items:
        await message.answer(
            "🌿 <b>На сегодня слотов пока нет</b>\n\n"
            "<blockquote>Идеальный день для творческого потока, медитации или спокойного отдыха!</blockquote>"
        )
        return

    text = f"📅 <b>Расписание на сегодня ({today}):</b>\n\n"
    for it in items:
        cat_icon = "🎓" if it["category"] == "academic" else "💼"
        text += (
            f"{cat_icon} <b>{it['title']}</b>\n"
            f"   ▸ <i>Слот:</i> <code>{it['time_slot'] or 'В течение дня'}</code>\n"
        )
    await message.answer(text)

@dp.message(F.text == "🗓 План на завтра")
async def plan_tomorrow(message: types.Message):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    items = db.get_schedule_for_date(tomorrow, user_role="polina")
    
    if not items:
        await message.answer(
            "🌿 <b>На завтра задач пока нет</b>\n\n"
            "<i>Напиши мне, если нужно зафиксировать встречу или спринт!</i>"
        )
        return

    text = f"🗓 <b>Расписание на завтра ({tomorrow}):</b>\n\n"
    for it in items:
        cat_icon = "🎓" if it["category"] == "academic" else "💼"
        text += (
            f"{cat_icon} <b>{it['title']}</b>\n"
            f"   ▸ <i>Слот:</i> <code>{it['time_slot'] or 'В течение дня'}</code>\n"
        )
    await message.answer(text)

@dp.message(F.text == "🎓 Академические дедлайны")
async def view_academic(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schedule_items WHERE category = 'academic' AND scheduled_date >= ? ORDER BY scheduled_date ASC LIMIT 10", (today,))
        items = [dict(r) for r in cursor.fetchall()]

    if not items:
        await message.answer(
            "🎓 <b>Ближайших учебных дедлайнов нет!</b>\n\n"
            "Чтобы добавить, напиши:\n"
            "<code>/add academic 2026-11-25 Зачет по философии</code>"
        )
        return

    text = "🎓 <b>Твои академические задачи и дедлайны:</b>\n\n"
    for it in items:
        text += f"▫️ <code>{it['scheduled_date']}</code> ▸ <b>{it['title']}</b> <i>({it['time_slot'] or 'Весь день'})</i>\n"
    await message.answer(text)

@dp.message(F.text == "💼 Бизнес-слоты & Игры")
async def view_business(message: types.Message):
    active_projects = db.get_active_projects()
    text = "💼 <b>Проекты в работе и игровые спринты:</b>\n\n"
    if not active_projects:
        text += "<i>Пока нет активных проектов.</i>\n"
    else:
        for p in active_projects:
            text += f"▫️ <b>{p['title']}</b> ▸ <i>Дедлайн:</i> <code>{p['deadline'] or 'в процессе'}</code>\n"
            
    await message.answer(text)

@dp.message(F.text == "📊 Семейный баланс (Я + Муж)")
async def view_family_balance(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    p_summary = db.get_user_workload_summary("polina", today, next_week)
    h_summary = db.get_user_workload_summary("husband", today, next_week)
    
    text = (
        "⚖️ <b>Семейный баланс на ближайшие 7 дней:</b>\n\n"
        "🌸 <b>Полина:</b>\n"
        f"• Академические задачи: <code>{p_summary.get('academic', 0)}</code>\n"
        f"• Бизнес и Steam: <code>{p_summary.get('business', 0)}</code>\n\n"
        "⚡️ <b>Муж:</b>\n"
        f"• Яндекс.Игры & Бизнес: <code>{h_summary.get('business', 0)}</code>\n"
        f"• Учёба / Академ: <code>{h_summary.get('academic', 0)}</code>\n\n"
        "<blockquote>💡 <b>Совет от Хроны:</b> запланируйте хотя бы один совместный вечер без кодинга и дедлайнов! ☕️</blockquote>"
    )
    await message.answer(text)

@dp.message(Command("add"))
async def cmd_add_task(message: types.Message):
    """Быстрое добавление задачи: /add <academic|business> <YYYY-MM-DD> <Описание>"""
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer(
            "⚠️ <b>Формат команды:</b>\n"
            "<code>/add academic 2026-11-25 Сдать зачёт</code>\n"
            "или\n"
            "<code>/add business 2026-11-28 Релиз билда</code>"
        )
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
    await message.answer(
        f"✅ <b>Зафиксировала!</b>\n\n"
        f"▫️ Задача: <b>{title}</b>\n"
        f"▫️ Дата: <code>{date_str}</code>\n"
        f"▫️ Категория: <code>{category}</code>"
    )

@dp.message()
async def on_user_message(message: types.Message):
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
    if not CHRONA_TOKEN:
        print("❌ CHRONA_BOT_TOKEN не задан в .env!")
        return
    bot = Bot(token=CHRONA_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("🌸 Хрона (Хранительница времени) запущена и готова к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
