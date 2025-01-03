from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import math
from states.states import BotStates
from database.db import Database
from config import DAILY_INVITE_LIMIT, INVITE_DELAY, DECLINE_WAIT_DAYS

router = Router()

@router.message(F.text == "📨 Приглашение пользователей")
async def text_invite_users(message: Message, state: FSMContext):
    try:
        db = Database()
        groups = db.execute("SELECT id, name, username FROM groups").fetchall()
        
        if not groups:
            await message.answer("❌ Сначала добавьте хотя бы одну группу")
            return
            
        response = "Выберите группу для приглашения пользователей (введите ID):\n\n"
        for group in groups:
            group_id, name, username = group
            response += f"ID: {group_id} | {name} (@{username})\n"
            
        await message.answer(response)
        await state.set_state(BotStates.waiting_for_invite_group_id)
    except Exception as e:
        print(f"Ошибка при получении списка групп: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

async def invite_users_to_group(message: Message, group_id, users):
    try:
        client = message.bot.get("client")
        if not client or not client.is_connected():
            await message.answer("❌ Ошибка подключения к Telegram API")
            return
            
        # Остальной код приглашения...
    except Exception as e:
        print(f"Ошибка при приглашении пользователей: {e}")
        raise

@router.message(BotStates.waiting_for_invite_group_id)
async def process_invite_group(message: Message, state: FSMContext):
    try:
        group_id = int(message.text)
        db = Database()
        
        # Проверяем существование группы
        group = db.execute(
            "SELECT username FROM groups WHERE id = ?",
            (group_id,)
        ).fetchone()
        
        if not group:
            await message.answer("❌ Группа с таким ID не найдена")
            await state.clear()
            return
            
        # Получаем список пользователей для приглашения
        users = db.execute(
            "SELECT username FROM contacts WHERE group_id = ?",
            (group_id,)
        ).fetchall()
        
        if not users:
            await message.answer("❌ Нет пользователей для приглашения в эту группу")
            await state.clear()
            return
            
        await message.answer(f"🔄 Начинаю приглашение пользователей в группу @{group[0]}...")
        
        # Приглашаем пользователей
        await invite_users_to_group(message, group_id, users)
        
        await message.answer("✅ Приглашение пользователей завершено")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректный ID группы (число)")
    except Exception as e:
        print(f"Ошибка при обработке приглашения: {e}")
        await message.answer("❌ Произошла ошибка при обработке приглашения")
        await state.clear()

async def get_invite_status(group_id):
    try:
        db = Database()
        # Получаем количество приглашений за сегодня
        today = datetime.now().date()
        invites = db.execute("""
            SELECT COUNT(*) 
            FROM invites 
            WHERE group_id = ? 
            AND DATE(invite_date) = ?
        """, (group_id, today)).fetchone()[0]
        
        # Получаем количество отклоненных приглашений
        decline_date = datetime.now() - timedelta(days=DECLINE_WAIT_DAYS)
        declined = db.execute("""
            SELECT COUNT(*) 
            FROM invites 
            WHERE group_id = ? 
            AND status = 'declined' 
            AND invite_date > ?
        """, (group_id, decline_date)).fetchone()[0]
        
        return {
            'daily_invites': invites,
            'remaining_invites': DAILY_INVITE_LIMIT - invites,
            'declined_invites': declined
        }
    except Exception as e:
        print(f"Ошибка при получении статуса инвайтов: {e}")
        raise
