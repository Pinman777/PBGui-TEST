import ccxt
import json
import os
import time
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
from Exchange import Exchange, Exchanges
from User import User, Users
from pbgui_func import PBGDIR

class MarketDataManager:
    """
    Универсальный менеджер для работы с рыночными данными различных бирж.
    Поддерживает: binance, bingx, bitget, blofin, bybit, gate, htx, kucoin, lbank, mexc, okx
    """
    
    def __init__(self):
        self.db_path = Path(f'{PBGDIR}/data/market_data.db')
        self.cache_dir = Path(f'{PBGDIR}/data/market_cache')
        if not self.cache_dir.exists():
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.users = Users()
        self.exchanges = {}
        self.supported_exchanges = {
            'binance': 'binance',
            'bingx': 'bingx',
            'bitget': 'bitget',
            'blofin': 'blofin',
            'bybit': 'bybit',
            'gate': 'gateio',
            'htx': 'huobi',
            'kucoin': 'kucoin',
            'lbank': 'lbank',
            'mexc': 'mexc',
            'okx': 'okx'
        }
        self._initialize_db()
        self._load_exchanges()
    
    def _initialize_db(self):
        """Инициализация базы данных для хранения рыночных данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу для тикеров (текущие цены)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            bid REAL,
            ask REAL,
            last REAL,
            volume REAL,
            raw_data TEXT,
            UNIQUE(exchange, symbol)
        )
        ''')
        
        # Создаем таблицу для OHLCV данных (свечи)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ohlcv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            UNIQUE(exchange, symbol, timeframe, timestamp)
        )
        ''')
        
        # Создаем таблицу для метаданных о символах
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            base_asset TEXT NOT NULL,
            quote_asset TEXT NOT NULL,
            price_precision INTEGER,
            quantity_precision INTEGER,
            min_notional REAL,
            min_qty REAL,
            max_qty REAL,
            market_type TEXT,
            last_updated INTEGER NOT NULL,
            raw_data TEXT,
            UNIQUE(exchange, symbol)
        )
        ''')
        
        # Создаем таблицу для кросс-биржевых корреляций
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            exchange1 TEXT NOT NULL,
            exchange2 TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            correlation REAL NOT NULL,
            timestamp INTEGER NOT NULL,
            UNIQUE(symbol, exchange1, exchange2, timeframe)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_exchanges(self):
        """Загружает экземпляры бирж на основе доступных пользователей"""
        self.users.load()
        
        # Создаем экземпляры для всех поддерживаемых бирж
        for exchange_name, ccxt_id in self.supported_exchanges.items():
            # Найдем пользователя для этой биржи, если он существует
            user = None
            for u in self.users:
                if u.exchange.lower() == exchange_name.lower():
                    user = u
                    break
            
            try:
                # Создаем экземпляр биржи с пользователем или без
                self.exchanges[exchange_name] = Exchange(ccxt_id, user)
            except Exception as e:
                print(f"Ошибка при инициализации биржи {exchange_name}: {str(e)}")
    
    def refresh_exchanges(self):
        """Обновляет экземпляры бирж на случай изменения пользователей"""
        self._load_exchanges()
    
    def get_ticker(self, exchange: str, symbol: str, force_update: bool = False) -> Dict:
        """
        Получает текущие данные тикера для указанного символа на бирже
        
        Args:
            exchange: Название биржи
            symbol: Символ (криптовалютная пара)
            force_update: Принудительно обновить данные с биржи
            
        Returns:
            Словарь с данными тикера
        """
        if exchange not in self.supported_exchanges:
            raise ValueError(f"Биржа {exchange} не поддерживается")
            
        if not force_update:
            # Проверяем есть ли свежие данные в базе (не старше 30 секунд)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tickers WHERE exchange = ? AND symbol = ? AND timestamp > ?",
                (exchange, symbol, int(time.time() * 1000) - 30000)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return json.loads(result[8])  # raw_data
        
        # Если нет свежих данных или требуется принудительное обновление
        try:
            # Получаем данные с биржи
            exchange_instance = self.exchanges[exchange]
            market_type = "swap"  # По умолчанию используем futures/swap
            ticker = exchange_instance.fetch_price(symbol, market_type)
            
            # Сохраняем в базу
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT OR REPLACE INTO tickers (exchange, symbol, timestamp, bid, ask, last, volume, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    exchange,
                    symbol,
                    ticker['timestamp'],
                    ticker.get('bid'),
                    ticker.get('ask'),
                    ticker.get('last'),
                    ticker.get('volume'),
                    json.dumps(ticker)
                )
            )
            
            conn.commit()
            conn.close()
            
            return ticker
        except Exception as e:
            print(f"Ошибка при получении тикера {symbol} с биржи {exchange}: {str(e)}")
            return None
    
    def get_ohlcv(self, exchange: str, symbol: str, timeframe: str = '1h', 
                 limit: int = 100, since: Optional[int] = None, 
                 force_update: bool = False) -> List:
        """
        Получает OHLCV данные (свечи) для указанного символа на бирже
        
        Args:
            exchange: Название биржи
            symbol: Символ (криптовалютная пара)
            timeframe: Временной интервал (1m, 5m, 15m, 1h, 4h, 1d и т.д.)
            limit: Количество свечей
            since: Временная метка начала в миллисекундах
            force_update: Принудительно обновить данные с биржи
            
        Returns:
            Список OHLCV данных
        """
        if exchange not in self.supported_exchanges:
            raise ValueError(f"Биржа {exchange} не поддерживается")
        
        # Если не требуется принудительное обновление, проверяем кэш
        if not force_update and not since:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT timestamp, open, high, low, close, volume FROM ohlcv "
                "WHERE exchange = ? AND symbol = ? AND timeframe = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (exchange, symbol, timeframe, limit)
            )
            result = cursor.fetchall()
            conn.close()
            
            if len(result) == limit:
                # Инвертируем, так как запрос был в обратном порядке
                return [[row[0], row[1], row[2], row[3], row[4], row[5]] for row in reversed(result)]
        
        # Получаем данные с биржи
        try:
            exchange_instance = self.exchanges[exchange]
            market_type = "swap"  # По умолчанию используем futures/swap
            ohlcv = exchange_instance.fetch_ohlcv(symbol, market_type, timeframe, limit, since)
            
            if ohlcv:
                # Сохраняем в базу
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for candle in ohlcv:
                    timestamp, open_price, high, low, close, volume = candle
                    cursor.execute(
                        "INSERT OR REPLACE INTO ohlcv (exchange, symbol, timeframe, timestamp, open, high, low, close, volume) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (exchange, symbol, timeframe, timestamp, open_price, high, low, close, volume)
                    )
                
                conn.commit()
                conn.close()
            
            return ohlcv
        except Exception as e:
            print(f"Ошибка при получении OHLCV для {symbol} с биржи {exchange}: {str(e)}")
            return []
    
    def synchronize_exchanges(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Dict:
        """
        Синхронизирует данные по указанному символу между всеми доступными биржами
        
        Args:
            symbol: Символ (криптовалютная пара)
            timeframe: Временной интервал (1m, 5m, 15m, 1h, 4h, 1d и т.д.)
            limit: Количество свечей для анализа
            
        Returns:
            Словарь с результатами синхронизации
        """
        results = {}
        available_exchanges = []
        ohlcv_data = {}
        
        # Получаем данные с каждой биржи
        for exchange_name, exchange in self.exchanges.items():
            try:
                data = self.get_ohlcv(exchange_name, symbol, timeframe, limit, force_update=True)
                if data and len(data) == limit:
                    available_exchanges.append(exchange_name)
                    ohlcv_data[exchange_name] = data
                    results[exchange_name] = {
                        "status": "success",
                        "last_price": data[-1][4],  # close price
                        "volume_24h": sum([candle[5] for candle in data if candle[0] > (time.time() - 86400) * 1000])
                    }
                else:
                    results[exchange_name] = {"status": "no_data"}
            except Exception as e:
                results[exchange_name] = {"status": "error", "message": str(e)}
        
        # Если есть хотя бы две биржи с данными, вычисляем корреляции
        if len(available_exchanges) >= 2:
            for i, exchange1 in enumerate(available_exchanges):
                for exchange2 in available_exchanges[i+1:]:
                    # Создаем DataFrame для вычисления корреляции
                    df1 = pd.DataFrame(ohlcv_data[exchange1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df2 = pd.DataFrame(ohlcv_data[exchange2], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    # Убедимся, что временные метки совпадают (или близки)
                    merged_df = pd.merge_asof(
                        df1.sort_values('timestamp'), 
                        df2.sort_values('timestamp'), 
                        on='timestamp', 
                        suffixes=('_1', '_2'), 
                        tolerance=60000  # Допуск 1 минута
                    )
                    
                    if not merged_df.empty:
                        correlation = merged_df['close_1'].corr(merged_df['close_2'])
                        price_ratio = merged_df['close_1'].iloc[-1] / merged_df['close_2'].iloc[-1]
                        
                        # Записываем корреляцию в базу
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT OR REPLACE INTO correlations (symbol, exchange1, exchange2, timeframe, correlation, timestamp) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (symbol, exchange1, exchange2, timeframe, correlation, int(time.time() * 1000))
                        )
                        conn.commit()
                        conn.close()
                        
                        results[f"{exchange1}_vs_{exchange2}"] = {
                            "correlation": correlation,
                            "price_ratio": price_ratio,
                            "price_difference_percent": (price_ratio - 1) * 100
                        }
        
        return results
    
    def update_market_data(self, exchanges: List[str] = None, symbols: List[str] = None, 
                          timeframes: List[str] = None) -> Dict:
        """
        Обновляет рыночные данные для указанных бирж, символов и таймфреймов
        
        Args:
            exchanges: Список бирж (если None, используются все доступные)
            symbols: Список символов (если None, используются все доступные)
            timeframes: Список таймфреймов (если None, используется ['1h', '4h', '1d'])
            
        Returns:
            Словарь с результатами обновления
        """
        if exchanges is None:
            exchanges = list(self.exchanges.keys())
        
        if timeframes is None:
            timeframes = ['1h', '4h', '1d']
        
        results = {}
        
        for exchange_name in exchanges:
            if exchange_name not in self.exchanges:
                results[exchange_name] = {"status": "error", "message": "Биржа не поддерживается"}
                continue
            
            exchange = self.exchanges[exchange_name]
            exchange_symbols = []
            
            if symbols is None:
                # Если символы не указаны, получаем их с биржи
                try:
                    exchange.load_market()
                    if exchange.market_type == "swap":
                        exchange_symbols = exchange.swap
                    else:
                        exchange_symbols = exchange.spot
                except Exception as e:
                    results[exchange_name] = {"status": "error", "message": f"Ошибка получения символов: {str(e)}"}
                    continue
            else:
                exchange_symbols = symbols
            
            results[exchange_name] = {"symbols": {}}
            
            for symbol in exchange_symbols:
                results[exchange_name]["symbols"][symbol] = {"timeframes": {}}
                
                # Получаем текущий тикер
                try:
                    ticker = self.get_ticker(exchange_name, symbol, force_update=True)
                    results[exchange_name]["symbols"][symbol]["ticker"] = "success" if ticker else "error"
                except Exception as e:
                    results[exchange_name]["symbols"][symbol]["ticker"] = f"error: {str(e)}"
                
                # Получаем OHLCV данные для каждого таймфрейма
                for timeframe in timeframes:
                    try:
                        ohlcv = self.get_ohlcv(exchange_name, symbol, timeframe, limit=100, force_update=True)
                        results[exchange_name]["symbols"][symbol]["timeframes"][timeframe] = "success" if ohlcv else "error"
                    except Exception as e:
                        results[exchange_name]["symbols"][symbol]["timeframes"][timeframe] = f"error: {str(e)}"
        
        return results
    
    def get_arbitrage_opportunities(self, min_difference: float = 0.5, quote_currency: str = "USDT") -> List[Dict]:
        """
        Ищет арбитражные возможности между биржами
        
        Args:
            min_difference: Минимальная разница в процентах для рассмотрения арбитража
            quote_currency: Валюта котировки (USDT, USDC и т.д.)
            
        Returns:
            Список словарей с арбитражными возможностями
        """
        opportunities = []
        
        # Получаем все символы с указанной валютой котировки
        all_symbols = {}
        
        for exchange_name, exchange in self.exchanges.items():
            try:
                exchange.load_market()
                symbols = [s for s in exchange.swap if s.endswith(quote_currency)]
                all_symbols[exchange_name] = symbols
            except Exception:
                continue
        
        # Находим общие символы на разных биржах
        common_symbols = set()
        for symbols in all_symbols.values():
            common_symbols.update(symbols)
        
        common_symbols = {s for s in common_symbols if sum(1 for symbols in all_symbols.values() if s in symbols) > 1}
        
        # Проверяем разницу в ценах
        for symbol in common_symbols:
            prices = {}
            
            for exchange_name, symbols in all_symbols.items():
                if symbol in symbols:
                    try:
                        ticker = self.get_ticker(exchange_name, symbol, force_update=True)
                        if ticker and 'last' in ticker and ticker['last']:
                            prices[exchange_name] = ticker['last']
                    except:
                        continue
            
            if len(prices) < 2:
                continue
            
            # Находим биржу с минимальной и максимальной ценой
            min_exchange = min(prices.items(), key=lambda x: x[1])
            max_exchange = max(prices.items(), key=lambda x: x[1])
            
            difference_percent = (max_exchange[1] - min_exchange[1]) / min_exchange[1] * 100
            
            if difference_percent >= min_difference:
                opportunities.append({
                    "symbol": symbol,
                    "buy_exchange": min_exchange[0],
                    "buy_price": min_exchange[1],
                    "sell_exchange": max_exchange[0],
                    "sell_price": max_exchange[1],
                    "difference_percent": difference_percent,
                    "timestamp": int(time.time() * 1000)
                })
        
        return sorted(opportunities, key=lambda x: x['difference_percent'], reverse=True)
    
    def get_all_data_for_symbol(self, symbol: str, timeframe: str = '1d', days: int = 30) -> Dict:
        """
        Получает все доступные данные по символу со всех бирж
        
        Args:
            symbol: Символ (криптовалютная пара)
            timeframe: Временной интервал
            days: Количество дней для анализа
            
        Returns:
            Словарь с данными со всех бирж
        """
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        limit = days * 24 // int(timeframe[0]) if timeframe.endswith('h') else days
        
        result = {}
        
        for exchange_name in self.exchanges:
            try:
                data = self.get_ohlcv(exchange_name, symbol, timeframe, limit, since, force_update=True)
                if data:
                    result[exchange_name] = {
                        "ohlcv": data,
                        "current_price": data[-1][4],
                        "price_change_percent": ((data[-1][4] - data[0][4]) / data[0][4]) * 100,
                        "volume_avg": sum(candle[5] for candle in data) / len(data)
                    }
            except Exception as e:
                result[exchange_name] = {"error": str(e)}
        
        return result
    
    def export_data_to_csv(self, exchange: str, symbol: str, timeframe: str, 
                         days: int = 30, filename: Optional[str] = None) -> str:
        """
        Экспортирует OHLCV данные в CSV файл
        
        Args:
            exchange: Название биржи
            symbol: Символ (криптовалютная пара)
            timeframe: Временной интервал
            days: Количество дней для экспорта
            filename: Имя файла (если None, генерируется автоматически)
            
        Returns:
            Путь к созданному CSV файлу
        """
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        limit = days * 24 // int(timeframe[0]) if timeframe.endswith('h') else days
        
        data = self.get_ohlcv(exchange, symbol, timeframe, limit, since, force_update=True)
        
        if not data:
            raise ValueError(f"Данные не найдены для {symbol} на бирже {exchange}")
        
        if filename is None:
            filename = f"{exchange}_{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        filepath = os.path.join(self.cache_dir, filename)
        
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.to_csv(filepath, index=False)
        
        return filepath 