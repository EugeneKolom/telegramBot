import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config import TOKEN, API_ID, API_HASH
from database.db import Database
from handlers import (
    base_router,
    group_parsing_router,
    group_management_router,
    user_parsing_router,
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from middleware.client_middleware import TelethonClientMiddleware
from handlers.invite_management import router as invite_router
from telethon.sessions import StringSession

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = None
client = None
db = None

# Конфигурация вебхука
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://bot.yourdomain.com" + WEBHOOK_PATH  # Замените на свой субдомен
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 8000

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

async def on_startup(bot: Bot) -> None:
    """Действия при запуске"""
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    await set_commands(bot)

async def run_bot():
    """Основная функция для запуска бота"""
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
    dp.include_router(invite_router)
    logger.info("Роутеры подключены")

    # Настройка вебхука
    dp.startup.register(on_startup)
    
    # Создаем aiohttp приложение
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Запуск сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)
    await site.start()

    logger.info(f"Вебхук сервер запущен на {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    await asyncio.Event().wait()  # Бесконечное ожидание

async def shutdown():
    """Корректное завершение работы"""
    global bot, client, db
    logger.info("Удаление вебхука...")
    await bot.delete_webhook()
    logger.info("Вебхук удален")
    
    if bot:
        await bot.session.close()
    if client:
        await client.disconnect()
    if db:
        db.close()

if __name__ == "__main__":
    try:
        # Запускаем бота
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        asyncio.run(shutdown())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        asyncio.run(shutdown())
        import traceback
        logger.error(traceback.format_exc())