# -*- coding: utf-8 -*-
"""Конфигурация арбитражного бота"""

# API настройки
API_BASE_URL = "https://api.bybit.com/v5"
RECV_WINDOW = "5000"

# Торговые параметры
TRADE_AMOUNT_USD = 30.0
LEVERAGE = 1

# Пороги для арбитража
MIN_SPREAD_PCT = 0.0
MIN_ENTRY_SPREAD_PCT = 0.0
MIN_FUNDING_RATE = 0.02
MIN_PROFIT_PCT = -0.2
COMMISSION_PCT = 0.27

CLOSE_FR_THRESHOLD = -0.001
MAX_CLOSE_SPREAD_PCT = 0.5

# Параметры мониторинга
MONITOR_INTERVAL_SEC = 300
MAX_MONITOR_ATTEMPTS = 1000

# Параметры потоков
MAX_WORKERS_ORDERBOOK = 20
MAX_WORKERS_FUNDING = 10

# Rate Limiting
MAX_REQUESTS_PER_SECOND = 50  # Безопасное значение (Bybit лимит: 120)
MAX_WEIGHT_PER_SECOND = 300   # Безопасное значение (Bybit лимит: 600)

# НОВОЕ: Параметры многопоточной торговли
MAX_CONCURRENT_POSITIONS = 1  # Максимум одновременных позиций
MAX_TRADING_THREADS = 3       # Максимум потоков для торговли
POSITIONS_DIR = "positions"   # Директория для хранения позиций
SCAN_INTERVAL_SEC = 180        # Интервал сканирования новых возможностей

# Файл сохранения позиции
POSITION_FILE = "open_position.json"

# ✅ НОВОЕ: Список исключений для криптовалют
BLACKLIST_FILE = "blacklist.json"

# ✅ НОВОЕ: Коды ошибок, при которых криптовалюта добавляется в blacklist
CRITICAL_ERROR_CODES = [
    30228,  # No new positions during delisting
    10001,  # Symbol not found
    110043, # Set margin mode failed (suspended trading)
]

LOW_FR_TRACKING_THRESHOLD = 0.01
MIN_FUNDING_PAYMENTS_FOR_CLOSE = 10
