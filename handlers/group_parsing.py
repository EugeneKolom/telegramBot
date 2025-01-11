import asyncio
from aiogram import Router, F
from telethon.sync import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.states import BotStates
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
            continue

    print(f"Всего найдено уникальных групп: {len(results)}")
    return results

@router.message(F.text == "🔍 Поиск групп")
async def text_parse_groups(message: Message, state: FSMContext):
    await message.answer("Введите ключевые слова для поиска групп через запятую:")
    await state.set_state(BotStates.waiting_for_keywords)

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

@router.callback_query(lambda c: c.data.startswith("select_group_"))
async def toggle_group_selection(callback: CallbackQuery, state: FSMContext):
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
            builder.button(
                text=f"{checkbox} {group['title']} {username_part}",
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
        print(f"Ошибка при выборе группы: {e}")
        await callback.answer("❌ Ошибка при выборе группы")

@router.callback_query(lambda c: c.data == "select_all")
async def handle_select_all(callback: CallbackQuery, state: FSMContext):
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
            builder.button(
                text=f"✅ {group['title']} {username_part}",
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
        print(f"Ошибка при выборе всех групп: {e}")
        await callback.answer("❌ Ошибка при выборе всех групп")

@router.callback_query(lambda c: c.data == "deselect_all")
async def handle_deselect_all(callback: CallbackQuery, state: FSMContext):
    try:
        state_data = await state.get_data()
        found_groups = state_data.get("found_groups", [])
        
        # Очищаем выбор
        await state.update_data(selected_groups=[])
        
        # Обновляем клавиатуру
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
        
        await callback.message.edit_text(
            "📋 Выберите группы для сохранения:",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        print(f"Ошибка при снятии выбора: {e}")
        await callback.answer("❌ Ошибка при снятии выбора")