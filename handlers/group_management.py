from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.states import BotStates
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import Database
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest

router = Router()

@router.callback_query(lambda c: c.data == "save_selected")
async def save_selected_groups(callback: CallbackQuery, state: FSMContext):
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        selected_indices = state_data.get("selected_groups", [])
        
        if not selected_indices:
            await callback.answer("❌ Не выбрано ни одной группы")
            return
            
        selected_groups = [found_groups[i] for i in selected_indices]
        print(f"Сохранение групп: {selected_groups}")
        
        # Сохраняем группы в базу данных
        db = Database("bot_database.db")
        saved_count = 0
        already_exists = 0
        
        for group in selected_groups:
            try:
                # Проверяем, существует ли группа уже в базе
                cursor = db.execute("SELECT id FROM groups WHERE username = ?", (group['username'],))
                existing_group = cursor.fetchone()
                
                if existing_group:
                    already_exists += 1
                    continue
                
                # Сохраняем новую группу
                db.execute(
                    "INSERT INTO groups (id, name, username) VALUES (?, ?, ?)",
                    (group['id'], group['title'], group['username'])
                )
                saved_count += 1
                
            except Exception as e:
                print(f"Ошибка при сохранении группы {group['title']}: {e}")
                continue
        
        db.commit()
        
        # Формируем сообщение о результатах
        result_message = (
            f"✅ Результаты сохранения:\n\n"
            f"📥 Сохранено новых групп: {saved_count}\n"
            f"📝 Уже существующих: {already_exists}\n"
            f"📊 Всего выбрано: {len(selected_indices)}"
        )
        
        await callback.message.edit_text(result_message)
        await state.clear()
        
    except Exception as e:
        print(f"Ошибка при сохранении групп: {e}")
        await callback.answer("❌ Ошибка при сохранении групп")
        await state.clear()

@router.message(F.text == "📋 Просмотреть группы")
async def view_groups(message: Message, telethon_client=None):
    print("Обработчик view_groups вызван")
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
                print(f"Ошибка при получении информации о группе {group[2]}: {e}")
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
        print(f"Ошибка при показе списка групп: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

@router.message(F.text == "❌ Удалить группу")
async def delete_group_start(message: Message, state: FSMContext, telethon_client=None):
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
                # Получаем полную информацию о группе через Telethon
                group_entity = await telethon_client.get_entity(f"t.me/{group[2]}")
                full_chat = await telethon_client(GetFullChannelRequest(group_entity))
                participants_count = full_chat.full_chat.participants_count
                builder.button(
                    text=f"❌ {group[1]} (@{group[2]}) | ID: {group[0]} | 👥 {participants_count}",
                    callback_data=f"delete_group_{group[0]}"
                )
            except Exception as e:
                builder.button(
                    text=f"❌ {group[1]} (@{group[2]}) | ID: {group[0]} | ❌ Ошибка",
                    callback_data=f"delete_group_{group[0]}"
                )
                print(f"Ошибка при получении информации о группе {group[2]}: {e}")

        builder.adjust(1)
        
        await message.answer(
            "Выберите группу для удаления:",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        print(f"Ошибка при показе групп для удаления: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

@router.callback_query(lambda c: c.data.startswith("delete_group_"))
async def delete_group_callback(callback: CallbackQuery):
    try:
        group_id = int(callback.data.split("_")[2])
        
        # Подключение к базе данных
        db = Database("bot_database.db")
        
        # Удаляем группу
        db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        db.commit()
        
        await callback.answer("✅ Группа успешно удалена")
        await callback.message.edit_text("Группа удалена из базы данных")
        
    except Exception as e:
        print(f"Ошибка при удалении группы: {e}")
        await callback.answer("❌ Ошибка при удалении группы")

@router.message(F.text == "➕ Добавить группу вручную")
async def add_group_manually(message: Message, state: FSMContext):
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