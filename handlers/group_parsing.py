import asyncio
import logging
from aiogram import Router, F
from telethon.sync import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.states import BotStates
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import Database
from aiogram.exceptions import TelegramBadRequest

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

async def is_comments_enabled(client: TelegramClient, chat) -> bool:
    """Проверка, разрешены ли комментарии в канале."""
    try:
        full_chat = await client(GetFullChannelRequest(chat))
        is_enabled = full_chat.full_chat.comments_enabled
        logger.debug(f"Комментарии в канале {chat.title} ({chat.id}) {'включены' if is_enabled else 'выключены'}")
        return is_enabled
    except Exception as e:
        logger.error(f"Ошибка при проверке комментариев в канале {chat}: {e}", exc_info=True)
        return False

async def has_user_messages(client: TelegramClient, chat) -> bool:
    """Проверка, есть ли сообщения от пользователей."""
    try:
        user_messages = False
        async for message in client.iter_messages(chat, limit=10):
            if message.sender and not message.sender.bot:
                user_messages = True
                break  # Прекращаем после первого сообщения пользователя
        logger.debug(f"Наличие сообщений от пользователей в канале {chat.title} ({chat.id}): {'есть' if user_messages else 'нет'}")
        return user_messages
    except Exception as e:
        logger.error(f"Ошибка при проверке сообщений в канале {chat}: {e}", exc_info=True)
        return False

async def global_search(client: TelegramClient, keywords: list[str]) -> list[dict]:
    """Поиск групп через поиск Telegram с фильтрацией."""
    results = []
    unique_groups = set()  # Для хранения уникальных групп
    total_keywords = len(keywords)
    logger.info(f"Начинается глобальный поиск по {total_keywords} ключевым словам.")

    for i, keyword in enumerate(keywords):
        logger.info(f"[{i+1}/{total_keywords}] 🔍 Поиск по ключевому слову: {keyword}")
        try:
            search_result = await client(SearchRequest(
                q=keyword,
                limit=100
            ))

            chats = search_result.chats if hasattr(search_result, 'chats') else []
            num_chats = len(chats)
            logger.info(f"[{i+1}/{total_keywords}] Получен результат поиска для '{keyword}'. Найдено {num_chats} чатов.")

            for j, chat in enumerate(chats):
                if hasattr(chat, 'username') and chat.username:
                    logger.debug(f"[{i+1}/{total_keywords}] [{j+1}/{num_chats}] Обработка чата: {chat.title} (@{chat.username})")

                    comments_enabled = await is_comments_enabled(client, chat)
                    has_messages = await has_user_messages(client, chat)

                    if comments_enabled or has_messages:
                        group_data = (chat.id, chat.title, chat.username)  # Используем кортеж для уникальности
                        if group_data not in unique_groups:
                            unique_groups.add(group_data)
                            group_info = {
                                "id": chat.id,
                                "title": chat.title,
                                "username": chat.username,
                                "comments_enabled": comments_enabled,
                                "has_user_messages": has_messages
                            }
                            results.append(group_info)
                            logger.info(f"[{i+1}/{total_keywords}] [{j+1}/{num_chats}]  ✅ Найдена и добавлена группа: {chat.title} (@{chat.username}), ID: {chat.id}")
                        else:
                             logger.debug(f"[{i+1}/{total_keywords}] [{j+1}/{num_chats}] Группа {chat.title} (@{chat.username}), ID: {chat.id} уже существует в unique_groups, пропущена.")
                    else:
                        logger.debug(f"[{i+1}/{total_keywords}] [{j+1}/{num_chats}] Группа {chat.title} (@{chat.username}), ID: {chat.id} пропущена, т.к. комментарии отключены и нет сообщений от пользователей.")
                else:
                     logger.warning(f"[{i+1}/{total_keywords}] [{j+1}/{num_chats}] Чат {chat.title} ({chat.id}) пропущен, нет username.")

        except Exception as e:
            logger.error(f"[{i+1}/{total_keywords}] ❌ Ошибка при поиске по '{keyword}': {str(e)}", exc_info=True)

    total_found = len(results)
    logger.info(f"Глобальный поиск завершен. Всего найдено уникальных групп: {total_found}")
    return results


# --- Обработчики Aiogram ---

@router.message(F.text == " Поиск групп")
async def text_parse_groups(message: Message, state: FSMContext):
    """Обработчик команды 'Поиск групп'."""
    await message.answer("Введите ключевые слова для поиска групп через запятую:")
    await state.set_state(BotStates.waiting_for_keywords)


