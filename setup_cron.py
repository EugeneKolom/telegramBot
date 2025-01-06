from crontab import CronTab

# Укажите своего пользователя
cron = CronTab(user='kliptoman')

# Создаем новую задачу
job = cron.new(command='python3.9 /home/kliptoman/run_bot.py')

# Задаем интервал выполнения (каждые 15 минут)
job.minute.every(15)

cron.write()
print("Cron задача создана!")
