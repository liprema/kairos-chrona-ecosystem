import os
import re
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database import EcosystemDB
from llm_service import LLMService
from shared_bridge import BridgeService

load_dotenv()

KAIROS_TOKEN = os.getenv("KAIROS_BOT_TOKEN")
CHRONA_TOKEN = os.getenv("CHRONA_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "/tmp/kairos_chrona/data/ecosystem.db")

db = EcosystemDB(DB_PATH)
llm = LLMService()
bridge = BridgeService(db, chrona_token=CHRONA_TOKEN, kairos_token=KAIROS_TOKEN)

dp = Dispatcher()
bot_info: types.User = None

def get_main_keyboard(user_id: int):
    kb = [
        [KeyboardButton(text="🏛 Steam: Мифология"), KeyboardButton(text="🕹 Яндекс.Игры")],
        [KeyboardButton(text="💡 Брейншторм / Бизнес"), KeyboardButton(text="🚀 Проекты в работе")],
        [KeyboardButton(text="⏳ Запрос к Хроне (Тайминги)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def is_addressed_to_kairos(message: types.Message) -> bool:
    """Проверяет, адресовано ли сообщение Кайросу в группе или ЛС"""
    if message.chat.type == "private":
        return True

    # Ответ на сообщение Кайроса
    if message.reply_to_message and message.reply_to_message.from_user:
        if bot_info and message.reply_to_message.from_user.id == bot_info.id:
            return True

    text = (message.text or message.caption or "").lower()
    if not text:
        return False

    # Упоминание юзернейма (@kairos_bot)
    if bot_info and bot_info.username and f"@{bot_info.username.lower()}" in text:
        return True

    # Обращение по имени (Кайрос, Кайросу, Кайросом и т.д.)
    patterns = [r"\bкайрос\b", r"\bкайроса\b", r"\bкайросу\b", r"\bкайросом\b", r"\bкайросе\b", r"\bkairos\b"]
    for pat in patterns:
        if re.search(pat, text):
            return True

    return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_addressed_to_kairos(message):
        return

    user_id = message.from_user.id
    db.set_user_mode(user_id, "steam_myth")
    
    greeting = (
        "⚡️ <b>Салют! Я Кайрос</b> — твой партнёр по вайбкодингу и инди-проектам.\n\n"
        "Работаем в тандеме с <b>Хроной</b> (она держит расписание).\n\n"
        "• 🏛 <b>Steam & Мифы</b> (Хроники Акаши, боги, квесты)\n"
        "• 🕹 <b>Яндекс.Игры</b> (быстрые циклы, WebGL, удержание)\n"
        "• 💡 <b>Брейншторм</b> (любые стартап-идеи и MVP)\n"
        "• 🚀 <b>Проекты</b> (запуск спринта с фиксацией у Хроны)\n\n"
        "<i>На связи! Выбирай тему внизу или пиши так.</i>"
    )
    await message.answer(greeting, reply_markup=get_main_keyboard(user_id))

@dp.message(F.text == "🏛 Steam: Мифология")
async def mode_steam(message: types.Message):
    db.set_user_mode(message.from_user.id, "steam_myth")
    await message.answer(
        "🏛 <b>Режим «Steam: Мифология»!</b>\n"
        "Хроники Акаши, пантеоны и сюжет. О какой главе или механике думаем?"
    )

@dp.message(F.text == "🕹 Яндекс.Игры")
async def mode_yandex(message: types.Message):
    db.set_user_mode(message.from_user.id, "yandex_games")
    await message.answer(
        "🕹 <b>Режим «Яндекс.Игры»!</b>\n"
        "Фокус на быстрых механиках и ретеншне. Какую игру пилим или тестим?"
    )

@dp.message(F.text == "💡 Брейншторм / Бизнес")
async def mode_consulting(message: types.Message):
    db.set_user_mode(message.from_user.id, "consulting")
    await message.answer(
        "💡 <b>Режим «Бизнес-консалтинг»!</b>\n"
        "Накидывай идеи. Прикинем ЦА, монетизацию и MVP."
    )

@dp.message(F.text == "⏳ Запрос к Хроне (Тайминги)")
async def check_timings(message: types.Message):
    workload = bridge.get_workload_status_for_kairos("polina")
    await message.answer(
        f"⏳ <b>Сводка от Хроны:</b>\n\n"
        f"<blockquote>{workload}</blockquote>\n"
        f"<i>Учитываю при планировании спринтов.</i>"
    )

@dp.message(F.text == "🚀 Проекты в работе")
@dp.message(Command("projects"))
async def list_projects(message: types.Message):
    if not is_addressed_to_kairos(message):
        return

    projects = db.get_active_projects()
    if not projects:
        await message.answer("🚀 Пока нет активных проектов. Обсудим идею в 💡 <b>Брейншторме</b>?")
        return

    text = "🚀 <b>Проекты в работе:</b>\n\n"
    inline_kb = []
    for p in projects:
        text += f"▫️ <b>{p['title']}</b> (дедлайн: <code>{p['deadline'] or 'гибкий'}</code>)\n"
        inline_kb.append([InlineKeyboardButton(text=f"🎯 {p['title']}", callback_data=f"select_proj_{p['id']}")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb))

@dp.callback_query(F.data.startswith("select_proj_"))
async def on_project_selected(callback: types.CallbackQuery):
    proj_id = int(callback.data.replace("select_proj_", ""))
    project = db.get_project_by_id(proj_id)
    if not project:
        await callback.answer("Проект не найден")
        return

    db.set_user_mode(callback.from_user.id, f"project_{proj_id}", active_project_id=proj_id)
    await callback.message.answer(
        f"🎯 <b>Фокус на проекте:</b> <code>{project['title']}</code>\n"
        f"Дедлайн: <code>{project['deadline'] or 'гибкий'}</code>. С чего начнём?"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("take_in_work_"))
async def on_take_in_work(callback: types.CallbackQuery):
    code = f"proj_{int(callback.message.date.timestamp())}"
    title = "Новая бизнес-инициатива"
    
    project_id = db.add_project(
        code=code,
        title=title,
        description="Проект создан по результатам брейншторма",
        category="custom_business",
        owner="polina"
    )
    db.set_user_mode(callback.from_user.id, f"project_{project_id}", active_project_id=project_id)
    await bridge.notify_chrona_about_new_project(project_id, user_chat_id=callback.from_user.id)
    
    await callback.message.answer(
        f"🚀 <b>Взяли в работу!</b> ID: <code>#{project_id}</code>.\n"
        f"Хрона зафиксировала спринты. Переименовать: <code>/rename новое имя</code>"
    )
    await callback.answer()

@dp.message(Command("take"))
async def cmd_take_project(message: types.Message):
    if not is_addressed_to_kairos(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажи название: <code>/take Сервис открыток</code>")
        return
        
    title = args[1].strip()
    code = f"proj_{int(message.date.timestamp())}"
    
    project_id = db.add_project(
        code=code,
        title=title,
        description="Запущен через прямое добавление",
        category="custom_business",
        owner="polina"
    )
    db.set_user_mode(message.from_user.id, f"project_{project_id}", active_project_id=project_id)
    await bridge.notify_chrona_about_new_project(project_id, user_chat_id=message.from_user.id)
    
    await message.answer(f"🚀 Проект <b>«{title}»</b> взят в работу! Хрона добавила контрольные точки.")

@dp.message()
async def on_user_message(message: types.Message):
    # В группе отвечает ТОЛЬКО если обращаются к Кайросу
    if not is_addressed_to_kairos(message):
        return

    user_id = message.from_user.id
    state = db.get_user_mode(user_id)
    mode = state.get("active_mode", "steam_myth")
    
    project_context = None
    if mode.startswith("project_") and state.get("active_project_id"):
        proj = db.get_project_by_id(state["active_project_id"])
        if proj:
            project_context = f"Название: {proj['title']}\nОписание: {proj['description']}\nДедлайн: {proj['deadline']}"

    workload = bridge.get_workload_status_for_kairos("polina")
    
    reply = llm.generate_kairos_reply(
        user_message=message.text or "",
        mode=mode,
        project_context=project_context,
        workload_info=workload
    )
    
    inline_kb = None
    if mode == "consulting":
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Взять в работу", callback_data="take_in_work_current")]
        ])
    
    try:
        await message.answer(reply, reply_markup=inline_kb)
    except Exception:
        await message.answer(reply, reply_markup=inline_kb, parse_mode=None)

async def main():
    global bot_info
    if not KAIROS_TOKEN:
        print("❌ KAIROS_BOT_TOKEN не задан в .env!")
        return
    bot = Bot(token=KAIROS_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot_info = await bot.get_me()
    print(f"⚡️ Кайрос (@{bot_info.username}) запущен и слушает эфир...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
