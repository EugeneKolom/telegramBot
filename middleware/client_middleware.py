from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from telethon import TelegramClient
import os

class TelethonClientMiddleware(BaseMiddleware):
    def __init__(self, client: TelegramClient = None):
        super().__init__()
        self.clients: Dict[int, TelegramClient] = {}
        self.default_client = client
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
            
            if user_id not in self.clients:
                if self.default_client:
                    self.clients[user_id] = self.default_client
                else:
                    session_name = f"user_{user_id}"
                    if os.path.exists(f"{session_name}.session"):
                        client = TelegramClient(session_name, API_ID, API_HASH)
                        await client.connect()
                        if await client.is_user_authorized():
                            self.clients[user_id] = client
            
            data["telethon_client"] = self.clients.get(user_id)
        
        return await handler(event, data) 