#!/bin/bash
# Скрипт быстрого запуска PBGui на Ubuntu 22.04.5 LTS
# Сделайте этот файл исполняемым: chmod +x launch.sh

# Проверка зависимостей
command -v python3 >/dev/null 2>&1 || { echo "Python 3 не установлен. Установите его с помощью 'sudo apt install python3'"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "Pip не установлен. Установите его с помощью 'sudo apt install python3-pip'"; exit 1; }

# Определение путей
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="${SCRIPT_DIR}/venv"

# Создание виртуального окружения, если оно не существует
if [ ! -d "$VENV_DIR" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv "$VENV_DIR"
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source "${VENV_DIR}/bin/activate"
fi

# Создание необходимых директорий
mkdir -p "${SCRIPT_DIR}/data/logs"
mkdir -p "${SCRIPT_DIR}/data/market_cache"
mkdir -p "${SCRIPT_DIR}/data/strategies"
mkdir -p "${SCRIPT_DIR}/data/pid"

# Функция для остановки всех процессов при закрытии
cleanup() {
    echo "Остановка всех процессов..."
    pkill -f "python.*PBData.py" || true
    exit 0
}

# Регистрация обработчика выхода
trap cleanup EXIT

# Запуск сервисов
echo "Запуск PBData..."
python "$SCRIPT_DIR/PBData.py" &

# Небольшая задержка
sleep 2

# Запуск основного приложения
echo "Запуск PBGui..."
python -m streamlit run "$SCRIPT_DIR/pbgui.py" 