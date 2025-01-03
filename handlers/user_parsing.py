from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.states import BotStates
from database.db import Database
from aiogram.utils.keyboard import InlineKeyboardBuilder
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantsRequest, JoinChannelRequest, LeaveChannelRequest
from telethon.tl.types import (
    ChannelParticipantsSearch,
    ChannelParticipantsRecent,
    ChannelParticipantsBots,
    ChannelParticipantsAdmins
)
import asyncio

router = Router()

@router.message(F.text == "👥 Поиск пользователей")
async def start_parse_users(message: Message, state: FSMContext, telethon_client=None):
    try:
        if not telethon_client:
            await message.answer("❌ Ошибка: клиент Telethon не найден")
            return

        db = Database("bot_database.db")
        cursor = db.execute("SELECT * FROM groups")
        groups = cursor.fetchall()
        
        if not groups:
            await message.answer("❌ В базе данных нет сохраненных групп")
            return
            
        builder = InlineKeyboardBuilder()
        for group in groups:
            try:
                # Получаем информацию о группе
                group_entity = await telethon_client.get_entity(f"t.me/{group[2]}")
                full_chat = await telethon_client(GetFullChannelRequest(group_entity))
                participants_count = full_chat.full_chat.participants_count
                builder.button(
                    text=f"👥 {group[1]} (@{group[2]}) | {participants_count} подписчиков",
                    callback_data=f"parse_users_{group[0]}"
                )
            except Exception as e:
                builder.button(
                    text=f"👥 {group[1]} (@{group[2]}) | Ошибка",
                    callback_data=f"parse_users_{group[0]}"
                )
                print(f"Ошибка при получении информации о группе {group[2]}: {e}")

        builder.adjust(1)
        
        await message.answer(
            "Выберите группу для поиска пользователей:",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        print(f"Ошибка при показе групп для парсинга: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

@router.callback_query(lambda c: c.data.startswith("parse_users_"))
async def parse_users_callback(callback: CallbackQuery, telethon_client=None):
    try:
        if not telethon_client:
            await callback.answer("❌ Ошибка: клиент Telethon не найден")
            return

        group_id = int(callback.data.split("_")[2])
        db = Database("bot_database.db")
        
        # Получаем информацию о группе
        cursor = db.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()
        if not group:
            await callback.answer("❌ Группа не найдена")
            return

        await callback.message.edit_text(f"🔄 Начинаю парсинг пользователей группы {group[1]}...")
        
        try:
            # Получаем участников группы
            group_entity = await telethon_client.get_entity(f"t.me/{group[2]}")
            participants = await telethon_client.get_participants(group_entity)
            
            # Счетчики для статистики
            total_users = 0
            saved_users = 0
            
            for participant in participants:
                total_users += 1
                if participant.username:  # Сохраняем только пользователей с username
                    try:
                        db.execute(
                            "INSERT OR IGNORE INTO contacts (username, group_id) VALUES (?, ?)",
                            (participant.username, group_id)
                        )
                        saved_users += 1
                    except Exception as e:
                        print(f"Ошибка при сохранении пользователя {participant.username}: {e}")

            db.commit()
            
            if saved_users == 0:
                error_message = (
                    f"❌ Парсинг не удался!\n\n"
                    f"Причина: не удалось сохранить ни одного пользователя\n"
                    f"Всего найдено пользователей: {total_users}\n"
                    f"Возможные причины:\n"
                    f"- У пользователей нет username\n"
                    f"- Нет доступа к участникам группы\n"
                    f"- Группа закрыта или требует подписки"
                )
                await callback.message.edit_text(error_message)
            else:
                # Формируем сообщение о результатах
                success_message = (
                    f"✅ Парсинг успешно завершен!\n\n"
                    f"📊 Статистика:\n"
                    f"👥 Всего пользователей: {total_users}\n"
                    f"📥 Сохранено пользователей: {saved_users}\n"
                    f"💡 Пропущено пользователей без username: {total_users - saved_users}"
                )
                await callback.message.edit_text(success_message)
            
        except Exception as e:
            error_message = (
                f"❌ Парсинг не удался!\n\n"
                f"Причина: {str(e)}\n\n"
                f"Возможные решения:\n"
                f"- Проверьте доступ к группе\n"
                f"- Убедитесь, что группа публичная\n"
                f"- Попробуйте позже"
            )
            await callback.message.edit_text(error_message)
            print(f"Ошибка при парсинге группы {group[2]}: {e}")
            
    except Exception as e:
        print(f"Ошибка в обработчике парсинга: {e}")
        await callback.message.edit_text(
            f"❌ Произошла ошибка при парсинге пользователей\n\n"
            f"Причина: {str(e)}"
        )

async def parse_all_users(client, entity, status_message):
    """Парсинг всех пользователей группы"""
    all_participants = []
    
    # Различные фильтры для получения всех типов пользователей
    filters = [
        ChannelParticipantsSearch(''),  # Все пользователи
        ChannelParticipantsRecent(),    # Недавние пользователи
        ChannelParticipantsAdmins(),    # Администраторы
    ]
    
    for filter_type in filters:
        offset = 0
        limit = 200  # Увеличиваем лимит для ускорения парсинга
        
        while True:
            try:
                participants = await client(GetParticipantsRequest(
                    channel=entity,
                    filter=filter_type,
                    offset=offset,
                    limit=limit,
                    hash=0
                ))
                
                if not participants.users:
                    break
                
                # Добавляем только уникальных пользователей
                new_users = [user for user in participants.users 
                           if user.id not in [p.id for p in all_participants]]
                all_participants.extend(new_users)
                
                # Обновляем статус
                await status_message.edit_text(
                    f"🔄 Парсинг пользователей...\n"
                    f"Найдено: {len(all_participants)}\n"
                    f"Фильтр: {filter_type.__class__.__name__}"
                )
                
                offset += len(participants.users)
                await asyncio.sleep(1)  # Задержка для избежания ограничений
                
                if len(participants.users) < limit:
                    break
                    
            except Exception as e:
                print(f"Ошибка при парсинге с фильтром {filter_type.__class__.__name__}: {e}")
                continue
    
    return all_participants

@router.message(BotStates.waiting_for_group_name)
async def parse_users_handler(message: Message, state: FSMContext, client=None):
    try:
        input_text = message.text.strip()
        status_message = await message.answer("🔄 Начинаю парсинг...")
        
        try:
            # Получаем группу
            if input_text.isdigit():
                group_id = int(input_text)
                entity = await client.get_entity(group_id)
            else:
                group_username = input_text.lstrip("@")
                entity = await client.get_entity(group_username)
            
            # Сохраняем группу в базу
            db_group_id = await db.add_group(
                name=entity.title,
                username=entity.username if hasattr(entity, 'username') else None
            )
            
            # Парсим всех пользователей
            all_participants = await parse_all_users(client, entity, status_message)
            
            # Сохраняем пользователей в базу
            users_count = 0
            for user in all_participants:
                if user.bot:  # Пропускаем только ботов
                    continue
                    
                user_data = {
                    "id": user.id,
                    "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    "username": user.username or "No username",
                    "is_active": not user.deleted,  # Отмечаем удаленных пользователей
                    "is_bot": user.bot,
                    "is_admin": hasattr(user, 'admin_rights') and user.admin_rights is not None
                }
                
                if await db.add_user(db_group_id, user_data):
                    users_count += 1
                
                if users_count % 100 == 0:
                    await status_message.edit_text(
                        f"💾 Сохранение пользователей в базу...\n"
                        f"Обработано: {users_count}/{len(all_participants)}"
                    )
            
            # Получаем итоговую статистику
            stats = await db.get_group_stats(db_group_id)
            
            await status_message.edit_text(
                f"✅ Парсинг завершен\n\n"
                f"📊 Статистика:\n"
                f"👥 Всего найдено: {len(all_participants)}\n"
                f"✨ Новых добавлено: {users_count}\n"
                f"📝 Всего в базе: {stats['total']}\n\n"
                f"ℹ️ Информация о группе:\n"
                f"📌 Название: {entity.title}\n"
                f"🔗 Username: {f'@{entity.username}' if entity.username else 'Отсутствует'}\n"
                f"🆔 ID: {entity.id}"
            )
            
        except ValueError as e:
            await status_message.edit_text(
                f"❌ Ошибка формата: {str(e)}\n\n"
                "Введите:\n"
                "1. ID группы (например: 1234567890)\n"
                "2. Или username группы (например: @group или group)"
            )
        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка при парсинге: {str(e)}")
            
    except Exception as e:
        await message.answer(f"❌ Общая ошибка: {str(e)}")
    finally:
        await state.clear()
