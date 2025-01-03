from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from ..states.states import BotStates
from ..database.db import db
from ..middleware.auth import IsAdmin

router = Router()

@router.message(F.text == "⚙️ Админ панель", IsAdmin())
async def admin_panel(message: Message):
    stats = await db.get_admin_stats()
    await message.answer(
        f"👤 Всего пользователей: {stats['total_users']}\n"
        f"💎 Премиум пользователей: {stats['premium_users']}\n"
        f"📊 Активных сегодня: {stats['active_today']}"
    ) 