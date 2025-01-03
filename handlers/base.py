from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states.states import BotStates

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать!\nИспользуйте меню для управления ботом.",
        reply_markup=get_main_keyboard()
    )

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск групп"), KeyboardButton(text="👥 Поиск пользователей")],
            [KeyboardButton(text="📋 Просмотреть группы"), KeyboardButton(text="❌ Удалить группу")],
            [KeyboardButton(text="➕ Добавить группу вручную"), KeyboardButton(text="📨 Рассылка инвайтов")],
            [KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

@router.message(F.text == "⚙️ Настройки")
async def text_settings(message: Message, state: FSMContext):
    await message.answer(
        f"Текущие настройки:\n- Лимит парсинга: 500 групп в день\n- Лимит инвайтов: 50 пользователей в день\n\n"
        f"Введите новые значения через пробел (парсинг, инвайты):"
    )
    await state.set_state(BotStates.waiting_for_settings)

@router.message(BotStates.waiting_for_settings)
async def settings_handler(message: Message, state: FSMContext):
    try:
        parse_limit, invite_limit = map(int, message.text.split())
        await message.answer(f"Настройки обновлены:\n- Лимит парсинга: {parse_limit} групп в день\n- Лимит инвайтов: {invite_limit} пользователей в день")
    except ValueError:
        await message.answer("Некорректный формат данных. Введите два числа через пробел.")
    await state.clear()
