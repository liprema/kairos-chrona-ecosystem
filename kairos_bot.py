import os
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

def get_main_keyboard(user_id: int):
    kb = [
        [KeyboardButton(text="🏛 Steam: Мифология"), KeyboardButton(text="🕹 Яндекс.Игры")],
        [KeyboardButton(text="💡 Брейншторм / Бизнес"), KeyboardButton(text="🚀 Проекты в работе")],
        [KeyboardButton(text="⏳ Запрос к Хроне (Тайминги)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    db.set_user_mode(user_id, "steam_myth")
    
    greeting = (
        "⚡️ <b>Салют! Я Кайрос</b> — твой партнёр по вайбкодингу и бизнес-эдвайзер.\n\n"
        "Мы работаем в связке с <b>Хроной</b> (она рулит расписанием и бережёт от выгорания).\n\n"
        "<b>В чём я могу помочь прямо сейчас:</b>\n"
        "• 🏛 <b>Steam & Мифы</b> — лор Хроник Акаши, пантеоны богов, механики, вишлисты и страница игры.\n"
        "• 🕹 <b>Яндекс.Игры</b> — быстрые концепты, удержание, монетизация и WebGL.\n"
        "• 💡 <b>Бизнес-консалтинг</b> — разбор любых сторонних идей, MVP за выходные.\n"
        "• 🚀 <b>Взять в работу</b> — превратим идею в проект и сразу поставим слоты Хроне!\n\n"
        "<i>Выбирай режим в меню ниже или просто пиши, что на уме!</i>"
    )
    await message.answer(greeting, reply_markup=get_main_keyboard(user_id))

@dp.message(F.text == "🏛 Steam: Мифология")
async def mode_steam(message: types.Message):
    db.set_user_mode(message.from_user.id, "steam_myth")
    await message.answer(
        "🏛 <b>Режим «Steam: Мифология & Путешествия души» активен!</b>\n\n"
        "Погружаемся в Хроники Акаши, пантеоны богов и нарратив. О какой главе или механике думаем?"
    )

@dp.message(F.text == "🕹 Яндекс.Игры")
async def mode_yandex(message: types.Message):
    db.set_user_mode(message.from_user.id, "yandex_games")
    await message.answer(
        "🕹 <b>Режим «Яндекс.Игры» активен!</b>\n\n"
        "Фокус на быстрых циклах, высоком ретеншне и кликабельных механиках. Какую игру пилим или тестируем?"
    )

@dp.message(F.text == "💡 Брейншторм / Бизнес")
async def mode_consulting(message: types.Message):
    db.set_user_mode(message.from_user.id, "consulting")
    await message.answer(
        "💡 <b>Режим «Бизнес-консалтинг» активен!</b>\n\n"
        "Накидывай любые стартап-идеи или гипотезы. Разберём ЦА, монетизацию и подводные камни. "
        "Если идея огонь — сразу возьмём в работу!"
    )

@dp.message(F.text == "⏳ Запрос к Хроне (Тайминги)")
async def check_timings(message: types.Message):
    workload = bridge.get_workload_status_for_kairos("polina")
    await message.answer(
        f"⏳ <b>Сводка от Хроны по твоему расписанию:</b>\n\n"
        f"<blockquote>{workload}</blockquote>\n"
        f"<i>Я учитываю это при планировании наших спринтов!</i>"
    )

@dp.message(F.text == "🚀 Проекты в работе")
@dp.message(Command("projects"))
async def list_projects(message: types.Message):
    projects = db.get_active_projects()
    if not projects:
        await message.answer(
            "🚀 <b>Проекты в работе:</b>\n\n"
            "Пока нет активных кастомных проектов в работе.\n"
            "Обсудим идею в режиме 💡 <b>Брейншторм</b> и запустим?"
        )
        return

    text = "🚀 <b>Твои активные проекты в работе:</b>\n\n"
    inline_kb = []
    for p in projects:
        text += (
            f"▫️ <b>{p['title']}</b>\n"
            f"   ▸ Категория: <code>{p['category']}</code>\n"
            f"   ▸ Дедлайн: <code>{p['deadline'] or 'гибкий'}</code>\n\n"
        )
        inline_kb.append([InlineKeyboardButton(text=f"🎯 Фокус: {p['title']}", callback_data=f"select_proj_{p['id']}")])

    text += "<i>Нажми кнопку ниже, чтобы переключить контекст обсуждения:</i>"
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
        f"🎯 <b>Режим переключен на проект:</b> <code>{project['title']}</code>\n\n"
        f"<blockquote>Дедлайн: {project['deadline'] or 'гибкий'}\n"
        f"Теперь держу весь контекст этого бизнеса в фокусе.</blockquote>\n"
        f"С чего начнём спринт?"
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
    
    # Синхронизация с Хроной
    await bridge.notify_chrona_about_new_project(project_id, user_chat_id=callback.from_user.id)
    
    await callback.message.answer(
        f"🚀 <b>Отлично, идея взята в работу!</b>\n\n"
        f"▫️ Создан проект ID: <code>#{project_id}</code>\n"
        f"▫️ Хрона уже получила уведомление и запланировала майлстоуны!\n\n"
        f"<i>Переименовать проект можно командой:</i> <code>/rename новое имя</code>"
    )
    await callback.answer()

@dp.message(Command("take"))
async def cmd_take_project(message: types.Message):
    """Взять конкретный проект: /take Название проекта"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "⚠️ <b>Укажи название проекта</b>, например:\n"
            "<code>/take Сервис открыток со славянскими богами</code>"
        )
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
    
    # Сигнал Хроне
    await bridge.notify_chrona_about_new_project(project_id, user_chat_id=message.from_user.id)
    
    await message.answer(
        f"🚀 Проект <b>«{title}»</b> успешно запущен и взят в работу!\n\n"
        f"<blockquote>Режим переключен. Хрона добавила контрольные точки в твой календарь.</blockquote>"
    )

@dp.message()
async def on_user_message(message: types.Message):
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
            [InlineKeyboardButton(text="🚀 Взять эту идею в работу!", callback_data="take_in_work_current")]
        ])
    
    try:
        await message.answer(reply, reply_markup=inline_kb)
    except Exception:
        # Резервный вариант, если в HTML закралась ошибка разметки
        await message.answer(reply, reply_markup=inline_kb, parse_mode=None)

async def main():
    if not KAIROS_TOKEN:
        print("❌ KAIROS_BOT_TOKEN не задан в .env!")
        return
    bot = Bot(token=KAIROS_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("⚡️ Кайрос (Вайбкодинг-партнёр) запущен и готов к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
