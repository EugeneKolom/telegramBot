from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from ..states.states import BotStates

router = Router()

@router.message(F.text == "💎 Премиум")
async def premium_info(message: Message):
    await message.answer(
        "💎 Премиум доступ:\n\n"
        "✅ Увеличенные лимиты\n"
        "✅ Приоритетная поддержка\n"
        "✅ Дополнительные функции\n\n"
        "Стоимость: $XX/месяц",
        reply_markup=get_payment_keyboard()
    ) 