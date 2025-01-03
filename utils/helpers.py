import re
from typing import Optional, Dict, List, Union
from datetime import datetime, timedelta
import logging
from telethon.tl.types import User, Channel, Chat

logger = logging.getLogger(__name__)

def validate_username(username: str) -> str:
    """
    Проверка и форматирование username
    """
    # Убираем @ если есть
    username = username.lstrip('@')
    
    # Проверяем формат
    if not re.match(r'^[a-zA-Z]\w{3,30}[a-zA-Z0-9]$', username):
        raise ValueError("Неверный формат username")
    
    return username

def format_time_remaining(seconds: int) -> str:
    """
    Форматирование оставшегося времени
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours} ч. {minutes} мин."
    return f"{minutes} мин."

def calculate_invite_stats(
    total_users: int,
    daily_limit: int,
    current_invited: int
) -> Dict[str, Union[int, str]]:
    """
    Расчет статистики и времени для инвайтинга
    """
    remaining_users = total_users - current_invited
    remaining_days = (remaining_users + daily_limit - 1) // daily_limit
    total_time = remaining_days * 24  # часы
    
    return {
        "remaining_users": remaining_users,
        "remaining_days": remaining_days,
        "total_time": f"{total_time} часов",
        "daily_limit": daily_limit,
        "progress_percent": round((current_invited / total_users) * 100, 1)
    }

async def extract_entity_info(entity: Union[User, Channel, Chat]) -> Optional[Dict[str, str]]:
    """
    Извлечение информации из Telethon entity
    """
    try:
        if isinstance(entity, (Channel, Chat)):
            return {
                "id": str(entity.id),
                "name": entity.title,
                "username": entity.username if hasattr(entity, 'username') else None,
                "type": "channel" if isinstance(entity, Channel) else "chat"
            }
        elif isinstance(entity, User):
            return {
                "id": str(entity.id),
                "name": f"{entity.first_name or ''} {entity.last_name or ''}".strip(),
                "username": entity.username,
                "type": "user"
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при извлечении информации: {e}")
        return None

def format_group_info(group_data: Dict[str, str]) -> str:
    """
    Форматирование информации о группе
    """
    return (
        f"📊 Информация о группе:\n"
        f"📝 Название: {group_data['name']}\n"
        f"🔗 Username: @{group_data['username']}\n"
        f"🆔 ID: {group_data['id']}"
    )

def check_invite_limits(
    last_invite_date: Optional[datetime],
    decline_date: Optional[datetime],
    daily_limit: int,
    current_count: int
) -> Dict[str, Union[bool, str]]:
    """
    Проверка ограничений для инвайтинга
    """
    now = datetime.now()
    result = {"can_invite": False, "reason": ""}

    # Проверка дневного лимита
    if current_count >= daily_limit:
        result["reason"] = f"Достигнут дневной лимит ({daily_limit} приглашений)"
        return result

    # Проверка времени после отказа
    if decline_date:
        days_since_decline = (now - decline_date).days
        if days_since_decline < 30:
            result["reason"] = f"Нужно подождать еще {30 - days_since_decline} дней после отказа"
            return result

    # Проверка последнего приглашения
    if last_invite_date:
        hours_since_invite = (now - last_invite_date).total_seconds() / 3600
        if hours_since_invite < 24:
            result["reason"] = f"Нужно подождать еще {format_time_remaining(int((24 - hours_since_invite) * 3600))}"
            return result

    result["can_invite"] = True
    return result

def generate_progress_bar(current: int, total: int, length: int = 20) -> str:
    """
    Создание прогресс-бара
    """
    filled = int(length * current / total)
    bar = '█' * filled + '░' * (length - filled)
    percent = round(100 * current / total, 1)
    return f"{bar} {percent}%"

def format_invite_status(stats: Dict[str, int]) -> str:
    """
    Форматирование статуса инвайтинга
    """
    total = stats["total"]
    invited = stats["invited"]
    declined = stats["declined"]
    not_invited = stats["not_invited"]
    
    progress_bar = generate_progress_bar(invited, total)
    
    return (
        f"📊 Статус инвайтинга:\n"
        f"{progress_bar}\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"✅ Приглашено: {invited}\n"
        f"⛔️ Отказов: {declined}\n"
        f"⏳ Ожидает приглашения: {not_invited}"
    )

def validate_group_link(link: str) -> Optional[str]:
    """
    Проверка и извлечение username из ссылки на группу
    """
    # Паттерны для разных форматов ссылок
    patterns = [
        r'(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z]\w{3,30}[a-zA-Z0-9])',
        r'@([a-zA-Z]\w{3,30}[a-zA-Z0-9])',
        r'^([a-zA-Z]\w{3,30}[a-zA-Z0-9])$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    
    return None
