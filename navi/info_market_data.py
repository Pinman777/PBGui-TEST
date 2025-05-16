import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from MarketDataManager import MarketDataManager
from datetime import datetime, timedelta
from pbgui_purefunc import save_ini, load_ini
import os

# Инициализация менеджера рыночных данных
@st.cache_resource
def get_market_data_manager():
    return MarketDataManager()

mdm = get_market_data_manager()

st.title("🌍 Межбиржевые Рыночные Данные")

tabs = st.tabs(["Мультибиржевой просмотр", "Арбитраж", "Синхронизация", "Экспорт данных"])

with tabs[0]:
    st.header("Мультибиржевой Просмотр")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbol = st.text_input("Символ (например, BTCUSDT):", "BTCUSDT")
    with col2:
        timeframe = st.selectbox("Таймфрейм:", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
    with col3:
        days = st.number_input("Количество дней:", min_value=1, max_value=90, value=30)
    
    if st.button("Получить данные", type="primary"):
        with st.spinner("Получение данных со всех бирж..."):
            try:
                data = mdm.get_all_data_for_symbol(symbol, timeframe, days)
                
                if not data:
                    st.error(f"Не удалось получить данные для {symbol}")
                else:
                    # Создаем таблицу с текущими ценами
                    price_data = []
                    for exchange, exchange_data in data.items():
                        if "error" not in exchange_data:
                            price_data.append({
                                "Биржа": exchange,
                                "Текущая цена": exchange_data.get("current_price"),
                                "Изменение (%)": exchange_data.get("price_change_percent"),
                                "Средний объем": exchange_data.get("volume_avg")
                            })
                    
                    if price_data:
                        price_df = pd.DataFrame(price_data)
                        st.subheader("Сравнение цен на разных биржах")
                        st.dataframe(price_df, use_container_width=True)
                        
                        # Создаем график цен
                        fig = go.Figure()
                        
                        for exchange, exchange_data in data.items():
                            if "error" not in exchange_data and "ohlcv" in exchange_data:
                                ohlcv = exchange_data["ohlcv"]
                                timestamps = [datetime.fromtimestamp(ts/1000) for ts, _, _, _, _, _ in ohlcv]
                                close_prices = [close for _, _, _, _, close, _ in ohlcv]
                                fig.add_trace(go.Scatter(
                                    x=timestamps,
                                    y=close_prices,
                                    mode='lines',
                                    name=exchange
                                ))
                        
                        fig.update_layout(
                            title=f"{symbol} - Сравнение цен закрытия ({timeframe})",
                            xaxis_title="Дата",
                            yaxis_title="Цена",
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Вычисляем корреляцию между биржами
                        exchanges = [e for e in data.keys() if "error" not in data[e]]
                        if len(exchanges) > 1:
                            st.subheader("Матрица корреляций")
                            corr_data = {}
                            
                            for exchange in exchanges:
                                if "ohlcv" in data[exchange]:
                                    corr_data[exchange] = [close for _, _, _, _, close, _ in data[exchange]["ohlcv"]]
                            
                            if corr_data:
                                corr_df = pd.DataFrame(corr_data)
                                correlation_matrix = corr_df.corr()
                                
                                # Визуализация матрицы корреляций
                                fig = go.Figure(data=go.Heatmap(
                                    z=correlation_matrix.values,
                                    x=correlation_matrix.columns,
                                    y=correlation_matrix.index,
                                    colorscale='Viridis',
                                    zmin=-1, zmax=1,
                                    text=np.round(correlation_matrix.values, 3),
                                    texttemplate="%{text}",
                                    showscale=True
                                ))
                                fig.update_layout(
                                    title="Матрица корреляций цен закрытия между биржами",
                                    width=600,
                                    height=600
                                )
                                st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Не удалось получить данные ни с одной биржи")
            except Exception as e:
                st.error(f"Ошибка при получении данных: {str(e)}")

with tabs[1]:
    st.header("Арбитражные Возможности")
    
    col1, col2 = st.columns(2)
    with col1:
        min_diff = st.slider("Минимальная разница (%)", min_value=0.1, max_value=5.0, value=0.5, step=0.1)
    with col2:
        quote_currency = st.selectbox("Валюта котировки:", ["USDT", "USDC", "BUSD", "TUSD"])
    
    if st.button("Найти арбитражные возможности", type="primary"):
        with st.spinner("Поиск арбитражных возможностей..."):
            try:
                opportunities = mdm.get_arbitrage_opportunities(min_diff, quote_currency)
                
                if not opportunities:
                    st.info(f"Не найдено арбитражных возможностей с разницей от {min_diff}%")
                else:
                    # Создаем таблицу с возможностями
                    arb_data = []
                    for opp in opportunities:
                        arb_data.append({
                            "Символ": opp["symbol"],
                            "Биржа (покупка)": opp["buy_exchange"],
                            "Цена (покупка)": opp["buy_price"],
                            "Биржа (продажа)": opp["sell_exchange"],
                            "Цена (продажа)": opp["sell_price"],
                            "Разница (%)": opp["difference_percent"]
                        })
                    
                    st.subheader(f"Найдено {len(opportunities)} арбитражных возможностей")
                    arb_df = pd.DataFrame(arb_data)
                    st.dataframe(arb_df, use_container_width=True)
                    
                    # Визуализируем топ-5 возможностей
                    if len(opportunities) > 0:
                        top_opportunities = opportunities[:5] if len(opportunities) > 5 else opportunities
                        
                        fig = go.Figure()
                        symbols = [opp["symbol"] for opp in top_opportunities]
                        diff_pcts = [opp["difference_percent"] for opp in top_opportunities]
                        
                        fig.add_trace(go.Bar(
                            x=symbols,
                            y=diff_pcts,
                            text=np.round(diff_pcts, 2),
                            textposition='auto',
                            marker_color='lightseagreen'
                        ))
                        
                        fig.update_layout(
                            title="Топ арбитражные возможности",
                            xaxis_title="Символ",
                            yaxis_title="Разница (%)",
                            yaxis=dict(range=[0, max(diff_pcts) * 1.1])
                        )
                        st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Ошибка при поиске арбитражных возможностей: {str(e)}")

with tabs[2]:
    st.header("Синхронизация Данных")
    
    col1, col2 = st.columns(2)
    with col1:
        sync_symbol = st.text_input("Символ для синхронизации:", "BTCUSDT")
    with col2:
        sync_timeframe = st.selectbox("Таймфрейм для синхронизации:", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
    
    if st.button("Синхронизировать данные", type="primary"):
        with st.spinner("Синхронизация данных между биржами..."):
            try:
                results = mdm.synchronize_exchanges(sync_symbol, sync_timeframe)
                
                if not results:
                    st.error("Не удалось получить результаты синхронизации")
                else:
                    # Фильтруем успешные результаты
                    exchange_results = {k: v for k, v in results.items() if "status" in v and v["status"] == "success"}
                    
                    if exchange_results:
                        # Таблица с ценами на разных биржах
                        price_data = []
                        for exchange, result in exchange_results.items():
                            price_data.append({
                                "Биржа": exchange,
                                "Последняя цена": result["last_price"],
                                "Объем (24ч)": result["volume_24h"]
                            })
                        
                        st.subheader("Цены на разных биржах")
                        price_df = pd.DataFrame(price_data)
                        st.dataframe(price_df, use_container_width=True)
                        
                        # Таблица с корреляциями
                        corr_data = []
                        for key, value in results.items():
                            if "_vs_" in key:  # Это запись о корреляции
                                exchanges = key.split("_vs_")
                                corr_data.append({
                                    "Биржа 1": exchanges[0],
                                    "Биржа 2": exchanges[1],
                                    "Корреляция": value["correlation"],
                                    "Соотношение цен": value["price_ratio"],
                                    "Разница (%)": value["price_difference_percent"]
                                })
                        
                        if corr_data:
                            st.subheader("Корреляции между биржами")
                            corr_df = pd.DataFrame(corr_data)
                            st.dataframe(corr_df, use_container_width=True)
                    else:
                        st.warning("Не удалось получить данные ни с одной биржи")
            except Exception as e:
                st.error(f"Ошибка при синхронизации: {str(e)}")
    
    st.divider()
    
    st.subheader("Массовое обновление данных")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_exchanges = st.multiselect(
            "Выберите биржи для обновления:",
            list(mdm.supported_exchanges.keys()),
            default=["binance", "bybit"]
        )
    with col2:
        selected_timeframes = st.multiselect(
            "Выберите таймфреймы для обновления:",
            ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
            default=["1h", "4h", "1d"]
        )
    
    symbols_text = st.text_area(
        "Введите символы для обновления (по одному на строку, оставьте пустым для всех символов):",
        height=100
    )
    selected_symbols = [s.strip() for s in symbols_text.split("\n") if s.strip()] if symbols_text else None
    
    if st.button("Обновить рыночные данные", type="primary"):
        if not selected_exchanges:
            st.error("Выберите хотя бы одну биржу")
        elif not selected_timeframes:
            st.error("Выберите хотя бы один таймфрейм")
        else:
            with st.spinner("Обновление рыночных данных..."):
                try:
                    results = mdm.update_market_data(selected_exchanges, selected_symbols, selected_timeframes)
                    
                    if not results:
                        st.error("Не удалось получить результаты обновления")
                    else:
                        success_count = 0
                        error_count = 0
                        
                        for exchange, exchange_results in results.items():
                            if "status" in exchange_results and exchange_results["status"] == "error":
                                st.error(f"Ошибка для биржи {exchange}: {exchange_results['message']}")
                                error_count += 1
                                continue
                            
                            if "symbols" in exchange_results:
                                for symbol, symbol_results in exchange_results["symbols"].items():
                                    ticker_status = symbol_results["ticker"]
                                    if "error" in ticker_status:
                                        error_count += 1
                                    else:
                                        success_count += 1
                        
                        st.success(f"Обновление завершено. Успешно: {success_count}, Ошибок: {error_count}")
                except Exception as e:
                    st.error(f"Ошибка при обновлении данных: {str(e)}")

with tabs[3]:
    st.header("Экспорт Данных")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        export_exchange = st.selectbox("Биржа:", list(mdm.supported_exchanges.keys()))
    with col2:
        export_symbol = st.text_input("Символ:", "BTCUSDT")
    with col3:
        export_timeframe = st.selectbox("Таймфрейм:", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
    
    col1, col2 = st.columns(2)
    with col1:
        export_days = st.number_input("Количество дней:", min_value=1, max_value=365, value=30)
    with col2:
        export_filename = st.text_input("Имя файла (оставьте пустым для автоматического):", "")
    
    if st.button("Экспортировать в CSV", type="primary"):
        with st.spinner("Экспорт данных..."):
            try:
                filename = None if not export_filename else export_filename
                filepath = mdm.export_data_to_csv(
                    export_exchange, export_symbol, export_timeframe, export_days, filename)
                
                st.success(f"Данные успешно экспортированы в: {filepath}")
                
                # Загрузка и отображение данных
                try:
                    df = pd.read_csv(filepath)
                    st.dataframe(df, use_container_width=True)
                    
                    # Создание графика
                    fig = go.Figure(data=[go.Candlestick(
                        x=df['datetime'],
                        open=df['open'],
                        high=df['high'],
                        low=df['low'],
                        close=df['close']
                    )])
                    
                    fig.update_layout(
                        title=f"{export_symbol} на {export_exchange} ({export_timeframe})",
                        xaxis_title="Дата",
                        yaxis_title="Цена",
                        xaxis_rangeslider_visible=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Добавляем кнопку для скачивания CSV
                    st.download_button(
                        label="Скачать CSV файл",
                        data=open(filepath, 'rb').read(),
                        file_name=os.path.basename(filepath),
                        mime="text/csv",
                    )
                except Exception as e:
                    st.error(f"Ошибка при отображении данных: {str(e)}")
            except Exception as e:
                st.error(f"Ошибка при экспорте данных: {str(e)}")

# Обновление списка пользователей при необходимости
if st.sidebar.button("Обновить список пользователей"):
    mdm.refresh_exchanges()
    st.sidebar.success("Список пользователей обновлен")

# Статус подключения к биржам
st.sidebar.divider()
st.sidebar.subheader("Статус подключения к биржам")
for exchange_name, exchange in mdm.exchanges.items():
    if exchange.user and exchange.user.key != 'key':
        st.sidebar.success(f"✅ {exchange_name} ({exchange.user.name})")
    else:
        st.sidebar.warning(f"⚠️ {exchange_name} (без API)")

# Обновить все рыночные данные
st.sidebar.divider()
if st.sidebar.button("Обновить все рыночные данные"):
    with st.sidebar.status("Обновление данных..."):
        try:
            result = mdm.update_market_data()
            st.sidebar.write("Обновление завершено")
        except Exception as e:
            st.sidebar.error(f"Ошибка: {str(e)}")
            
# Добавим информацию о модуле
st.sidebar.divider()
st.sidebar.info("""
**Модуль Рыночные Данные**

Позволяет работать с данными с разных бирж:
- Сравнивать цены и объемы
- Искать арбитражные возможности
- Синхронизировать данные между биржами
- Экспортировать данные для анализа
""") 