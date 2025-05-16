import json
import os
import uuid
import importlib.util
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable
from datetime import datetime
from MarketDataManager import MarketDataManager
from pbgui_func import PBGDIR

class Strategy:
    """
    Базовый класс для создания пользовательских торговых стратегий
    """
    def __init__(self, name: str, description: str = "", author: str = ""):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.author = author
        self.created_at = datetime.now().timestamp()
        self.updated_at = self.created_at
        self.parameters = {}
        self.exchanges = []
        self.symbols = []
        self.timeframes = []
        self.market_type = "swap"  # По умолчанию используем фьючерсы
        self.limit = 100
        self.since = None
        self.code = ""
        
    def set_parameters(self, parameters: Dict[str, Any]):
        """Устанавливает параметры стратегии"""
        self.parameters = parameters
        self.updated_at = datetime.now().timestamp()
        return self
    
    def set_markets(self, exchanges: List[str], symbols: List[str], timeframes: List[str], market_type: str = "swap"):
        """Устанавливает рынки для стратегии"""
        self.exchanges = exchanges
        self.symbols = symbols
        self.timeframes = timeframes
        self.market_type = market_type
        self.updated_at = datetime.now().timestamp()
        return self
    
    def set_code(self, code: str):
        """Устанавливает код стратегии"""
        self.code = code
        self.updated_at = datetime.now().timestamp()
        return self
    
    def to_dict(self) -> Dict:
        """Конвертирует стратегию в словарь для сохранения"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parameters": self.parameters,
            "exchanges": self.exchanges,
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "market_type": self.market_type,
            "limit": self.limit,
            "code": self.code
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Strategy':
        """Создает стратегию из словаря"""
        strategy = cls(data["name"], data.get("description", ""), data.get("author", ""))
        strategy.id = data["id"]
        strategy.created_at = data["created_at"]
        strategy.updated_at = data["updated_at"]
        strategy.parameters = data["parameters"]
        strategy.exchanges = data["exchanges"]
        strategy.symbols = data["symbols"]
        strategy.timeframes = data["timeframes"]
        strategy.market_type = data["market_type"]
        strategy.limit = data.get("limit", 100)
        strategy.code = data["code"]
        return strategy

class StrategyManager:
    """
    Менеджер пользовательских торговых стратегий
    """
    def __init__(self, mdm: MarketDataManager):
        self.mdm = mdm
        self.strategies_dir = Path(f'{PBGDIR}/data/strategies')
        if not self.strategies_dir.exists():
            self.strategies_dir.mkdir(parents=True, exist_ok=True)
        self.strategies = self._load_strategies()
        self.current_strategy = None
        
    def _load_strategies(self) -> Dict[str, Strategy]:
        """Загружает все стратегии из директории стратегий"""
        strategies = {}
        for file in self.strategies_dir.glob("*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                strategy = Strategy.from_dict(data)
                strategies[strategy.id] = strategy
            except Exception as e:
                print(f"Ошибка при загрузке стратегии {file}: {str(e)}")
        return strategies
    
    def save_strategy(self, strategy: Strategy) -> bool:
        """Сохраняет стратегию в файл"""
        try:
            file_path = self.strategies_dir / f"{strategy.id}.json"
            with open(file_path, "w") as f:
                json.dump(strategy.to_dict(), f, indent=4)
            self.strategies[strategy.id] = strategy
            return True
        except Exception as e:
            print(f"Ошибка при сохранении стратегии {strategy.name}: {str(e)}")
            return False
    
    def create_strategy(self, name: str, description: str = "", author: str = "") -> Strategy:
        """Создает новую стратегию"""
        strategy = Strategy(name, description, author)
        self.save_strategy(strategy)
        return strategy
    
    def delete_strategy(self, strategy_id: str) -> bool:
        """Удаляет стратегию"""
        try:
            file_path = self.strategies_dir / f"{strategy_id}.json"
            if file_path.exists():
                file_path.unlink()
            if strategy_id in self.strategies:
                del self.strategies[strategy_id]
            return True
        except Exception as e:
            print(f"Ошибка при удалении стратегии {strategy_id}: {str(e)}")
            return False
    
    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Получает стратегию по ID"""
        return self.strategies.get(strategy_id)
    
    def list_strategies(self) -> List[Strategy]:
        """Возвращает список всех стратегий"""
        return list(self.strategies.values())
    
    def execute_strategy(self, strategy: Strategy, params: Optional[Dict] = None) -> Dict:
        """
        Выполняет стратегию с возможностью переопределения параметров
        
        Returns:
            Dict с результатами: {
                "success": bool,
                "signals": List[Dict],
                "data": Dict,
                "logs": List[str],
                "error": Optional[str]
            }
        """
        # Объединяем параметры стратегии с переопределенными
        strategy_params = {**strategy.parameters}
        if params:
            strategy_params.update(params)
        
        # Создаем временный модуль для выполнения кода стратегии
        spec = importlib.util.spec_from_loader(f"strategy_{strategy.id}", loader=None)
        module = importlib.util.module_from_spec(spec)
        
        # Добавляем необходимые импорты и контекст
        setup_code = """
import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta

# Глобальные переменные для стратегии
signals = []
logs = []
data = {}

def log(message):
    logs.append(str(message))

def add_signal(exchange, symbol, side, price, amount, reason="", timeframe=""):
    signals.append({
        "exchange": exchange,
        "symbol": symbol,
        "side": side,  # "buy" или "sell"
        "price": price,
        "amount": amount,
        "reason": reason,
        "timeframe": timeframe,
        "timestamp": datetime.now().timestamp()
    })
"""
        
        # Подготавливаем данные для стратегии
        data_prep_code = "try:\n"
        
        # Загружаем данные для каждой комбинации биржи, символа и таймфрейма
        for exchange in strategy.exchanges:
            for symbol in strategy.symbols:
                for timeframe in strategy.timeframes:
                    var_name = f"df_{exchange}_{symbol}_{timeframe}".replace("-", "_").replace(".", "_")
                    data_prep_code += f"""
    # Загружаем данные для {exchange} {symbol} {timeframe}
    ohlcv_{exchange}_{symbol}_{timeframe} = mdm.get_ohlcv("{exchange}", "{symbol}", "{timeframe}", {strategy.limit})
    {var_name} = pd.DataFrame(ohlcv_{exchange}_{symbol}_{timeframe}, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    {var_name}['datetime'] = pd.to_datetime({var_name}['timestamp'], unit='ms')
    data["{exchange}_{symbol}_{timeframe}"] = {var_name}
"""
                    
        data_prep_code += """
except Exception as e:
    logs.append(f"Ошибка при загрузке данных: {str(e)}")
    success = False
    error = str(e)
"""
        
        # Добавляем выполнение стратегии
        execution_code = f"""
# Параметры стратегии
params = {json.dumps(strategy_params)}

# Код стратегии
success = True
error = None
try:
{strategy.code}
except Exception as e:
    logs.append(f"Ошибка при выполнении стратегии: {{str(e)}}")
    success = False
    error = str(e)
"""
        
        # Объединяем весь код
        full_code = setup_code + data_prep_code + execution_code
        
        # Выполняем код
        global_vars = {
            "mdm": self.mdm,
            "__name__": module.__name__
        }
        
        try:
            exec(full_code, global_vars)
            # Получаем результаты
            return {
                "success": global_vars.get("success", False),
                "signals": global_vars.get("signals", []),
                "data": global_vars.get("data", {}),
                "logs": global_vars.get("logs", []),
                "error": global_vars.get("error")
            }
        except Exception as e:
            return {
                "success": False,
                "signals": [],
                "data": {},
                "logs": [],
                "error": f"Критическая ошибка при выполнении стратегии: {str(e)}"
            }
    
    def backtest_strategy(self, strategy: Strategy, start_date: str, end_date: str, initial_balance: float = 10000.0, params: Optional[Dict] = None) -> Dict:
        """
        Выполняет бэктестинг стратегии на историческом периоде
        
        Args:
            strategy: Стратегия для тестирования
            start_date: Дата начала в формате 'YYYY-MM-DD'
            end_date: Дата окончания в формате 'YYYY-MM-DD'
            initial_balance: Начальный баланс
            params: Параметры для переопределения
            
        Returns:
            Dict с результатами бэктестинга
        """
        # Конвертируем даты в UNIX timestamp
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        
        # Определяем период для тестирования
        period_days = (end_ts - start_ts) // (1000 * 60 * 60 * 24)
        
        # Портфель для отслеживания позиций и баланса
        portfolio = {
            "balance": initial_balance,
            "positions": {},
            "trades": [],
            "equity_curve": []
        }
        
        # Дневная петля для симуляции торговли
        current_ts = start_ts
        
        while current_ts <= end_ts:
            # Устанавливаем стратегии ограничение по времени
            strategy.since = current_ts
            strategy.limit = 100
            
            # Выполняем стратегию на текущую дату
            result = self.execute_strategy(strategy, params)
            
            if result["success"]:
                # Обрабатываем сигналы
                for signal in result["signals"]:
                    # Проверяем, что сигнал в пределах текущего временного окна
                    signal_ts = signal["timestamp"] * 1000
                    if start_ts <= signal_ts <= current_ts:
                        # Обрабатываем торговый сигнал
                        self._process_trade_signal(portfolio, signal, current_ts)
                
                # Обновляем стоимость портфеля
                portfolio_value = portfolio["balance"]
                for symbol, position in portfolio["positions"].items():
                    if position["size"] != 0:
                        # Получаем текущую цену
                        exchange = position["exchange"]
                        current_price = self._get_latest_price(exchange, symbol, current_ts)
                        position_value = position["size"] * current_price
                        portfolio_value += position_value
                
                # Добавляем точку в кривую капитала
                portfolio["equity_curve"].append({
                    "timestamp": current_ts,
                    "value": portfolio_value,
                    "datetime": datetime.fromtimestamp(current_ts / 1000).strftime('%Y-%m-%d')
                })
            
            # Переходим к следующему дню
            current_ts += 24 * 60 * 60 * 1000
        
        # Рассчитываем метрики
        metrics = self._calculate_metrics(portfolio, initial_balance, start_ts, end_ts)
        
        return {
            "portfolio": portfolio,
            "metrics": metrics,
            "logs": result.get("logs", [])
        }
    
    def _process_trade_signal(self, portfolio: Dict, signal: Dict, current_ts: int):
        """Обрабатывает торговый сигнал в симуляции"""
        symbol = signal["symbol"]
        exchange = signal["exchange"]
        side = signal["side"]
        price = signal["price"]
        amount = signal["amount"]
        
        # Создаем ключ для позиции
        position_key = f"{exchange}_{symbol}"
        
        # Инициализируем позицию, если она не существует
        if position_key not in portfolio["positions"]:
            portfolio["positions"][position_key] = {
                "exchange": exchange,
                "symbol": symbol,
                "size": 0,
                "entry_price": 0,
                "cost": 0
            }
        
        position = portfolio["positions"][position_key]
        
        # Рассчитываем стоимость сделки
        trade_cost = price * amount
        
        # Обрабатываем покупку
        if side == "buy":
            if portfolio["balance"] >= trade_cost:
                # Обновляем позицию
                new_size = position["size"] + amount
                new_cost = position["cost"] + trade_cost
                position["entry_price"] = new_cost / new_size if new_size > 0 else 0
                position["size"] = new_size
                position["cost"] = new_cost
                
                # Уменьшаем баланс
                portfolio["balance"] -= trade_cost
                
                # Записываем сделку
                portfolio["trades"].append({
                    "timestamp": current_ts,
                    "datetime": datetime.fromtimestamp(current_ts / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    "exchange": exchange,
                    "symbol": symbol,
                    "side": side,
                    "price": price,
                    "amount": amount,
                    "cost": trade_cost,
                    "balance_after": portfolio["balance"]
                })
        
        # Обрабатываем продажу
        elif side == "sell":
            if position["size"] >= amount:
                # Рассчитываем прибыль/убыток
                trade_value = price * amount
                cost_basis = position["entry_price"] * amount
                pnl = trade_value - cost_basis
                
                # Обновляем позицию
                new_size = position["size"] - amount
                position["size"] = new_size
                if new_size == 0:
                    position["entry_price"] = 0
                    position["cost"] = 0
                else:
                    position["cost"] = position["entry_price"] * new_size
                
                # Увеличиваем баланс
                portfolio["balance"] += trade_value
                
                # Записываем сделку
                portfolio["trades"].append({
                    "timestamp": current_ts,
                    "datetime": datetime.fromtimestamp(current_ts / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    "exchange": exchange,
                    "symbol": symbol,
                    "side": side,
                    "price": price,
                    "amount": amount,
                    "cost": trade_value,
                    "pnl": pnl,
                    "balance_after": portfolio["balance"]
                })
    
    def _get_latest_price(self, exchange: str, symbol: str, timestamp: int) -> float:
        """Получает последнюю доступную цену до указанного timestamp"""
        try:
            ohlcv = self.mdm.get_ohlcv(exchange, symbol, "1d", 1, timestamp - 24*60*60*1000)
            if ohlcv and len(ohlcv) > 0:
                return ohlcv[0][4]  # Close price
            return 0
        except:
            return 0
    
    def _calculate_metrics(self, portfolio: Dict, initial_balance: float, start_ts: int, end_ts: int) -> Dict:
        """Рассчитывает метрики производительности портфеля"""
        if not portfolio["equity_curve"]:
            return {
                "total_return_pct": 0,
                "annualized_return_pct": 0,
                "max_drawdown_pct": 0,
                "sharpe_ratio": 0,
                "win_rate_pct": 0,
                "profit_factor": 0,
                "total_trades": 0
            }
        
        # Создаем DataFrame с кривой капитала
        equity_df = pd.DataFrame(portfolio["equity_curve"])
        
        # Рассчитываем общую доходность
        initial_value = initial_balance
        final_value = equity_df["value"].iloc[-1]
        total_return = (final_value - initial_value) / initial_value
        
        # Рассчитываем годовую доходность
        days = (end_ts - start_ts) / (1000 * 60 * 60 * 24)
        annualized_return = ((1 + total_return) ** (365 / days)) - 1 if days > 0 else 0
        
        # Рассчитываем максимальную просадку
        equity_df["prev_peak"] = equity_df["value"].cummax()
        equity_df["drawdown"] = (equity_df["value"] - equity_df["prev_peak"]) / equity_df["prev_peak"]
        max_drawdown = equity_df["drawdown"].min()
        
        # Рассчитываем коэффициент Шарпа (если достаточно данных)
        if len(equity_df) > 1:
            equity_df["daily_return"] = equity_df["value"].pct_change()
            avg_return = equity_df["daily_return"].mean()
            std_return = equity_df["daily_return"].std()
            sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Рассчитываем процент выигрышных сделок и фактор прибыли
        trades_df = pd.DataFrame(portfolio["trades"])
        if not trades_df.empty and "pnl" in trades_df.columns:
            winning_trades = trades_df[trades_df["pnl"] > 0]
            win_rate = len(winning_trades) / len(trades_df) if len(trades_df) > 0 else 0
            
            # Фактор прибыли
            gross_profit = winning_trades["pnl"].sum() if not winning_trades.empty else 0
            losing_trades = trades_df[trades_df["pnl"] < 0]
            gross_loss = abs(losing_trades["pnl"].sum()) if not losing_trades.empty else 0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        else:
            win_rate = 0
            profit_factor = 0
        
        return {
            "total_return_pct": total_return * 100,
            "annualized_return_pct": annualized_return * 100,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_ratio": sharpe_ratio,
            "win_rate_pct": win_rate * 100,
            "profit_factor": profit_factor,
            "total_trades": len(portfolio["trades"])
        }
    
    def export_strategy(self, strategy_id: str, file_path: str) -> bool:
        """Экспортирует стратегию в файл"""
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return False
        
        try:
            with open(file_path, "w") as f:
                json.dump(strategy.to_dict(), f, indent=4)
            return True
        except Exception as e:
            print(f"Ошибка при экспорте стратегии {strategy_id}: {str(e)}")
            return False
    
    def import_strategy(self, file_path: str) -> Optional[Strategy]:
        """Импортирует стратегию из файла"""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            strategy = Strategy.from_dict(data)
            self.save_strategy(strategy)
            return strategy
        except Exception as e:
            print(f"Ошибка при импорте стратегии из {file_path}: {str(e)}")
            return None 