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
from middleware.client_middleware import TelethonClientMiddleware
from handlers.invite_management import router as invite_router
from telethon.sessions import StringSession

# Настройка логирования
logging.basicConfig(level=logging.DEBUG) #  Включите DEBUG для просмотра всех логов
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = None
client = None
db = None

# Конфигурация вебхука
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://bot.crimea-tour.site" + WEBHOOK_PATH
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
    """Настройка и авторизация Telethon клиента через сессию"""
    global client
    if not string_session:
        logger.error("Требуется STRING_SESSION. Создайте новую сессию и укажите её в переменных окружения.")
        exit(1)

    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("Недействительная сессия. Пожалуйста, обновите STRING_SESSION.")
        await client.disconnect()
        exit(1)

    logger.info("Telethon клиент успешно авторизован с использованием сессии")

async def generate_new_session():
    """Генерация новой сессии при первом запуске"""
    temp_client = TelegramClient(StringSession(), api_id, api_hash)
    await temp_client.connect()
    
    if not await temp_client.is_user_authorized():
        logger.info("Создание новой сессии...")
        await temp_client.start()
        new_session = temp_client.session.save()
        logger.info(f"Новая сессия создана. Добавьте её в переменные окружения:\nSTRING_SESSION={new_session}")
        await temp_client.disconnect()
        exit()

async def ensure_client_connected():
    """Убедиться, что Telethon клиент подключен"""
    global client
    if client is None or not client.is_connected():
        await setup_telethon()

async def on_startup(bot: Bot) -> None:
    """Действия при запуске"""
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        ssl_certificate=open('/etc/letsencrypt/live/bot.crimea-tour.site/fullchain.pem', 'r') # Добавьте эту строку
    )
    await set_commands(bot)

async def run_bot():
    """Основная функция для запуска бота"""
    global bot, client, db
    
    # Проверка наличия обязательных переменных
    if not all([API_ID, API_HASH]):
        logger.error("Требуются API_ID и API_HASH в конфигурации")
        exit(1)

    # Генерация новой сессии если нет существующей
    if not string_session:
        await generate_new_session()

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
    await asyncio.Event().wait()

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
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        asyncio.run(shutdown())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        asyncio.run(shutdown())
        import traceback
        logger.error(traceback.format_exc())