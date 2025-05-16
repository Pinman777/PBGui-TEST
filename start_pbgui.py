import sys
import os

# Добавляем текущий каталог в путь поиска Python
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Запускаем PBGui
import streamlit.web.cli as stcli
import streamlit as st

if __name__ == "__main__":
    sys.argv = ["streamlit", "run", "pbgui.py"]
    sys.exit(stcli.main()) 