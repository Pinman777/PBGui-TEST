# Установка PBGui на Ubuntu 22.04.5 LTS

## Системные требования
- Ubuntu 22.04.5 LTS
- Python 3.8 или выше
- Git
- Доступ к командной строке с правами администратора

## Методы установки

### Метод 1: Быстрый запуск (одной командой)

Для быстрого запуска PBGui одной командой выполните следующие действия:

```bash
# Клонируем репозиторий
git clone https://github.com/Pinman777/PBGui-TEST.git
cd PBGui-TEST

# Делаем скрипт запуска исполняемым
chmod +x launch.sh

# Запускаем PBGui
./launch.sh
```

Скрипт `launch.sh` автоматически:
- Проверит зависимости
- Создаст виртуальное окружение
- Установит необходимые пакеты
- Создаст нужные директории
- Запустит PBData и PBGui

По умолчанию PBGui будет доступен по адресу http://localhost:8501

### Метод 2: Пошаговая установка

Если вы предпочитаете полный контроль над процессом установки, следуйте этим шагам:

### 1. Подготовка системы

```bash
# Обновляем пакеты
sudo apt update
sudo apt upgrade -y

# Устанавливаем необходимые пакеты
sudo apt install -y python3-pip python3-venv git
```

### 2. Клонирование репозитория

```bash
# Создаем директорию для проекта
mkdir -p ~/software
cd ~/software

# Клонируем репозиторий
git clone https://github.com/Pinman777/PBGui-TEST.git pbgui
cd pbgui
```

### 3. Создание виртуального окружения и установка зависимостей

```bash
# Создаем виртуальное окружение для PBGui
python3 -m venv ~/software/venv_pbgui

# Активируем виртуальное окружение
source ~/software/venv_pbgui/bin/activate

# Обновляем pip
pip install --upgrade pip

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 4. Создание необходимых директорий

```bash
# Создаем директории для данных и кэша
mkdir -p data/logs
mkdir -p data/market_cache
mkdir -p data/strategies
mkdir -p data/pid
```

### 5. Создание виртуальных окружений для Passivbot (при необходимости)

```bash
# Для Passivbot v6 (при необходимости)
python3 -m venv ~/software/venv_pb6

# Для Passivbot v7 (при необходимости)
python3 -m venv ~/software/venv_pb7
```

### 6. Настройка конфигурации

Создайте или отредактируйте файл `pbgui.ini` в корневой директории проекта:

```bash
# Копируем пример конфигурации, если файл не существует
cp -n pbgui.ini.example pbgui.ini

# Редактируем конфигурацию
nano pbgui.ini
```

Внесите свои настройки в файл, например:

```ini
[main]
pbname = localhost
pbdir = /home/username/software/pb6    # Путь к директории Passivbot v6
pbvenv = /home/username/software/venv_pb6/bin/python
pb7dir = /home/username/software/pb7   # Путь к директории Passivbot v7
pb7venv = /home/username/software/venv_pb7/bin/python

[pbremote]
bucket = 

[coinmarketcap]
api_key = 
fetch_limit = 1000
fetch_interval = 4

[pbdata]
fetch_users = []
```

Замените `username` на ваше имя пользователя.

### 7. Настройка доступа из локальной сети

```bash
# Создаем конфигурацию для Streamlit
mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << EOF
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
EOF
```

### 8. Запуск PBGui

```bash
# Активируем виртуальное окружение (если не активировано)
source ~/software/venv_pbgui/bin/activate

# Запускаем PBGui
cd ~/software/pbgui
python -m streamlit run pbgui.py
```

По умолчанию PBGui будет доступен по адресу http://localhost:8501 и по адресу http://ваш-IP-адрес:8501 в локальной сети.

### 9. Создание службы systemd (для автозапуска)

Создайте файл службы systemd для автоматического запуска PBGui при старте системы:

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

### Проблемы с правами доступа

Если у вас возникают проблемы с правами доступа, выполните:

```bash
sudo chown -R $USER:$USER ~/software/pbgui
sudo chmod -R 755 ~/software/pbgui
```

### Просмотр логов

Логи PBGui хранятся в директории `data/logs`. Для просмотра логов:

```bash
tail -f ~/software/pbgui/data/logs/debug.log
```

### Перезапуск службы

Если вы внесли изменения в код или конфигурацию, перезапустите службу:

```bash
sudo systemctl restart pbgui.service
```

### Проверка статуса Streamlit

Чтобы убедиться, что Streamlit работает правильно:

```bash
ps aux | grep streamlit
``` 