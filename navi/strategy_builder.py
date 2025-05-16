import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import json
import os
from datetime import datetime, timedelta
from MarketDataManager import MarketDataManager
from StrategyManager import StrategyManager, Strategy
from pbgui_purefunc import save_ini, load_ini

# Инициализация менеджеров
@st.cache_resource
def get_market_data_manager():
    return MarketDataManager()

@st.cache_resource
def get_strategy_manager(_mdm):
    return StrategyManager(_mdm)

mdm = get_market_data_manager()
sm = get_strategy_manager(mdm)

st.title("💹 Конструктор Стратегий")

# Инициализация сессии
if "current_strategy_id" not in st.session_state:
    st.session_state.current_strategy_id = None
if "code_changed" not in st.session_state:
    st.session_state.code_changed = False
if "editor_height" not in st.session_state:
    st.session_state.editor_height = 400

# Функции обработчики
def on_strategy_select():
    if st.session_state.strategy_selector != st.session_state.current_strategy_id:
        if st.session_state.code_changed:
            st.warning("У вас есть несохраненные изменения. Сохраните их перед переключением стратегии.")
            return
        st.session_state.current_strategy_id = st.session_state.strategy_selector
        st.session_state.code_changed = False

def on_code_change():
    st.session_state.code_changed = True

def create_new_strategy():
    if st.session_state.new_strategy_name.strip():
        strategy = sm.create_strategy(
            st.session_state.new_strategy_name,
            st.session_state.new_strategy_description,
            st.session_state.new_strategy_author
        )
        st.session_state.current_strategy_id = strategy.id
        st.session_state.code_changed = False
        st.rerun()

# Боковая панель с выбором стратегии
with st.sidebar:
    # Список стратегий
    strategies = sm.list_strategies()
    strategy_options = {s.id: f"{s.name} ({s.author})" for s in strategies}
    
    if strategy_options:
        st.selectbox(
            "Выберите стратегию:",
            options=list(strategy_options.keys()),
            format_func=lambda x: strategy_options[x],
            key="strategy_selector",
            on_change=on_strategy_select
        )
    else:
        st.info("Нет доступных стратегий. Создайте новую стратегию.")
    
    # Кнопка создания новой стратегии
    with st.expander("Создать новую стратегию"):
        st.text_input("Название стратегии:", key="new_strategy_name")
        st.text_area("Описание:", key="new_strategy_description")
        st.text_input("Автор:", key="new_strategy_author")
        if st.button("Создать", use_container_width=True):
            create_new_strategy()
    
    # Настройки интерфейса
    st.divider()
    st.slider("Высота редактора кода:", 200, 800, st.session_state.editor_height, 50, 
             key="editor_height_slider", on_change=lambda: setattr(st.session_state, "editor_height", st.session_state.editor_height_slider))

# Основная область
tabs = st.tabs(["Редактор", "Параметры", "Бэктестинг", "Результаты"])

# Получаем текущую стратегию
current_strategy = sm.get_strategy(st.session_state.current_strategy_id) if st.session_state.current_strategy_id else None

# Шаблон кода по умолчанию
default_code = """# Стратегия бота
# Доступные переменные:
# df_<exchange>_<symbol>_<timeframe> - DataFrame с данными (timestamp, open, high, low, close, volume, datetime)
# params - словарь с параметрами стратегии
# Доступные функции:
# log(message) - Запись сообщения в лог
# add_signal(exchange, symbol, side, price, amount, reason, timeframe) - Добавить торговый сигнал

# Пример: Простая стратегия пересечения скользящих средних
for exchange in params["exchanges"]:
    for symbol in params["symbols"]:
        for timeframe in params["timeframes"]:
            df = data[f"{exchange}_{symbol}_{timeframe}"]
            
            # Вычисляем индикаторы
            df['sma_fast'] = df['close'].rolling(window=params["fast_period"]).mean()
            df['sma_slow'] = df['close'].rolling(window=params["slow_period"]).mean()
            
            # Ищем пересечения (кроссоверы)
            df['signal'] = 0
            df.loc[df['sma_fast'] > df['sma_slow'], 'signal'] = 1
            df.loc[df['sma_fast'] < df['sma_slow'], 'signal'] = -1
            
            # Находим точки входа (изменение сигнала)
            df['signal_change'] = df['signal'].diff()
            
            # Последние данные для принятия решения
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2] if len(df) > 1 else None
            
            if prev_row is not None:
                # Сигнал на покупку: быстрая SMA пересекла медленную SMA снизу вверх
                if last_row['signal_change'] == 2:
                    log(f"Сигнал на покупку для {symbol} на {exchange} ({timeframe})")
                    add_signal(
                        exchange=exchange,
                        symbol=symbol,
                        side="buy",
                        price=last_row['close'],
                        amount=params["position_size"],
                        reason="SMA Fast пересекла SMA Slow снизу вверх",
                        timeframe=timeframe
                    )
                
                # Сигнал на продажу: быстрая SMA пересекла медленную SMA сверху вниз
                elif last_row['signal_change'] == -2:
                    log(f"Сигнал на продажу для {symbol} на {exchange} ({timeframe})")
                    add_signal(
                        exchange=exchange,
                        symbol=symbol,
                        side="sell",
                        price=last_row['close'],
                        amount=params["position_size"],
                        reason="SMA Fast пересекла SMA Slow сверху вниз",
                        timeframe=timeframe
                    )
"""

