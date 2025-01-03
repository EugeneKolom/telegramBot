from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from ..states.states import BotStates

router = Router()

@router.message(F.text == "🔑 Авторизация")
async def start_auth(message: Message, state: FSMContext):
    await message.answer(
        "Для начала работы нужно авторизоваться.\n"
        "Введите номер телефона в формате: +79001234567"
    )
    await state.set_state(BotStates.waiting_for_phone)

@router.message(BotStates.waiting_for_phone)
async def handle_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    
    try:
        # Создаем уникальную сессию для каждого пользователя
        session_name = f"user_{message.from_user.id}"
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        
        await client.send_code_request(phone)
        await state.update_data(phone=phone)
        await state.set_state(BotStates.waiting_for_code)
        
        await message.answer(
            "Код подтверждения отправлен.\n"
            "Введите его:"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear() 