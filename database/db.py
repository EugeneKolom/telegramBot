import sqlite3

class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.update_database_structure()

    def update_database_structure(self):
        cursor = self.conn.cursor()
        
        try:
            # Создаем временную таблицу для бэкапа
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                username TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id),
                UNIQUE(group_id, username)
            )
            ''')
            
            # Проверяем существует ли старая таблица contacts
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'")
            if cursor.fetchone():
                # Получаем список колонок в существующей таблице
                cursor.execute("PRAGMA table_info(contacts)")
                columns = [column[1] for column in cursor.fetchall()]
                
                # Если структура старая, копируем данные
                if 'username' not in columns:
                    print("Обновляем структуру базы данных...")
                    
                    # Создаем новую таблицу с правильной структурой
                    cursor.execute('''
                    CREATE TABLE contacts_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        username TEXT NOT NULL,
                        FOREIGN KEY (group_id) REFERENCES groups(id),
                        UNIQUE(group_id, username)
                    )
                    ''')
                    
                    # Копируем существующие данные если они есть
                    try:
                        cursor.execute("INSERT INTO contacts_new (group_id, username) SELECT group_id, username FROM contacts")
                    except:
                        print("Не удалось скопировать старые данные")
                    
                    # Удаляем старую таблицу
                    cursor.execute("DROP TABLE contacts")
                    
                    # Переименовываем новую таблицу
                    cursor.execute("ALTER TABLE contacts_new RENAME TO contacts")
                    
                    print("Структура базы данных обновлена")
            else:
                # Если таблицы нет, создаем с нужной структурой
                cursor.execute('''
                CREATE TABLE contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    username TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES groups(id),
                    UNIQUE(group_id, username)
                )
                ''')
                
            # Создаем таблицу для групп, если её нет
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE
            )
            ''')
            
            # Добавляем таблицу пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    phone TEXT,
                    session_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Добавляем таблицу invites
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS invites (
                username TEXT,
                group_id INTEGER,
                status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (username, group_id),
                FOREIGN KEY (group_id) REFERENCES groups(id)
            )
            ''')
            
            self.conn.commit()
            print("Проверка структуры базы данных завершена")
            
        except Exception as e:
            print(f"Ошибка при обновлении структуры базы данных: {e}")
            self.conn.rollback()
            raise e

    def execute(self, query, params=None):
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
