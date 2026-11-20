import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import aiohttp
from database import EcosystemDB

class BridgeService:
    def __init__(self, db: EcosystemDB, chrona_token: Optional[str] = None, kairos_token: Optional[str] = None):
        self.db = db
        self.chrona_token = chrona_token
        self.kairos_token = kairos_token

    async def send_tg_notification(self, bot_token: str, chat_id: int, text: str):
        """Отправка системного сообщения через Telegram Bot API"""
        if not bot_token or not chat_id:
            return
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload)
        except Exception as e:
            print(f"Failed to send notification: {e}")

    async def notify_chrona_about_new_project(self, project_id: int, user_chat_id: Optional[int] = None):
        """Кайрос сообщает Хроне о новом проекте в работе"""
        project = self.db.get_project_by_id(project_id)
        if not project:
            return

        # Создаем базовый дедлайн-слот в расписании Хроны
        deadline_date = project["deadline"]
        if not deadline_date:
            # По умолчанию ставим спринт на 14 дней вперед
            deadline_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

        self.db.add_schedule_item(
            user_role=project["owner"],
            title=f"🎯 Дедлайн/Майлстоун проекта: {project['title']}",
            category="business",
            project_id=project_id,
            scheduled_date=deadline_date,
            user_id=user_chat_id
        )

        message = (
            f"✨ <b>Хрона на связи!</b>\n\n"
            f"Кайрос только что зафиксировал новый проект в работе: <b>«{project['title']}»</b>!\n"
            f"📌 Категория: {project['category']}\n"
            f"📅 Предварительный дедлайн: {deadline_date}\n\n"
            f"Я уже занесла майлстоун в расписание и запланирую рабочие слоты, чтобы вы не перегружались учёбой."
        )

        if self.chrona_token and user_chat_id:
            await self.send_tg_notification(self.chrona_token, user_chat_id, message)

        return message

    def get_workload_status_for_kairos(self, user_role: str = "polina") -> str:
        """Кайрос проверяет у Хроны текущую загрузку на ближайшие 7 дней"""
        today = datetime.now().strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        summary = self.db.get_user_workload_summary(user_role, today, next_week)

        academic = summary.get("academic", 0)
        business = summary.get("business", 0)

        if academic > 4:
            return f"⚠️ Внимание: У тебя сейчас плотная академическая неделя ({academic} учебных слотов/задач). Не бери слишком большой скоуп по кодингу прямо сейчас!"
        elif academic + business == 0:
            return "🟢 График на неделю свободен! Отличное время для глубокого вайбкодинг-спринта."
        else:
            return f"ℹ️ Баланс на неделю: {academic} учебных задач, {business} проектных задач. Идём по графику."
