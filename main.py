import asyncio
import logging
import signal
import socket
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import TOKEN, API_ID, API_HASH
from database.db import Database
from handlers import (
    base_router,
    group_parsing_router,
    group_management_router,
    user_parsing_router,
    inviting_router
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from middleware.client_middleware import TelethonClientMiddleware
from handlers.invite_management import router as invite_router
from telethon.sessions import StringSession
import platform

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = None
client = None
db = None

# Получение переменных окружения
api_id = int(os.getenv('API_ID', API_ID))
api_hash = os.getenv('API_HASH', API_HASH)
string_session = os.getenv('STRING_SESSION')

async def set_commands(bot: Bot) -> None:
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Открыть главное меню"),
        BotCommand(command="help", description="Помощь")
    ]
    await bot.set_my_commands(commands)

async def setup_telethon():
    """Настройка и авторизация Telethon клиента"""
    global client
    if client is not None and client.is_connected():
        logger.info("Telethon клиент уже настроен")
        return

    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        logger.info("Требуется авторизация в Telethon")
        phone = input("Введите номер телефона (в формате +7...): ")
        await client.send_code_request(phone)
        code = input("Введите код подтверждения из Telegram: ")
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Введите пароль двухфакторной аутентификации: ")
            await client.sign_in(password=password)

    logger.info("Telethon клиент успешно авторизован")

async def ensure_client_connected():
    """Убедиться, что Telethon клиент подключен"""
    global client
    if client is None or not client.is_connected():
        logger.warning("Telethon клиент не подключен. Выполняется повторная настройка...")
        await setup_telethon()

async def start_dummy_server():
    """Создаёт фиктивный сервер, который слушает порт, чтобы удовлетворить Render"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 8000))  # Render ожидает, что приложение будет слушать порт
    server.listen(5)
    logger.info("Фиктивный сервер запущен на порту 8000")
    while True:
        await asyncio.sleep(3600)  # Поддерживаем сервер активным

async def run_bot():
    """Функция для запуска бота"""
    global bot, client, db
    logger.info("Запуск бота...")

    # Инициализация базы данных
    db = Database("bot_database.db")
    logger.info("База данных инициализирована")

    # Инициализация бота и диспетчера
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Убедиться, что клиент Telethon подключен
    await ensure_client_connected()

    # Регистрируем middleware
    dp.message.middleware(TelethonClientMiddleware(client))
    dp.callback_query.middleware(TelethonClientMiddleware(client))

    # Подключение роутеров
    dp.include_router(base_router)
    dp.include_router(group_parsing_router)
    dp.include_router(group_management_router)
    dp.include_router(user_parsing_router)
    dp.include_router(inviting_router)
    dp.include_router(invite_router)
    logger.info("Роутеры подключены")

    # Установка команд бота
    await set_commands(bot)
    logger.info("Команды бота установлены")

    try:
        logger.info("Запуск поллинга...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
        raise
    finally:
        logger.info("Завершение работы...")
        if bot:
            await bot.session.close()  # Закрываем сессию aiogram
        if client:
            await client.disconnect()  # Закрываем Telethon клиент
        if db:
            db.close()  # Закрываем базу данных

async def shutdown(signal, loop):
    """Корректное завершение работы"""
    global bot, client, db
    logger.info(f"Получен сигнал завершения: {signal}")
    if bot:
        await bot.session.close()
    if client:
        await client.disconnect()
    if db:
        db.close()
    loop.stop()

async def main():
    """Основная функция"""
    loop = asyncio.get_event_loop()
    tasks = []

    # Запускаем основные задачи
    bot_task = asyncio.create_task(run_bot())
    dummy_server_task = asyncio.create_task(start_dummy_server())
    tasks.append(bot_task)
    tasks.append(dummy_server_task)

    # Регистрируем обработчики сигналов для Unix-систем
    if platform.system() != "Windows":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(sig, loop)))

    try:
        # Ожидаем завершения всех задач
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Задачи отменены")
    except Exception as e:
        logger.error(f"Ошибка в main: {e}")
    finally:
        # Корректное завершение
        await shutdown(None, loop)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())