# Вкладка редактора
with tabs[0]:
    if current_strategy:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"### Редактирование стратегии: {current_strategy.name}")
        with col2:
            save_btn = st.button("Сохранить изменения", type="primary", use_container_width=True)
        
        # Редактор кода
        code = st.text_area(
            "Код стратегии:",
            value=current_strategy.code if current_strategy.code else default_code,
            height=st.session_state.editor_height,
            key="strategy_code",
            on_change=on_code_change
        )
        
        # Сохраняем изменения
        if save_btn:
            current_strategy.set_code(st.session_state.strategy_code)
            sm.save_strategy(current_strategy)
            st.session_state.code_changed = False
            st.success("Изменения сохранены!")
    else:
        st.info("Выберите стратегию или создайте новую для начала работы.")

# Вкладка параметров
with tabs[1]:
    if current_strategy:
        st.write(f"### Параметры стратегии: {current_strategy.name}")
        
        col1, col2 = st.columns(2)
        
        # Настройка рынков
        with col1:
            with st.expander("Настройка рынков", expanded=True):
                # Выбор бирж
                available_exchanges = list(mdm.supported_exchanges.keys())
                selected_exchanges = st.multiselect(
                    "Биржи:",
                    options=available_exchanges,
                    default=current_strategy.exchanges or ["binance"]
                )
                
                # Получаем символы для выбранных бирж
                all_symbols = []
                for exchange_name in selected_exchanges:
                    if exchange_name in mdm.exchanges:
                        exchange = mdm.exchanges[exchange_name]
                        try:
                            exchange.load_market()
                            symbols = [s for s in exchange.swap]
                            all_symbols.extend(symbols)
                        except:
                            pass
                
                # Уникальные символы
                unique_symbols = sorted(list(set(all_symbols)))
                
                # Выбор символов
                symbol_input = st.text_area(
                    "Символы (по одному на строку):", 
                    value="\n".join(current_strategy.symbols) if current_strategy.symbols else "BTCUSDT"
                )
                selected_symbols = [s.strip() for s in symbol_input.split("\n") if s.strip()]
                
                # Выбор таймфреймов
                timeframe_options = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
                selected_timeframes = st.multiselect(
                    "Таймфреймы:",
                    options=timeframe_options,
                    default=current_strategy.timeframes or ["1h"]
                )
                
                # Тип рынка
                market_type = st.selectbox(
                    "Тип рынка:",
                    options=["swap", "spot"],
                    index=0 if current_strategy.market_type == "swap" else 1
                )
        
        # Настройка параметров стратегии
        with col2:
            with st.expander("Параметры стратегии", expanded=True):
                st.write("Добавьте параметры для вашей стратегии:")
                
                # Параметры по умолчанию для стратегии скользящих средних
                default_params = {
                    "fast_period": 10,
                    "slow_period": 30,
                    "position_size": 0.1
                }
                
                # Объединяем с существующими параметрами
                params = {**default_params, **current_strategy.parameters}
                
                # Редактирование параметров
                new_params = {}
                
                # Динамические поля для параметров
                new_params["fast_period"] = st.number_input("Период быстрой SMA:", value=params.get("fast_period", 10), min_value=1)
                new_params["slow_period"] = st.number_input("Период медленной SMA:", value=params.get("slow_period", 30), min_value=1)
                new_params["position_size"] = st.number_input("Размер позиции:", value=params.get("position_size", 0.1), min_value=0.01, step=0.01)
                
                # Добавление произвольных параметров
                with st.expander("Добавить произвольный параметр"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_param_name = st.text_input("Имя параметра:")
                    with col2:
                        new_param_value = st.text_input("Значение параметра:")
                    
                    if st.button("Добавить параметр") and new_param_name:
                        try:
                            # Пытаемся преобразовать в число, если возможно
                            value = json.loads(new_param_value)
                        except:
                            value = new_param_value
                        
                        new_params[new_param_name] = value
                
                # Сохраняем дополнительные параметры из существующих
                for k, v in params.items():
                    if k not in new_params:
                        new_params[k] = v
                
                # Добавляем биржи, символы и таймфреймы в параметры
                new_params["exchanges"] = selected_exchanges
                new_params["symbols"] = selected_symbols
                new_params["timeframes"] = selected_timeframes
        
        # Кнопка сохранения параметров
        if st.button("Сохранить параметры", type="primary"):
            # Обновляем стратегию
            current_strategy.set_parameters(new_params)
            current_strategy.set_markets(selected_exchanges, selected_symbols, selected_timeframes, market_type)
            
            # Сохраняем стратегию
            sm.save_strategy(current_strategy)
            st.success("Параметры сохранены!")
    else:
        st.info("Выберите стратегию или создайте новую для настройки параметров.")

# Вкладка бэктестинга
with tabs[2]:
    if current_strategy:
        st.write(f"### Бэктестинг стратегии: {current_strategy.name}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            start_date = st.date_input(
                "Дата начала:",
                value=datetime.now() - timedelta(days=30)
            )
        
        with col2:
            end_date = st.date_input(
                "Дата окончания:",
                value=datetime.now()
            )
        
        with col3:
            initial_balance = st.number_input(
                "Начальный баланс (USDT):",
                min_value=100.0,
                value=10000.0,
                step=1000.0
            )
        
        # Параметры для переопределения
        with st.expander("Переопределить параметры для теста"):
            # Создаем копию текущих параметров
            override_params = {}
            for key, value in current_strategy.parameters.items():
                if key not in ["exchanges", "symbols", "timeframes"]:
                    if isinstance(value, (int, float)):
                        override_params[key] = st.number_input(f"{key}:", value=value)
                    else:
                        override_params[key] = st.text_input(f"{key}:", value=str(value))
        
        # Кнопка запуска бэктеста
        if st.button("Запустить бэктест", type="primary"):
            with st.spinner("Выполняется бэктест..."):
                # Форматируем даты
                start_date_str = start_date.strftime("%Y-%m-%d")
                end_date_str = end_date.strftime("%Y-%m-%d")
                
                # Запускаем бэктест
                backtest_result = sm.backtest_strategy(
                    current_strategy,
                    start_date_str,
                    end_date_str,
                    initial_balance,
                    override_params
                )
                
                # Сохраняем результаты в сессию
                st.session_state.backtest_result = backtest_result
                
                # Переходим на вкладку результатов
                st.rerun()
    else:
        st.info("Выберите стратегию или создайте новую для запуска бэктеста.")

# Вкладка результатов
with tabs[3]:
    if current_strategy and "backtest_result" in st.session_state:
        st.write(f"### Результаты бэктеста: {current_strategy.name}")
        
        result = st.session_state.backtest_result
        
        # Метрики производительности
        metrics = result["metrics"]
        
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("Общая доходность", f"{metrics['total_return_pct']:.2f}%")
        with metric_cols[1]:
            st.metric("Годовая доходность", f"{metrics['annualized_return_pct']:.2f}%")
        with metric_cols[2]:
            st.metric("Макс. просадка", f"{metrics['max_drawdown_pct']:.2f}%")
        with metric_cols[3]:
            st.metric("Коэф. Шарпа", f"{metrics['sharpe_ratio']:.2f}")
        
        metric_cols = st.columns(3)
        with metric_cols[0]:
            st.metric("Процент выигрышных сделок", f"{metrics['win_rate_pct']:.2f}%")
        with metric_cols[1]:
            st.metric("Фактор прибыли", f"{metrics['profit_factor']:.2f}")
        with metric_cols[2]:
            st.metric("Всего сделок", f"{metrics['total_trades']}")
        
        # График кривой капитала
        if result["portfolio"]["equity_curve"]:
            equity_curve = pd.DataFrame(result["portfolio"]["equity_curve"])
            
            fig = px.line(
                equity_curve,
                x="datetime",
                y="value",
                title="Кривая капитала",
                labels={"value": "Стоимость портфеля", "datetime": "Дата"}
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Список сделок
        if result["portfolio"]["trades"]:
            trades_df = pd.DataFrame(result["portfolio"]["trades"])
            
            # Форматируем данные
            trades_df["pnl_formatted"] = trades_df["pnl"].apply(lambda x: f"{x:.2f}" if "pnl" in trades_df.columns and not pd.isna(x) else "")
            trades_df["cost_formatted"] = trades_df["cost"].apply(lambda x: f"{x:.2f}")
            trades_df["price_formatted"] = trades_df["price"].apply(lambda x: f"{x:.8f}")
            
            st.subheader("Сделки")
            
            # Создаем цветовой стиль для положительных/отрицательных PnL
            if "pnl" in trades_df.columns:
                def color_pnl(val):
                    if pd.isna(val):
                        return ""
                    return "color: green" if val > 0 else "color: red"
                
                # Отображаем сделки
                st.dataframe(
                    trades_df.style.applymap(
                        color_pnl, 
                        subset=["pnl"] if "pnl" in trades_df.columns else []
                    ),
                    use_container_width=True
                )
            else:
                st.dataframe(trades_df, use_container_width=True)
        
        # Логи
        if result["logs"]:
            with st.expander("Логи выполнения", expanded=False):
                for log in result["logs"]:
                    st.text(log)
    else:
        if current_strategy:
            st.info("Запустите бэктест, чтобы увидеть результаты.")
        else:
            st.info("Выберите стратегию или создайте новую для просмотра результатов.")

# Дополнительные функции в боковой панели
with st.sidebar:
    st.divider()
    
    if current_strategy:
        # Экспорт стратегии
        if st.button("Экспортировать стратегию", use_container_width=True):
            export_path = f"data/strategies/export_{current_strategy.name.replace(' ', '_')}.json"
            if sm.export_strategy(current_strategy.id, export_path):
                st.success(f"Стратегия экспортирована в {export_path}")
                
                # Добавляем кнопку скачивания
                with open(export_path, "r") as f:
                    st.download_button(
                        label="Скачать файл стратегии",
                        data=f.read(),
                        file_name=f"{current_strategy.name.replace(' ', '_')}.json",
                        mime="application/json"
                    )
            else:
                st.error("Ошибка при экспорте стратегии")
        
        # Удаление стратегии
        if st.button("Удалить стратегию", use_container_width=True):
            if st.session_state.current_strategy_id:
                if sm.delete_strategy(st.session_state.current_strategy_id):
                    st.session_state.current_strategy_id = None
                    st.success("Стратегия удалена")
                    st.rerun()
                else:
                    st.error("Ошибка при удалении стратегии")
    
    # Импорт стратегии
    with st.expander("Импорт стратегии"):
        uploaded_file = st.file_uploader("Загрузить файл стратегии", type=["json"])
        if uploaded_file:
            try:
                # Сохраняем файл временно
                import_path = f"data/strategies/import_{uploaded_file.name}"
                with open(import_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Импортируем стратегию
                strategy = sm.import_strategy(import_path)
                if strategy:
                    st.session_state.current_strategy_id = strategy.id
                    st.success(f"Стратегия '{strategy.name}' успешно импортирована")
                    st.rerun()
                else:
                    st.error("Ошибка при импорте стратегии")
            except Exception as e:
                st.error(f"Ошибка при импорте: {str(e)}")

# Информация о модуле
with st.sidebar:
    st.divider()
    st.info("""
    **Конструктор Стратегий**
    
    Позволяет создавать собственные торговые стратегии на основе данных с разных бирж:
    - Редактирование кода стратегии
    - Настройка параметров
    - Бэктестинг стратегии
    - Анализ результатов
    - Экспорт/импорт стратегий
    """) 