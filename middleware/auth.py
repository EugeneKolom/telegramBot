from aiogram import BaseMiddleware
from typing import Any, Callable, Dict, Awaitable
from aiogram.types import Message
from config import ADMIN_IDS

class IsAdmin:
    def __call__(self, message: Message) -> bool:
        return message.from_user.id in ADMIN_IDS 