@router.message(BotStates.waiting_for_keywords)
async def search_groups_handler(message: Message, state: FSMContext, telethon_client: TelegramClient = None):
    """Обработчик для поиска групп по ключевым словам."""
    try:
        if not telethon_client:
            await message.answer(" Ошибка: клиент Telethon не найден")
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
            comments_info = "💬" if group['comments_enabled'] else ""
            messages_info = "📨" if group['has_user_messages'] else ""
            builder.button(
                text=f"⬜️ {group['title']} {username_part} {comments_info} {messages_info}",
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
        logger.error(f"❌ Ошибка при поиске групп: {e}", exc_info=True)
        await message.answer(f"❌ Произошла ошибка при поиске: {str(e)}")
        await state.clear()


@router.callback_query(lambda c: c.data.startswith("select_group_"))
async def toggle_group_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик для переключения выбора группы."""
    try:
        index = int(callback.data.split("_")[2])
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
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            comments_info = "💬" if group['comments_enabled'] else ""
            messages_info = "📨" if group['has_user_messages'] else ""
            builder.button(
                text=f"{checkbox} {group['title']} {username_part} {comments_info} {messages_info}",
                callback_data=f"select_group_{i}"
            )

        builder.button(text="✅ Выбрать все", callback_data="select_all")
        builder.button(text="❌ Снять выбор", callback_data="deselect_all")
        builder.button(text="💾 Сохранить выбранные", callback_data="save_selected")

        builder.adjust(1)

        await callback.message.edit_text(
            "📋 Выберите группы для сохранения:",
            reply_markup=builder.as_markup()
        )

    except TelegramBadRequest as e:
        if "query is too old" in str(e):
            logger.warning(f"Игнорируем устаревший callback запрос: {e}")
            await callback.answer("Эта кнопка устарела. Пожалуйста, выполните команду заново.") #Опционально
        else:
            logger.error(f"Ошибка при выборе группы: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при выборе группы")


@router.callback_query(lambda c: c.data == "select_all")
async def handle_select_all(callback: CallbackQuery, state: FSMContext):
    """Обработчик для выбора всех групп."""
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])

        # Выбираем все группы
        selected_groups = list(range(len(found_groups)))
        await state.update_data(selected_groups=selected_groups)

        # Обновляем клавиатуру
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            comments_info = "💬" if group['comments_enabled'] else ""
            messages_info = "📨" if group['has_user_messages'] else ""
            builder.button(
                text=f"✅ {group['title']} {username_part} {comments_info} {messages_info}",
                callback_data=f"select_group_{i}"
            )

        builder.button(text="✅ Выбрать все", callback_data="select_all")
        builder.button(text="❌ Снять выбор", callback_data="deselect_all")
        builder.button(text="💾 Сохранить выбранные", callback_data="save_selected")

        builder.adjust(1)

        await callback.message.edit_text(
            "📋 Выберите группы для сохранения:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка при выборе всех групп: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при выборе всех групп")


@router.callback_query(lambda c: c.data == "deselect_all")
async def handle_deselect_all(callback: CallbackQuery, state: FSMContext):
    """Обработчик для снятия выбора со всех групп."""
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])

        # Очищаем выбор
        await state.update_data(selected_groups=[])

        # Обновляем клавиатуру
        builder = InlineKeyboardBuilder()
        for i, group in enumerate(found_groups):
            username_part = f"(@{group['username']})" if group['username'] else "(без username)"
            comments_info = "💬" if group['comments_enabled'] else ""
            messages_info = "📨" if group['has_user_messages'] else ""
            builder.button(
                text=f"⬜️ {group['title']} {username_part} {comments_info} {messages_info}",
                callback_data=f"select_group_{i}"
            )

        builder.button(text="✅ Выбрать все", callback_data="select_all")
        builder.button(text="❌ Снять выбор", callback_data="deselect_all")
        builder.button(text="💾 Сохранить выбранные", callback_data="save_selected")

        builder.adjust(1)

        await callback.message.edit_text(
            "📋 Выберите группы для сохранения:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка при снятии выбора: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при снятии выбора")


@router.callback_query(lambda c: c.data == "save_selected")
async def save_selected_groups(callback: CallbackQuery, state: FSMContext):
    """Обработчик для сохранения выбранных групп."""
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        selected_indices = state_data.get("selected_groups", [])

        if not selected_indices:
            await callback.answer("❌ Не выбрано ни одной группы")
            return

        selected_groups = [found_groups[i] for i in selected_indices]
        logger.info(f"Сохранение групп: {selected_groups}")

        # Сохраняем группы в базу данных
        db = Database("bot_database.db") #  Получите путь к БД из конфига, а не хардкодом
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
                logger.error(f"Ошибка при сохранении группы {group['title']}: {e}", exc_info=True)
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
        logger.error(f"Ошибка при сохранении групп: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при сохранении групп")
        await state.clear()