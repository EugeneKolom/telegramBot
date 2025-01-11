from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import Database
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from states.states import BotStates
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

# Просмотр групп
@router.message(F.text == "📋 Просмотреть группы")
async def view_groups(message: Message, telethon_client=None):
    """Показывает список групп с информацией о количестве пользователей и приглашений"""
    try:
        if not telethon_client:
            await message.answer("❌ Ошибка: клиент Telethon не найден")
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
            await message.answer("❌ В базе данных нет сохраненных групп")
            return
            
        groups_text = []
        
        for group in groups:
            parsed_users = group[3] if group[3] is not None else 0
            invited_users = group[4] if group[4] is not None else 0
            try:
                # Получаем количество подписчиков через Telethon
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
                logger.error(f"Ошибка при получении информации о группе {group[2]}: {e}")
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
        logger.error(f"Ошибка при показе списка групп: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

# Удаление групп с галочками
@router.message(F.text == "❌ Удалить группу")
async def delete_group_start(message: Message, state: FSMContext, telethon_client=None):
    """Начало процесса удаления групп с выбором через галочки"""
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
            
        # Сохраняем список групп в состояние
        await state.update_data(found_groups=groups)
        
        # Создаем клавиатуру с галочками
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(groups):
            username_part = f"(@{group[2]})" if group[2] else "(без username)"
            builder.button(
                text=f"⬜️ {group[1]} {username_part}",
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
        
        # Устанавливаем состояние выбора групп для удаления
        await state.set_state(BotStates.deleting_groups)
        await state.update_data(selected_groups=[])
        
    except Exception as e:
        logger.error(f"Ошибка при показе групп для удаления: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

@router.callback_query(lambda c: c.data.startswith("delete_group_select_"))
async def toggle_group_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора/снятия выбора группы"""
    try:
        index = int(callback.data.split("_")[3])
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        selected_groups = state_data.get("selected_groups", [])
        
        if index in selected_groups:
            selected_groups.remove(index)
        else:
            selected_groups.append(index)
            
        await state.update_data(selected_groups=selected_groups)
        
        # Обновляем клавиатуру
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            checkbox = "✅" if i in selected_groups else "⬜️"
            username_part = f"(@{group[2]})" if group[2] else "(без username)"
            builder.button(
                text=f"{checkbox} {group[1]} {username_part}",
                callback_data=f"delete_group_select_{i}"
            )
        
        builder.button(text="✅ Выбрать все", callback_data="delete_group_select_all")
        builder.button(text="❌ Снять выбор", callback_data="delete_group_deselect_all")
        builder.button(text="🗑️ Подтвердить удаление", callback_data="delete_group_confirm")
        
        builder.adjust(1)
        
        await callback.message.edit_text(
            "📋 Выберите группы для удаления:",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при выборе группы: {e}")
        await callback.answer("❌ Ошибка при выборе группы")

@router.callback_query(lambda c: c.data == "delete_group_select_all")
async def handle_select_all(callback: CallbackQuery, state: FSMContext):
    """Выбор всех групп"""
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        
        # Выбираем все группы
        selected_groups = list(range(len(found_groups)))
        await state.update_data(selected_groups=selected_groups)
        
        # Обновляем клавиатуру
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            checkbox = "✅" if i in selected_groups else "⬜️"
            username_part = f"(@{group[2]})" if group[2] else "(без username)"
            builder.button(
                text=f"{checkbox} {group[1]} {username_part}",
                callback_data=f"delete_group_select_{i}"
            )
        
        builder.button(text="✅ Выбрать все", callback_data="delete_group_select_all")
        builder.button(text="❌ Снять выбор", callback_data="delete_group_deselect_all")
        builder.button(text="🗑️ Подтвердить удаление", callback_data="delete_group_confirm")
        
        builder.adjust(1)
        
        await callback.message.edit_text(
            "📋 Выберите группы для удаления:",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при выборе всех групп: {e}")
        await callback.answer("❌ Ошибка при выборе всех групп")

@router.callback_query(lambda c: c.data == "delete_group_deselect_all")
async def handle_deselect_all(callback: CallbackQuery, state: FSMContext):
    """Снятие выбора всех групп"""
    try:
        # Очищаем выбор
        await state.update_data(selected_groups=[])
        
        # Получаем обновленные данные состояния
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        
        if not found_groups:
            await callback.answer("❌ Нет групп для выбора")
            return
        
        # Создаем новую клавиатуру с пустыми галочками
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            checkbox = "⬜️"  # Все галочки сняты
            username_part = f"(@{group[2]})" if group[2] else "(без username)"
            builder.button(
                text=f"{checkbox} {group[1]} {username_part}",
                callback_data=f"delete_group_select_{i}"
            )
        
        # Добавляем кнопки управления
        builder.button(text="✅ Выбрать все", callback_data="delete_group_select_all")
        builder.button(text="❌ Снять выбор", callback_data="delete_group_deselect_all")
        builder.button(text="🗑️ Подтвердить удаление", callback_data="delete_group_confirm")
        
        builder.adjust(1)
        
        # Обновляем сообщение с новой клавиатурой
        await callback.message.edit_text(
            "📋 Выберите группы для удаления:",
            reply_markup=builder.as_markup()
        )
        
        # Уведомляем пользователя
        await callback.answer("Выбор снят")
        
    except Exception as e:
        logger.error(f"Ошибка при снятии выбора: {e}")
        await callback.answer("❌ Ошибка при снятии выбора")

@router.callback_query(lambda c: c.data == "delete_group_confirm")
async def handle_confirm_deletion(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления выбранных групп"""
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
            db.execute("DELETE FROM groups WHERE id = ?", (group[0],))
            deleted_count += 1
        
        db.commit()
        
        await callback.message.edit_text(
            f"✅ Удалено групп: {deleted_count}\n\n"
            f"🗑️ Выбранные группы были успешно удалены."
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при удалении групп: {e}")
        await callback.answer("❌ Ошибка при удалении групп")

# Добавление группы вручную
@router.message(F.text == "➕ Добавить группу вручную")
async def add_group_manually(message: Message, state: FSMContext):
    """Добавление группы вручную"""
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
async def process_group_name(message: Message, state: FSMContext, telethon_client=None):
    """Обработка ввода username группы"""
    try:
        if not telethon_client:
            await message.answer("❌ Ошибка: клиент Telethon не найден")
            return

        group_username = message.text.strip()
        
        # Очищаем ссылку от лишнего
        if 't.me/' in group_username:
            group_username = group_username.split('t.me/')[-1]
        elif '@' in group_username:
            group_username = group_username.lstrip('@')
            
        try:
            # Пробуем получить информацию о группе
            group_entity = await telethon_client.get_entity(f"t.me/{group_username}")
            
            # Сохраняем группу в базу
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
            await message.answer(
                f"❌ Ошибка при добавлении группы:\n"
                f"{str(e)}\n\n"
                f"Убедитесь, что:\n"
                f"• Группа существует\n"
                f"• Группа публичная\n"
                f"• Указан правильный username"
            )
            
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
    finally:
        await state.clear()