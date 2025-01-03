from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from database.db import Database
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, UserNotMutualContactError
import asyncio
from config import INVITE_DELAY

router = Router()

@router.message(F.text == "📨 Рассылка инвайтов")
async def start_invite_mailing(message: Message, state: FSMContext):
    try:
        db = Database("bot_database.db")
        cursor = db.execute("""
            SELECT 
                g.id,
                g.name,
                g.username,
                COUNT(DISTINCT c.username) as users_count
            FROM groups g
            LEFT JOIN contacts c ON g.id = c.group_id
            GROUP BY g.id
        """)
        groups = cursor.fetchall()
        
        if not groups:
            await message.answer("❌ В базе данных нет сохраненных групп")
            return
            
        builder = InlineKeyboardBuilder()
        for group in groups:
            users_count = group[3] or 0
            builder.button(
                text=f"📨 {group[1]} (@{group[2]}) | 👥 {users_count} пользователей",
                callback_data=f"invite_to_group_{group[0]}"
            )
        
        builder.adjust(1)
        
        await message.answer(
            "Выберите группу для рассылки инвайтов:",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        print(f"Ошибка при показе групп для рассылки: {e}")
        await message.answer("❌ Произошла ошибка при получении списка групп")

@router.callback_query(lambda c: c.data.startswith("invite_to_group_"))
async def handle_invite_to_group(callback: CallbackQuery, state: FSMContext, telethon_client=None):
    try:
        if not telethon_client:
            await callback.answer("❌ Ошибка: клиент Telethon не найден")
            return

        group_id = int(callback.data.split("_")[3])
        db = Database("bot_database.db")
        
        # Получаем информацию о группе
        cursor = db.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()
        if not group:
            await callback.answer("❌ Группа не найдена")
            return

        # Получаем список пользователей для приглашения
        cursor = db.execute("""
            SELECT c.username 
            FROM contacts c
            LEFT JOIN invites i ON c.username = i.username AND c.group_id = i.group_id
            WHERE c.group_id = ? AND (i.status IS NULL OR i.status = 'failed')
            LIMIT 50
        """, (group_id,))
        users = cursor.fetchall()

        if not users:
            await callback.message.edit_text("❌ Нет пользователей для приглашения")
            return

        status_message = await callback.message.edit_text(
            f"🔄 Начинаю рассылку инвайтов в группу {group[1]}...\n"
            f"👥 Всего пользователей для приглашения: {len(users)}"
        )

        success_count = 0
        error_count = 0
        
        try:
            group_entity = await telethon_client.get_entity(f"t.me/{group[2]}")
            
            for i, user in enumerate(users, 1):
                try:
                    user_entity = await telethon_client.get_entity(f"@{user[0]}")
                    await telethon_client(InviteToChannelRequest(group_entity, [user_entity]))
                    
                    # Записываем успешное приглашение
                    db.execute(
                        "INSERT OR REPLACE INTO invites (username, group_id, status) VALUES (?, ?, ?)",
                        (user[0], group_id, 'success')
                    )
                    db.commit()
                    
                    success_count += 1
                    
                except (UserPrivacyRestrictedError, UserNotMutualContactError):
                    # Пользователь запретил приглашения
                    db.execute(
                        "INSERT OR REPLACE INTO invites (username, group_id, status) VALUES (?, ?, ?)",
                        (user[0], group_id, 'failed')
                    )
                    db.commit()
                    error_count += 1
                    
                except FloodWaitError as e:
                    await status_message.edit_text(
                        f"⚠️ Достигнут лимит приглашений. Нужно подождать {e.seconds} секунд.\n\n"
                        f"✅ Успешно приглашено: {success_count}\n"
                        f"❌ Ошибок: {error_count}"
                    )
                    break
                    
                except Exception as e:
                    print(f"Ошибка при приглашении пользователя {user[0]}: {e}")
                    error_count += 1
                
                # Обновляем статус каждые 5 пользователей
                if i % 5 == 0:
                    await status_message.edit_text(
                        f"🔄 Рассылка инвайтов в группу {group[1]}...\n"
                        f"✅ Успешно приглашено: {success_count}\n"
                        f"❌ Ошибок: {error_count}\n"
                        f"📊 Прогресс: {i}/{len(users)}"
                    )
                
                await asyncio.sleep(INVITE_DELAY)  # Задержка между приглашениями
            
            # Финальное сообщение
            await status_message.edit_text(
                f"✅ Рассылка инвайтов завершена!\n\n"
                f"📊 Статистика:\n"
                f"👥 Всего обработано: {len(users)}\n"
                f"✅ Успешно приглашено: {success_count}\n"
                f"❌ Ошибок: {error_count}"
            )
            
        except Exception as e:
            await status_message.edit_text(
                f"❌ Ошибка при рассылке инвайтов:\n{str(e)}\n\n"
                f"📊 Статистика:\n"
                f"✅ Успешно приглашено: {success_count}\n"
                f"❌ Ошибок: {error_count}"
            )
            
    except Exception as e:
        print(f"Ошибка в обработчике рассылки: {e}")
        await callback.message.edit_text(f"❌ Произошла ошибка: {str(e)}") 