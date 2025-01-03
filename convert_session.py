from telethon.sessions import StringSession
from telethon.sync import TelegramClient

# Замените эти значения на свои
api_id='24882971'
api_hash='75367c26a50045102aab7b012d79b06a'

# Убедитесь, что имя сессии соответствует вашему файлу сессии
with TelegramClient('bot_session', api_id, api_hash) as client:
    client.start()  # Это подключит клиента, используя вашу существующую сессию
    
    # Преобразуем сессию в строку
    string_session = StringSession.save(client.session)
    
    print("Ваша строковая сессия:")
    print(string_session)