import asyncio
import logging
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def set_commands(bot: Bot) -> None:
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Открыть главное меню"),
        BotCommand(command="help", description="Помощь")
    ]
    await bot.set_my_commands(commands)

async def setup_telethon() -> TelegramClient:
    """Настройка и авторизация Telethon клиента"""
    client = TelegramClient("bot_session", API_ID, API_HASH)
    
    try:
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
        return client
        
    except Exception as e:
        logger.error(f"Ошибка при настройке Telethon: {e}")
        raise

async def main() -> None:
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")
    
    # Инициализация базы данных
    db = Database("bot_database.db")
    logger.info("База данных инициализирована")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    
    # Настройка Telethon клиента
    client = await setup_telethon()
    
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
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            polling_timeout=30
        )
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
        raise
    finally:
        logger.info("Завершение работы...")
        await bot.session.close()
        await client.disconnect()
        db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
