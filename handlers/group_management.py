import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from database.db import Database
from states.states import BotStates

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = Router()

@router.message(F.text == "📋 Просмотреть группы")
async def view_groups(message: Message, telethon_client: TelegramClient):
    """Показать список групп с количеством пользователей и статистикой приглашений."""
    try:
        if not telethon_client or not await telethon_client.is_user_authorized():
            logger.error("Telethon client not found or not authorized")
            await message.answer("❌ Ошибка: клиент Telethon не найден или не авторизован")
            return

        db = Database("bot_database.db")
        cursor = db.execute("""
            SELECT 
                g.id,
                g.name,
                g.username,
                (SELECT COUNT(*) FROM contacts WHERE group_id = g.id) as parsed_users,
                (SELECT COUNT(*) FROM invites WHERE group_id = g.id AND status = 'success') as invited_users
            FROM groups g
        """)
        groups = cursor.fetchall()
        
        if not groups:
            logger.warning("No groups stored in the database")
            await message.answer("❌ В базе данных нет сохраненных групп")
            return
            
        groups_text = []
        
        for group in groups:
            parsed_users = group[3] or 0
            invited_users = group[4] or 0
            try:
                group_entity = await telethon_client.get_entity(f"t.me/{group[2]}")
                full_chat = await telethon_client(GetFullChannelRequest(group_entity))
                participants_count = full_chat.full_chat.participants_count
                
                groups_text.append(
                    f"📱 {group[1]} (@{group[2]})\n"
                    f"👥 ID: {group[0]}\n"
                    f"👥 Подписчиков: {participants_count}\n"
                    f"📥 Спарсено пользователей: {parsed_users}\n"
                    f"📨 Успешно приглашено: {invited_users}"
                )
            except Exception as e:
                logger.error(f"Error retrieving group info for {group[2]}: {e}")
                groups_text.append(
                    f"📱 {group[1]} (@{group[2]})\n"
                    f"👥 ID: {group[0]}\n"
                    f"👥 Подписчиков: Нет данных\n"
                    f"📥 Спарсено пользователей: {parsed_users}\n"
                    f"📨 Успешно приглашено: {invited_users}"
                )

        await message.answer(
            "📋 Список сохраненных групп:\n\n" + "\n\n".join(groups_text)
        )
        
    except Exception as e:
        logger.error(f"Error showing group list: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

@router.message(F.text == "❌ Удалить группу")
async def delete_group_start(message: Message, state: FSMContext, telethon_client: TelegramClient):
    """Начать процесс удаления групп с чекбоксами."""
    try:
        if not telethon_client:
            logger.error("Telethon client not found")
            await message.answer("❌ Ошибка: клиент Telethon не найден")
            return

        db = Database("bot_database.db")
        groups = db.execute("SELECT * FROM groups").fetchall()
        
        if not groups:
            logger.warning("No groups stored in the database for deletion")
            await message.answer("❌ В базе данных нет сохраненных групп")
            return
        
        # Преобразуем группы в список словарей для совместимости с логикой выбора
        formatted_groups = [{
            "id": group[0],
            "title": group[1],
            "username": group[2]
        } for group in groups]
            
        await state.update_data(found_groups=formatted_groups)
        
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(formatted_groups):
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            builder.button(
                text=f"⬜️ {group['title']} {username_part}",
                callback_data=f"delete_group_select_{i}"
            )
        
        builder.button(text="✅ Выбрать все", callback_data="delete_group_select_all")
        builder.button(text="❌ Снять выбор", callback_data="delete_group_deselect_all")
        builder.button(text="🗑️ Подтвердить удаление", callback_data="delete_group_confirm")
        
        builder.adjust(1)
        
        await message.answer(
            "📋 Выберите группы для удаления:",
            reply_markup=builder.as_markup()
        )
        
        await state.set_state(BotStates.deleting_groups)
        await state.update_data(selected_groups=[])
        
    except Exception as e:
        logger.error(f"Error showing groups for deletion: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

@router.callback_query(lambda c: c.data.startswith("delete_group_select_") or c.data in ["delete_group_select_all", "delete_group_deselect_all"])
async def toggle_group_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора групп для удаления."""
    try:
        callback_data = callback.data
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        selected_groups = state_data.get("selected_groups", [])

        if callback_data == "delete_group_select_all":
            # Выбираем все группы
            selected_groups = list(range(len(found_groups)))
            await callback.answer("Все группы выбраны")
        elif callback_data == "delete_group_deselect_all":
            # Снимаем выбор со всех групп
            selected_groups = []
            await callback.answer("Выбор снят")
        else:
            # Обрабатываем выбор конкретной группы
            index = int(callback_data.split("_")[3])
            if index in selected_groups:
                selected_groups.remove(index)
            else:
                selected_groups.append(index)

        # Обновляем состояние
        await state.update_data(selected_groups=selected_groups)

        # Обновляем клавиатуру
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            checkbox = "✅" if i in selected_groups else "⬜️"
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            builder.button(
                text=f"{checkbox} {group['title']} {username_part}",
                callback_data=f"delete_group_select_{i}"
            )

        # Добавляем кнопки управления
        builder.button(text="✅ Выбрать все", callback_data="delete_group_select_all")
        builder.button(text="❌ Снять выбор", callback_data="delete_group_deselect_all")
        builder.button(text="🗑️ Подтвердить удаление", callback_data="delete_group_confirm")

        builder.adjust(1)

        # Редактируем сообщение с обновленной клавиатурой
        await callback.message.edit_text(
            "📋 Выберите группы для удаления:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка при выборе группы: {e}")
        await callback.answer("❌ Ошибка при выборе группы")

@router.callback_query(lambda c: c.data == "delete_group_confirm")
async def handle_confirm_deletion(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и выполнение удаления выбранных групп."""
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        selected_groups = state_data.get("selected_groups", [])
        
        if not selected_groups:
            await callback.answer("❌ Не выбрано ни одной группы")
            return
        
        db = Database("bot_database.db")
        deleted_count = 0
        
        for index in selected_groups:
            group = found_groups[index]
            db.execute("DELETE FROM groups WHERE id = ?", (group['id'],))
            deleted_count += 1
        
        db.commit()
        
        await callback.message.edit_text(
            f"✅ Удалено групп: {deleted_count}\n\n"
            f"🗑️ Выбранные группы были успешно удалены."
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error deleting groups: {e}")
        await callback.answer("❌ Ошибка при удалении групп")

@router.message(F.text == "➕ Добавить группу вручную")
async def add_group_manually(message: Message, state: FSMContext):
    """Добавить группу вручную."""
    example_message = (
        "Введите ссылку на группу в одном из форматов:\n\n"
        "✅ Правильные форматы:\n"
        "• https://t.me/group_name\n"
        "• t.me/group_name\n"
        "• @group_name\n"
        "• group_name\n\n"
        "❌ Неправильные форматы:\n"
        "• https://t.me/+AbCdEf123456\n"
        "• https://t.me/joinchat/AbCdEf123456\n"
        "• +AbCdEf123456\n\n"
        "⚠️ Группа должна быть публичной и иметь username"
    )
    await message.answer(example_message)
    await state.set_state(BotStates.waiting_for_group_name)

@router.message(BotStates.waiting_for_group_name)
async def process_group_name(message: Message, state: FSMContext, telethon_client: TelegramClient):
    """Обработка введенного username группы для ручного добавления."""
    try:
        if not telethon_client:
            logger.error("Telethon client not found")
            await message.answer("❌ Ошибка: клиент Telethon не найден")
            return

        group_username = message.text.strip()
        if 't.me/' in group_username:
            group_username = group_username.split('t.me/')[-1]
        elif '@' in group_username:
            group_username = group_username.lstrip('@')
            
        try:
            group_entity = await telethon_client.get_entity(f"t.me/{group_username}")
            
            db = Database("bot_database.db")
            db.execute(
                "INSERT OR IGNORE INTO groups (id, name, username) VALUES (?, ?, ?)",
                (group_entity.id, group_entity.title, group_username)
            )
            db.commit()
            
            await message.answer(
                f"✅ Группа успешно добавлена!\n\n"
                f"📱 Название: {group_entity.title}\n"
                f"🔗 Username: @{group_username}\n"
                f"🆔 ID: {group_entity.id}"
            )
            
        except Exception as e:
            logger.error(f"Error adding group manually: {e}")
            await message.answer(
                f"❌ Ошибка при добавлении группы:\n"
                f"{str(e)}\n\n"
                f"Убедитесь, что:\n"
                f"• Группа существует\n"
                f"• Группа публичная\n"
                f"• Указан правильный username"
            )
            
    except Exception as e:
        logger.error(f"Error processing group username: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
    finally:
        await state.clear()