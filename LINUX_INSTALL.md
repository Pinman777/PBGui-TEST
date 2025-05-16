# Установка PBGui на Linux/Ubuntu

## Системные требования
- Python 3.8 или выше
- Git
- Доступ к командной строке с правами администратора

## Шаги установки

### 1. Клонирование репозитория

```bash
# Создаем директорию для проекта
mkdir -p ~/software
cd ~/software

# Клонируем репозиторий
git clone https://github.com/Pinman777/PBGui-TEST.git pbgui
cd pbgui
```

### 2. Создание виртуального окружения

```bash
# Создаем виртуальное окружение для PBGui
python3 -m venv ~/software/venv_pbgui

# Активируем виртуальное окружение
source ~/software/venv_pbgui/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 3. Создание виртуального окружения для Passivbot v6 и v7 (по необходимости)

```bash
# Для Passivbot v6
python3 -m venv ~/software/venv_pb6

# Для Passivbot v7
python3 -m venv ~/software/venv_pb7
```

### 4. Настройка конфигурации

Отредактируйте файл `pbgui.ini` в корневой директории проекта:

```ini
[main]
pbname = localhost
pbdir = /home/user/software/pb6    # Путь к вашей директории Passivbot v6
pbvenv = /home/user/software/venv_pb6/bin/python
pb7dir = /home/user/software/pb7   # Путь к вашей директории Passivbot v7
pb7venv = /home/user/software/venv_pb7/bin/python

[pbremote]
bucket = 

[coinmarketcap]
api_key = 
fetch_limit = 1000
fetch_interval = 4
```

Замените пути на актуальные для вашей системы.

### 5. Запуск PBGui

```bash
# Активируем виртуальное окружение, если еще не активировано
source ~/software/venv_pbgui/bin/activate

# Запускаем PBGui
cd ~/software/pbgui
python -m streamlit run pbgui.py
```

По умолчанию, PBGui будет доступен по адресу http://localhost:8501

### 6. Создание службы systemd (опционально)

Для автоматического запуска PBGui при старте системы, создайте файл службы systemd:

```bash
sudo nano /etc/systemd/system/pbgui.service
```

Добавьте следующее содержимое, заменив `username` на ваше имя пользователя:

```
[Unit]
Description=PBGui Streamlit Service
After=network.target

[Service]
User=username
WorkingDirectory=/home/username/software/pbgui
ExecStart=/home/username/software/venv_pbgui/bin/python -m streamlit run pbgui.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Активируйте и запустите службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pbgui.service
sudo systemctl start pbgui.service
```

Для проверки статуса службы:

```bash
sudo systemctl status pbgui.service
```

## Поиск и устранение неполадок

### Доступ из локальной сети

По умолчанию, Streamlit привязывается к localhost. Чтобы сделать интерфейс доступным из локальной сети, создайте файл конфигурации:

```bash
mkdir -p ~/.streamlit
echo '[server]
headless = true
enableCORS = false
enableXsrfProtection = false' > ~/.streamlit/config.toml
```

### Проблемы с правами доступа

Убедитесь, что у вас есть права на запись в директорию проекта:

```bash
sudo chown -R $USER:$USER ~/software/pbgui
```

### Логи

Логи PBGui хранятся в директории `data/logs`. Для просмотра логов:

```bash
tail -f ~/software/pbgui/data/logs/debug.log
``` 