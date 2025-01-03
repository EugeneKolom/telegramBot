import asyncio
from aiogram import Router, F
from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerEmpty, Chat, Channel
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.functions.contacts import SearchRequest
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.states import BotStates
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import Database
from telethon.tl.functions.channels import GetFullChannelRequest

router = Router()

async def global_search(client: TelegramClient, keywords: list[str]):
    """Поиск групп через поиск Telegram"""
    results = []
    for keyword in keywords:
        print(f"🔍 Поиск по ключевому слову: {keyword}")
        try:
            search_result = await client(SearchRequest(
                q=keyword,
                limit=100
            ))
            
            print(f"Получен результат поиска для '{keyword}'")
            
            if hasattr(search_result, 'chats'):
                print(f"Найдено чатов: {len(search_result.chats)}")
                for chat in search_result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        group_data = {
                            "id": chat.id,
                            "title": chat.title,
                            "username": chat.username
                        }
                        if group_data not in results:
                            results.append(group_data)
                            print(f"Найдена группа: {group_data['title']} (@{group_data['username']})")

            await asyncio.sleep(2)

        except Exception as e:
            print(f"❌ Ошибка при поиске: {str(e)}")
            print(f"Тип ошибки: {type(e)}")
            continue

    print(f"Всего найдено уникальных групп: {len(results)}")
    return results

@router.message(BotStates.waiting_for_keywords)
async def search_groups_handler(message: Message, state: FSMContext, telethon_client=None):
    try:
        if not telethon_client:
            await message.answer("❌ Ошибка: клиент Telethon не найден")
            return

        keywords = [k.strip() for k in message.text.split(',')]
        await message.answer(f"🔍 Начинаю поиск групп по ключевым словам: {keywords}")

        groups = await global_search(telethon_client, keywords)

        if not groups:
            await message.answer("❌ Группы не найдены")
            await state.clear()
            return

        await state.update_data(found_groups=groups)
        
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(groups):
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            builder.button(
                text=f"⬜️ {group['title']} {username_part}",
                callback_data=f"select_group_{i}"
            )
        
        builder.button(text="✅ Выбрать все", callback_data="select_all")
        builder.button(text="❌ Снять выбор", callback_data="deselect_all")
        builder.button(text="💾 Сохранить выбранные", callback_data="save_selected")
        
        builder.adjust(1)
        
        await message.answer(
            "📋 Выберите группы для сохранения:",
            reply_markup=builder.as_markup()
        )
        
        await state.set_state(BotStates.selecting_groups)
        await state.update_data(selected_groups=[])

    except Exception as e:
        print(f"❌ Ошибка при поиске групп: {e}")
        await message.answer(f"❌ Произошла ошибка при поиске: {str(e)}")
        await state.clear()

@router.message(F.text == "🔍 Парсить группы")
async def text_parse_groups(message: Message, state: FSMContext):
    await message.answer("Введите ключевые слова для поиска групп через запятую:")
    await state.set_state(BotStates.waiting_for_keywords)

@router.callback_query(lambda c: c.data.startswith("select_group_"))
async def toggle_group_selection(callback: CallbackQuery, state: FSMContext):
    try:
        group_index = int(callback.data.split("_")[2])
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        selected_groups = state_data.get("selected_groups", [])

        if group_index < len(found_groups):
            group = found_groups[group_index]
            if group_index in selected_groups:
                selected_groups.remove(group_index)
                checkbox = "⬜️"
            else:
                selected_groups.append(group_index)
                checkbox = "✅"

            await state.update_data(selected_groups=selected_groups)

            # Обновляем текст кнопки
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            builder = InlineKeyboardBuilder()
            
            # Воссоздаем все кнопки
            for i, g in enumerate(found_groups):
                is_selected = i in selected_groups
                u_part = f"(@{g['username']})" if g['username'] else "(без username)"
                builder.button(
                    text=f"{'✅' if is_selected else '⬜️'} {g['title']} {u_part}",
                    callback_data=f"select_group_{i}"
                )

            builder.button(text="✅ Выбрать все", callback_data="select_all")
            builder.button(text="❌ Снять выбор", callback_data="deselect_all")
            builder.button(text="💾 Сохранить выбранные", callback_data="save_selected")
            
            builder.adjust(1)

            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
            await callback.answer()

    except Exception as e:
        print(f"Ошибка при обработке выбора группы: {e}")
        await callback.answer("Произошла ошибка при выборе группы")

@router.callback_query(lambda c: c.data == "select_all")
async def handle_select_all(callback: CallbackQuery, state: FSMContext):
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        selected_groups = list(range(len(found_groups)))
        await state.update_data(selected_groups=selected_groups)

        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            builder.button(
                text=f"✅ {group['title']} {username_part}",
                callback_data=f"select_group_{i}"
            )

        builder.button(text="✅ Выбрать все", callback_data="select_all")
        builder.button(text="❌ Снять выбор", callback_data="deselect_all")
        builder.button(text="💾 Сохранить выбранные", callback_data="save_selected")
        
        builder.adjust(1)

        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        await callback.answer("Выбраны все группы")

    except Exception as e:
        print(f"Ошибка при выборе всех групп: {e}")
        await callback.answer("Произошла ошибка при выборе всех групп")

@router.callback_query(lambda c: c.data == "deselect_all")
async def handle_deselect_all(callback: CallbackQuery, state: FSMContext):
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        await state.update_data(selected_groups=[])

        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            builder.button(
                text=f"⬜️ {group['title']} {username_part}",
                callback_data=f"select_group_{i}"
            )

        builder.button(text="✅ Выбрать все", callback_data="select_all")
        builder.button(text="❌ Снять выбор", callback_data="deselect_all")
        builder.button(text="💾 Сохранить выбранные", callback_data="save_selected")
        
        builder.adjust(1)

        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        await callback.answer("Выбор всех групп снят")

    except Exception as e:
        print(f"Ошибка при снятии выбора всех групп: {e}")
        await callback.answer("Произошла ошибка при снятии выбора")

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
        for group in selected_groups:
            try:
                db.execute(
                    "INSERT OR IGNORE INTO groups (id, name, username) VALUES (?, ?, ?)",
                    (group['id'], group['title'], group['username'])
                )
                db.commit()
            except Exception as e:
                print(f"Ошибка при сохранении группы {group['title']}: {e}")
        
        await callback.answer("✅ Выбранные группы сохранены")
        await callback.message.answer(f"Сохранено {len(selected_groups)} групп")
        await state.clear()
        
    except Exception as e:
        print(f"Ошибка при сохранении групп: {e}")
        await callback.answer("❌ Ошибка при сохранении групп")

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
