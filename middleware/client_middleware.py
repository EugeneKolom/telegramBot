from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from telethon import TelegramClient
import os
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

class TelethonClientMiddleware(BaseMiddleware):
    def __init__(self, client: TelegramClient = None):
        super().__init__()
        self.clients: Dict[int, TelegramClient] = {}  # Словарь для хранения клиентов по user_id
        self.default_client = client  # Дефолтный клиент, если передан

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем, что событие является Message или CallbackQuery
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id  # Получаем ID пользователя

            # Если клиент для этого пользователя еще не создан
            if user_id not in self.clients:
                if self.default_client:
                    # Используем дефолтный клиент, если он передан
                    self.clients[user_id] = self.default_client
                else:
                    # Создаем новый клиент для пользователя
                    session_name = f"user_{user_id}"
                    client = TelegramClient(session_name, API_ID, API_HASH)

                    try:
                        # Подключаемся к Telegram
                        await client.connect()

                        # Проверяем, авторизован ли пользователь
                        if await client.is_user_authorized():
                            self.clients[user_id] = client
                            logger.info(f"Клиент Telethon создан для пользователя {user_id}")
                        else:
                            logger.warning(f"Пользователь {user_id} не авторизован в Telethon")
                    except Exception as e:
                        logger.error(f"Ошибка при создании клиента Telethon для пользователя {user_id}: {e}")

            # Передаем клиент в данные
            data["telethon_client"] = self.clients.get(user_id)

        # Вызываем следующий обработчик
        return await handler(event, data)