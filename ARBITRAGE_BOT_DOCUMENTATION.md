# Назначение проекта

Автоматический арбитражный бот для криптовалютной биржи Bybit. Система торгует арбитражем между спот и фьючерсными рынками, зарабатывая на положительном funding rate и спредах цен. Поддерживает множественные одновременные позиции с автоматическим мониторингом и закрытием по достижению целевых условий.

## Архитектура

- **Exchange**: Bybit API v5
- **Strategy**: Spot-Futures Arbitrage (Cash & Carry)
- **Concurrency**: Threading + ThreadPoolExecutor
- **Rate Limiting**: Token Bucket Algorithm
- **Storage**: SQLite база данных (SQLAlchemy ORM)
- **Migrations**: Alembic для управления схемой БД
- **Design Pattern**: Repository Pattern + Dependency Injection
- **Notifications**: Telegram Bot (python-telegram-bot v20+)
- **Logging**: Структурированное логирование с уровнями

## Структура проекта

```
/
├── main.py                          # Точка входа (запускает orchestrator)
├── .env                             # Конфигурация (API ключи Bybit + Telegram)
├── arbitrage.db                     # SQLite база данных
│
├── orchestrator.py                  # Главный координатор: сканирование + многопоточный мониторинг
├── config.py                        # Все константы и пороговые значения
│
├── /database/                       # Слой работы с БД
│   ├── __init__.py
│   ├── database.py                  # Инициализация БД, SQLAlchemy engine, session
│   ├── models.py                    # SQLAlchemy модели (Position, ClosedPosition, Blacklist)
│   └── /repositories/               # Repository Pattern для доступа к данным
│       ├── __init__.py
│       ├── base_repository.py       # Базовый класс для всех репозиториев
│       ├── position_repository.py   # CRUD операции с позициями
│       ├── history_repository.py    # Работа с историей закрытых позиций
│       └── blacklist_repository.py  # Работа с blacklist
│
├── /migrations/                     # Alembic миграции БД
│   ├── env.py                       # Конфигурация Alembic
│   ├── script.py.mako               # Шаблон для новых миграций
│   ├── alembic.ini                  # Настройки Alembic
│   └── /versions/                   # История миграций
│       └── xxx_initial_schema.py
│
├── /scripts/                        # Утилиты и скрипты
│   └── migrate_blacklist_to_db.py   # Миграция blacklist.json → БД (одноразовый)
│
├── /telegram_bot/                   # 🆕 Telegram бот интеграция
│   ├── __init__.py
│   ├── bot.py                       # Главный класс TelegramBot (lifecycle management)
│   ├── handlers.py                  # Command handlers (/start, /status, /positions, /stats)
│   ├── formatters.py                # Message formatters (форматирование данных)
│   ├── notifications.py             # Notification service (отправка уведомлений)
│   └── config.py                    # Telegram конфигурация (токен, admin chat_ids)
│
├── /integration/                    # 🆕 Интеграция внешних сервисов
│   ├── __init__.py
│   └── telegram_integration.py      # TelegramIntegration (singleton для доступа к боту)
│
├── /api/
│   ├── api_client.py                # Базовый клиент Bybit API (GET/POST с retry)
│   ├── auth.py                      # API ключи и создание подписи HMAC
│   └── rate_limiter.py              # Rate limiting (requests/sec, weight/sec)
│
├── /services/
│   ├── price_service.py             # Получение цен (orderbook, ticker)
│   ├── funding_rate_service.py      # Получение funding rates
│   ├── spread_analyzer.py           # Фильтрация по спредам
│   ├── arbitrage_calculator.py      # Расчет возможностей арбитража
│   ├── opportunity_monitor.py       # Мониторинг и исполнение (открытие/закрытие позиций)
│   └── order_executor.py            # Размещение ордеров (спот/фьючерс)
│
├── /managers/
│   ├── position_manager.py          # Управление позициями через репозитории (DI)
│   ├── blacklist_manager.py         # Управление blacklist через репозитории (DI)
│   ├── leverage_manager.py          # Установка плеча
│   └── balance.py                   # Получение балансов
│
├── /calculators/
│   ├── pnl_calculator.py            # Расчет PnL при закрытии
│   └── funding_calculator.py        # Расчет РЕАЛЬНОГО фандинга через API
│
└── /utils/
    ├── logger_config.py             # Конфигурация логирования
    └── utils.py                     # Утилиты (timestamp корректировка)
```

## Ключевые компоненты

### 1. Database Layer (database/)

**Слой доступа к данным с использованием Repository Pattern**

#### database.py
- Создание SQLAlchemy engine и session factory
- Проверка подключения к БД (`check_db_connection()`)
- Настройка SQLite (WAL mode, foreign keys)

#### models.py - SQLAlchemy модели
```python
class Position(Base):
    __tablename__ = 'positions'
    id = Column(Integer, primary_key=True)
    crypto = Column(String(20), unique=True, index=True)
    spot_entry_price = Column(Float)
    futures_entry_price = Column(Float)
    spot_qty = Column(Float)
    futures_qty = Column(Float)
    entry_spread_pct = Column(Float)
    entry_timestamp = Column(DateTime)
    funding_payments_count = Column(Integer, default=0)
    low_fr_count = Column(Integer, default=0)
    consecutive_low_fr = Column(Boolean, default=False)
    # ...

class ClosedPosition(Base):
    __tablename__ = 'closed_positions'
    id = Column(Integer, primary_key=True)
    crypto = Column(String(20), index=True)
    entry_timestamp = Column(DateTime)
    close_timestamp = Column(DateTime, index=True)
    net_pnl = Column(Float)
    funding_pnl = Column(Float)
    # ...

class Blacklist(Base):
    __tablename__ = 'blacklist'
    id = Column(Integer, primary_key=True)
    crypto = Column(String(20), unique=True, index=True)
    reason = Column(Text)
    error_code = Column(Integer, nullable=True)
    timestamp = Column(DateTime)
    # ...
```

#### Repositories - паттерн доступа к данным

**PositionRepository** (`position_repository.py`)
- `create_position()` - создание новой позиции
- `get_by_crypto()` - получение позиции по символу
- `has_position()` - проверка существования
- `get_all_open()` - все открытые позиции
- `increment_funding_count()` - обновление счетчика фандинга
- `delete_by_crypto()` - удаление позиции
- `update_position_quantities()` - обновление qty после докупки

**HistoryRepository** (`history_repository.py`)
- `save_closed_position()` - сохранение закрытой позиции
- `get_all_history()` - вся история
- `get_history_by_crypto()` - история по конкретной криптовалюте
- `get_recent_history()` - последние N закрытых позиций
- `get_statistics()` / `calculate_statistics()` - статистика (total PnL, win rate, avg PnL)

**BlacklistRepository** (`blacklist_repository.py`)
- `add_to_blacklist()` - добавление в blacklist
- `is_blacklisted()` - проверка наличия
- `remove_from_blacklist()` - удаление
- `get_all_blacklisted()` - все записи (Set[str])
- `get_all_details()` - все записи с деталями
- `bulk_add()` - массовое добавление (для миграции)

### 2. Telegram Bot Integration (telegram_bot/) 🆕

**Полнофункциональная интеграция с Telegram для уведомлений и управления**

#### Архитектура
- **bot.py**: Главный класс `TelegramBot` - управление жизненным циклом бота
- **handlers.py**: Command handlers - обработка пользовательских команд
- **formatters.py**: Message formatters - форматирование данных для Telegram
- **notifications.py**: Notification service - отправка уведомлений о событиях
- **config.py**: Конфигурация (токен бота, admin chat IDs)

#### TelegramBot (bot.py)

**Главный класс для управления Telegram ботом**

```python
class TelegramBot:
    def __init__(
        self,
        position_repo: Optional[PositionRepository] = None,
        history_repo: Optional[HistoryRepository] = None,
        blacklist_repo: Optional[BlacklistRepository] = None
    ):
        # Dependency Injection репозиториев
        self.position_repo = position_repo or PositionRepository()
        self.history_repo = history_repo or HistoryRepository()
        self.blacklist_repo = blacklist_repo or BlacklistRepository()

        # Создание handlers с доступом к репозиториям
        self.handlers = CommandHandlers(...)

        # Создание Application
        self.application = Application.builder().token(BOT_TOKEN).build()

    def start(self) -> bool:
        # Запускает бота в отдельном daemon thread
        # Использует asyncio.new_event_loop() для совместимости с threading

    def stop(self) -> None:
        # Корректное завершение работы бота
```

**Особенности реализации**:
- Запуск в отдельном daemon thread (не блокирует основной процесс)
- Использование `asyncio.new_event_loop()` для работы в non-main thread
- Dependency Injection репозиториев для доступа к данным
- Graceful shutdown с ожиданием завершения потока

#### Command Handlers (handlers.py)

**Обработчики пользовательских команд**

```python
class CommandHandlers:
    async def start(update, context):
        # Приветственное сообщение + список команд

    async def status(update, context):
        # Статус системы:
        # - Время работы
        # - Количество открытых позиций
        # - Размер blacklist
        # - Доступные слоты для новых позиций

    async def positions(update, context):
        # Список открытых позиций:
        # - Crypto symbol
        # - Время входа + длительность
        # - Цены входа (спот/фьючерс)
        # - Количества
        # - Спред входа

    async def stats(update, context):
        # Статистика торговли:
        # - Общее количество сделок
        # - Прибыльные/убыточные
        # - Win rate
        # - Total PnL
        # - Average PnL
        # - Лучшая/худшая сделка
```

**Пример вывода `/positions`:**
```
📍 ОТКРЫТЫЕ ПОЗИЦИИ (1)

1. BOBA
├─ Вход: 05.01 16:05 (1ч 15мин назад)
├─ Спот: 0.042540 USDT (qty: 703.9406)
├─ Фьючерс: 0.042740 USDT (qty: 701.9000)
└─ Спред: 0.47%
```

**Пример вывода `/stats`:**
```
📊 Статистика торговли

🔢 Сделки: 12
✅ Прибыльных: 10 (83.3%)
❌ Убыточных: 2 (16.7%)

💰 Финансы
• Общая прибыль: +45.80 USDT
• Средняя прибыль: +3.82 USDT
• Лучшая сделка: +8.50 USDT
• Худшая сделка: -2.10 USDT
```

#### Notification Service (notifications.py)

**Автоматические уведомления о торговых событиях**

```python
class TelegramNotificationService:
    def notify_position_opened(self, position_data: Dict):
        # Уведомление об открытии позиции
        # - Crypto symbol
        # - Цены входа (спот/фьючерс)
        # - Количества
        # - Спред входа
        # - Funding rate

    def notify_position_closed(self, position_data: Dict):
        # Уведомление о закрытии позиции
        # - Crypto symbol
        # - Длительность позиции
        # - Spot PnL
        # - Futures PnL
        # - Funding PnL
        # - Commission
        # - Net PnL

    def notify_critical_error(self, error_data: Dict):
        # 🚨 КРИТИЧЕСКОЕ уведомление
        # Используется когда фьючерс открыт, но спот не открылся
        # - Тип ошибки
        # - Crypto symbol
        # - Qty фьючерса для ручного закрытия
        # - Текст ошибки

    def notify_blacklist_added(self, crypto: str, reason: str, error_code: int):
        # Уведомление о добавлении в blacklist
        # - Crypto symbol
        # - Причина
        # - Код ошибки (если есть)
```

**Пример уведомления об открытии:**
```
🟢 Позиция открыта

💼 BOBA
• Спот: 0.042540 USDT (qty: 703.94)
• Фьючерс: 0.042740 USDT (qty: 701.90)
• Спред: 0.47%
• Funding Rate: 0.11%
```

**Пример уведомления о закрытии:**
```
🔴 Позиция закрыта

💼 BOBA
⏱ Время: 2ч 15мин

💰 PnL
• Спот: +1.25 USDT
• Фьючерс: +0.80 USDT
• Фандинг: +0.45 USDT
• Комиссии: -0.62 USDT
• Чистая прибыль: +1.88 USDT
```

**Пример критического уведомления:**
```
🚨 КРИТИЧЕСКАЯ ОШИБКА

⚠️ Тип: Фьючерс открыт, спот не открылся

💼 BOBA
• Qty: 701.9000
• Ошибка: Insufficient balance

🔴 НЕОБХОДИМО ВРУЧНУЮ ЗАКРЫТЬ ФЬЮЧЕРС!
```

#### TelegramIntegration (integration/telegram_integration.py)

**Singleton для глобального доступа к Telegram боту**

```python
class TelegramIntegration:
    _instance = None  # Singleton

    def __init__(self):
        self.telegram_bot = TelegramBot(
            position_repo=PositionRepository(),
            history_repo=HistoryRepository(),
            blacklist_repo=BlacklistRepository()
        )
        self.notification_service = TelegramNotificationService(...)

    def start_bot(self) -> bool:
        return self.telegram_bot.start()

    def stop_bot(self):
        self.telegram_bot.stop()

    def notify_position_opened(self, **kwargs):
        self.notification_service.notify_position_opened(kwargs)

    def notify_position_closed(self, **kwargs):
        self.notification_service.notify_position_closed(kwargs)

    # ... другие методы уведомлений

# Глобальный доступ
def get_telegram_integration() -> Optional[TelegramIntegration]:
    return TelegramIntegration.get_instance()
```

**Использование в opportunity_monitor.py:**
```python
from integration.telegram_integration import get_telegram_integration

# При открытии позиции
telegram = get_telegram_integration()
if telegram:
    telegram.notify_position_opened(
        crypto=crypto,
        spot_entry_price=spot_ask,
        futures_entry_price=futures_bid,
        spot_qty=purchased_qty,
        entry_spread_pct=spread_pct,
        funding_rate=funding_rate
    )

# При закрытии позиции
if telegram:
    telegram.notify_position_closed(
        crypto=crypto,
        entry_time=entry_timestamp,
        close_time=close_timestamp,
        spot_pnl=pnl_result['spot_pnl'],
        futures_pnl=pnl_result['futures_pnl'],
        funding=pnl_result['funding'],
        commission=pnl_result['commission'],
        net_pnl=pnl_result['net_pnl']
    )

# При критической ошибке
if telegram:
    telegram.notify_critical_error(
        error_type='futures_opened_spot_failed',
        message=f"Спот ошибка: {spot_result['error']}",
        crypto=crypto,
        qty=futures_result['qty']
    )
```

#### Конфигурация Telegram (telegram_bot/config.py)

```python
class TelegramConfig:
    # Токен бота (получить у @BotFather)
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7534003941:AAEib...')

    # Admin chat IDs (для получения уведомлений)
    ADMIN_CHAT_IDS = [
        # 123456789,  # Твой chat_id (получить через /start)
    ]

    # Настройки
    MESSAGE_TIMEOUT = 30  # Таймаут отправки сообщений
    ENABLE_NOTIFICATIONS = True  # Включить уведомления
    NOTIFICATION_COOLDOWN = 5  # Минимальный интервал между уведомлениями (сек)
```

**Как получить chat_id:**
1. Создать бота через @BotFather → получить токен
2. Запустить бота: `python main.py`
3. Написать `/start` в Telegram
4. В логах увидеть: `[TELEGRAM] Пользователь 123456789 (@username) отправил /start`
5. Добавить `123456789` в `ADMIN_CHAT_IDS`
6. Перезапустить бота

#### Интеграция с Orchestrator

```python
# orchestrator.py
from integration.telegram_integration import TelegramIntegration

class MultiCryptoOrchestrator:
    def __init__(self):
        # ... инициализация репозиториев и менеджеров ...

        # Инициализация Telegram интеграции
        self.telegram = TelegramIntegration(
            position_repo=self.position_repo,
            history_repo=self.history_repo,
            blacklist_repo=self.blacklist_repo
        )
        logger.info("✅ Telegram интеграция инициализирована")

    def run(self):
        try:
            # Запуск Telegram бота
            if self.telegram.start_bot():
                logger.info("✅ Telegram бот запущен")
            else:
                logger.warning("⚠️ Telegram бот не запущен")

            # ... основной цикл торговли ...

        finally:
            # Остановка Telegram бота при завершении
            self.telegram.stop_bot()
```

#### Отключение шумных логов

**В utils/logger_config.py:**
```python
def setup_logging():
    # ... основная настройка ...

    # Отключаем шумные HTTP логи от Telegram
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('telegram.ext').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    return logger
```

Это предотвращает спам в логах вида:
```
INFO - HTTP Request: POST https://api.telegram.org/bot.../sendMessage "HTTP/1.1 200 OK"
INFO - HTTP Request: POST https://api.telegram.org/bot.../getUpdates "HTTP/1.1 200 OK"
```

### 3. MultiCryptoOrchestrator (orchestrator.py)

**Главный координатор с Dependency Injection**

#### Инициализация
```python
def __init__(self):
    # Проверка подключения к БД
    if not check_db_connection():
        raise RuntimeError("Database connection failed")

    # Создание репозиториев
    self.position_repo = PositionRepository()
    self.history_repo = HistoryRepository()
    self.blacklist_repo = BlacklistRepository()

    # Dependency Injection в менеджеры
    self.position_manager = MultiPositionManager(
        position_repo=self.position_repo,
        history_repo=self.history_repo
    )

    self.blacklist_manager = BlacklistManager(
        blacklist_repo=self.blacklist_repo
    )

    # Telegram интеграция
    self.telegram = TelegramIntegration(
        position_repo=self.position_repo,
        history_repo=self.history_repo,
        blacklist_repo=self.blacklist_repo
    )
```

#### Сканирование рынка (`scan_opportunities`)
- Получает список всех торговых пар с Bybit
- Фильтрует blacklist криптовалюты (через БД)
- Анализирует спреды через `SpreadAnalyzer`
- Получает funding rates
- Находит топ-N прибыльных возможностей
- Запускает потоки открытия позиций

#### Мониторинг позиций (`monitor_position`)
- Каждая открытая позиция мониторится в отдельном daemon-потоке
- Проверяет условия закрытия каждые 300 секунд
- Поддерживает 2 режима закрытия:
  - **Обычный**: FR < -0.001% И спред <= 0.15%
  - **Мягкий**: FR <= 0.005% И спред <= 0.15% (после 15+ раундов с низким FR)

### 4. OpportunityMonitor (opportunity_monitor.py)

**Логика торговли**: открытие и закрытие позиций

#### Открытие позиции (`monitor_and_execute`)
```
Условия входа:
1. spread_pct >= 0.45%   (MIN_ENTRY_SPREAD_PCT)
2. funding_rate >= 0.02% (MIN_FUNDING_RATE)

Порядок исполнения:
1️⃣ Установка плеча (LEVERAGE = 1)
2️⃣ Открытие ФЬЮЧЕРСА (SHORT)  ← СНАЧАЛА!
3️⃣ Открытие СПОТА (LONG)
   ⚠️ Если спот не открылся → КРИТИЧЕСКАЯ СИТУАЦИЯ → Telegram уведомление
4️⃣ Сохранение в БД через position_manager.save_position()
5️⃣ Telegram уведомление об успешном открытии
```

#### Закрытие позиции (`monitor_open_position_single`)
```
Обычный режим:
- FR < -0.001% (CLOSE_FR_THRESHOLD)
- Спред закрытия <= 0.15% (MAX_CLOSE_SPREAD_PCT)

Мягкий режим (после 15+ раундов с FR <= 0.005%):
- FR <= 0.005% (LOW_FR_TRACKING_THRESHOLD)
- Спред закрытия <= 0.15%

Порядок закрытия:
1️⃣ Продажа СПОТА (по актуальному балансу)
2️⃣ Покупка ФЬЮЧЕРСА (по сохраненному qty)
3️⃣ Сохранение в историю через history_repo.save_closed_position()
4️⃣ Telegram уведомление о закрытии с PnL
```

### 5. MultiPositionManager (position_manager.py)

**Управление множественными позициями через репозитории**

#### Dependency Injection
```python
def __init__(
    self,
    position_repo: Optional[PositionRepository] = None,
    history_repo: Optional[HistoryRepository] = None
):
    self.position_repo = position_repo or PositionRepository()
    self.history_repo = history_repo or HistoryRepository()
    # ...
```

#### Ключевые методы
- `save_position()` - сохранение позиции через репозиторий
- `get_position(crypto)` - получение данных позиции (dict для совместимости)
- `has_position(crypto)` - проверка существования
- `increment_funding_count()` - отслеживание funding rate для мягкого режима
- `close_position_with_pnl()` - закрытие с расчетом PnL и сохранение в историю
- `get_all_positions()` - все открытые позиции (Dict[str, dict])
- `get_open_cryptos()` - список символов с открытыми позициями

#### Thread Safety
- Используется `threading.RLock` (реентерабельный lock)
- Все операции атомарны
- Безопасная работа из множественных потоков

### 6. BlacklistManager (blacklist_manager.py)

**Singleton-менеджер с кешированием в памяти**

#### Dependency Injection + Caching
```python
def __init__(self, blacklist_repo: Optional[BlacklistRepository] = None):
    self.blacklist_repo = blacklist_repo or BlacklistRepository()

    # Кеш для быстрого доступа
    self.blacklist: Set[str] = set()
    self.blacklist_details = {}

    # Загрузка из БД в кеш
    self._load_blacklist()
```

#### Критические коды ошибок (автоматическое добавление в blacklist)
```python
CRITICAL_ERROR_CODES = [
    30228,  # No new positions during delisting
    10001,  # Symbol not found
    110043, # Set margin mode failed (suspended trading)
]
```

#### Ключевые методы
- `add_to_blacklist()` - добавление в БД + обновление кеша + Telegram уведомление
- `is_blacklisted()` - быстрая проверка через кеш
- `remove_from_blacklist()` - удаление из БД + обновление кеша
- `get_blacklist()` - копия списка
- `refresh_cache()` - принудительное обновление кеша из БД

### 7. OrderExecutor (order_executor.py)

**Исполнение ордеров с точностью инструмента**

#### Ключевые функции
- `get_instrument_info()` - получение `qtyStep`, `basePrecision`, `minOrderQty`
- `round_to_step()` - округление qty с использованием Decimal (ROUND_DOWN)
- `place_spot_order()` - Market ордер на спот (в USDT, `marketUnit: quoteCoin`)
- `place_futures_order()` - Market ордер на фьючерс (в qty монеты)
- `close_spot_position_qty()` - закрытие спота (по актуальному балансу)
- `close_futures_position()` - закрытие фьючерса (reduceOnly=True)

### 8. PnLCalculator (pnl_calculator.py)

**Расчет прибыли/убытка при закрытии позиции**

#### Формула
```
Spot PnL = (exit_price - entry_price) * spot_qty
Futures PnL = (entry_price - exit_price) * futures_qty
Price PnL = Spot PnL + Futures PnL
Commission = (entry_value + exit_value) * commission_rate
Net PnL = Price PnL + Funding - Commission
```

### 9. RealizedFundingCalculator (funding_calculator.py)

**Расчет РЕАЛЬНОГО полученного фандинга через Bybit API**

#### Метод
- Запрашивает `/execution/list` с `execType: "Funding"`
- Разбивает период на интервалы по 7 дней (API ограничение)
- Суммирует все `execFee` (с инвертированием знака)
- Положительное число = прибыль от фандинга

### 10. Rate Limiter (rate_limiter.py)

**Token Bucket алгоритм для защиты от rate limit**

#### Лимиты Bybit
```python
MAX_REQUESTS_PER_SECOND = 50  # (Bybit: 120)
MAX_WEIGHT_PER_SECOND = 300   # (Bybit: 600)
```

## Конфигурация (config.py)

### Торговые параметры
```python
TRADE_AMOUNT_USD = 30.0      # Размер позиции в USDT
LEVERAGE = 1                 # Без плеча (хедж)
COMMISSION_PCT = 0.27        # Суммарная комиссия (открытие + закрытие)
```

### Пороги входа
```python
MIN_SPREAD_PCT = 0.0         # Фильтр для отображения
MIN_ENTRY_SPREAD_PCT = 0.45  # Порог для открытия позиции
MIN_FUNDING_RATE = 0.02      # Минимальный FR для входа (0.02% = 2 basis points)
```

### Пороги выхода
```python
CLOSE_FR_THRESHOLD = -0.001      # Обычный режим
LOW_FR_TRACKING_THRESHOLD = 0.01 # Мягкий режим
MIN_FUNDING_PAYMENTS_FOR_CLOSE = 15  # Раундов с низким FR для активации мягкого режима
MAX_CLOSE_SPREAD_PCT = 0.15      # Максимальный спред для закрытия
```

### Многопоточность
```python
MAX_CONCURRENT_POSITIONS = 1  # Одновременных позиций
MAX_TRADING_THREADS = 3       # Потоков для открытия
SCAN_INTERVAL_SEC = 180       # Интервал сканирования рынка
MONITOR_INTERVAL_SEC = 300    # Интервал проверки позиций
```

### База данных
```python
DATABASE_URL = "sqlite:///./arbitrage.db"  # SQLite файл
```

### Telegram Bot (telegram_bot/config.py)
```python
BOT_TOKEN = "7534003941:AAEib2A0V-aY1ohtj7yam5Wm6_7U1hU5HAA"
ADMIN_CHAT_IDS = []  # Добавить свой chat_id после /start
ENABLE_NOTIFICATIONS = True
MESSAGE_TIMEOUT = 30
```

## Deployment

### Требования
```
Python 3.9+
sqlalchemy>=2.0.0
alembic>=1.13.0
requests
python-telegram-bot==20.7
```

### Установка
```bash
pip install sqlalchemy alembic requests python-telegram-bot==20.7
```

### Переменные окружения (.env)
```env
# Bybit API
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret

# Telegram Bot
TELEGRAM_BOT_TOKEN=7534003941:AAEib2A0V-aY1ohtj7yam5Wm6_7U1hU5HAA

# База данных (опционально)
DATABASE_URL=sqlite:///./arbitrage.db

# Опционально (для VPS с неточным временем)
USE_SERVER_TIME=true
```

### Инициализация БД
```bash
# Применить все миграции
alembic upgrade head

# Миграция blacklist.json → БД (если есть старые данные)
python scripts/migrate_blacklist_to_db.py
```

### Настройка Telegram бота

#### 1. Создание бота
1. Написать @BotFather в Telegram
2. Отправить `/newbot`
3. Указать имя бота
4. Скопировать токен

#### 2. Получение chat_id
1. Запустить бота: `python main.py`
2. Написать `/start` своему боту в Telegram
3. В логах увидеть:
   ```
   [TELEGRAM] Пользователь 123456789 (@username) отправил /start
   ```
4. Открыть `telegram_bot/config.py`
5. Добавить свой chat_id:
   ```python
   ADMIN_CHAT_IDS = [123456789]
   ```
6. Перезапустить бота

#### 3. Проверка работы
```
/start    - Приветствие + список команд
/status   - Статус системы
/positions - Открытые позиции
/stats    - Статистика торговли
```

### Запуск
```bash
python main.py
```

**Ожидаемые логи:**
```
2026-01-05 17:00:00 - INFO - 🔧 Инициализация оркестратора...
2026-01-05 17:00:00 - INFO - ✅ Подключение к БД успешно
2026-01-05 17:00:00 - INFO - ✅ Telegram интеграция инициализирована
2026-01-05 17:00:00 - INFO - ✅ Telegram бот запущен
2026-01-05 17:00:00 - INFO - 🚀 Запуск Telegram Bot polling...
2026-01-05 17:00:01 - INFO - ✅ Telegram Bot polling запущен
```

### Мониторинг (tmux)
```bash
# Создать сессию
tmux new -s arbitrage

# Запустить бота
python main.py

# Отсоединиться: Ctrl+B, затем D
# Присоединиться обратно: tmux attach -t arbitrage
```

## Логирование

### Структура логов
```
[2026-01-05 17:00:00] [INFO] 🔧 Инициализация оркестратора...
[2026-01-05 17:00:00] [INFO] ✅ Telegram интеграция активна
[2026-01-05 17:00:01] [INFO] [BTC] 🔍 Мониторинг закрытия...
[2026-01-05 17:00:01] [INFO] [BTC] └─ FR 0.0150% >= -0.001%, ждем снижения FR
[2026-01-05 17:05:00] [INFO] [BTC] 🔥 Условия закрытия выполнены
[2026-01-05 17:05:01] [INFO] [BTC] ✅ Позиция успешно закрыта
[2026-01-05 17:05:02] [INFO] 💰 NET PnL: +0.45 USDT ✅
```

### Уровни
- `DEBUG`: Детальная информация (API запросы, SQL queries)
- `INFO`: Основные события (открытие/закрытие, Telegram уведомления)
- `WARNING`: Предупреждения (timeout, blacklist)
- `ERROR`: Ошибки (API failures, БД проблемы)
- `CRITICAL`: Критические ситуации (фьючерс открыт, спот не открыт)

### Отключение шумных логов
В `utils/logger_config.py`:
```python
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
```

## Roadmap & Known Issues

### Completed ✅
- [x] База данных вместо JSON (SQLite + SQLAlchemy)
- [x] Repository Pattern для доступа к данным
- [x] Alembic для управления миграциями
- [x] Dependency Injection в менеджеры
- [x] Скрипт миграции blacklist.json → БД
- [x] Telegram бот для уведомлений и управления
- [x] Real-time notifications о торговых событиях
- [x] Command handlers (/start, /status, /positions, /stats)
- [x] Критические уведомления (фьючерс открыт, спот не открылся)

### TODO
- [ ] Web dashboard для мониторинга (FastAPI + React)
- [ ] Unit-тесты (pytest) с mock репозиториями
- [ ] Backtesting на исторических данных
- [ ] Поддержка других бирж (Binance, OKX)
- [ ] PostgreSQL support для production
- [ ] Telegram команды для управления (/close, /blacklist add/remove)
- [ ] Графики PnL в Telegram

### Известные ограничения
- Максимум 1 одновременная позиция (можно увеличить в config)
- Bybit rate limits: 120 req/sec, 600 weight/sec (используем 50 и 300)
- Funding rate обновляется каждые 8 часов (00:00, 08:00, 16:00 UTC)
- SQLite не подходит для очень высокой нагрузки (миграция на PostgreSQL)
- Telegram бот работает в daemon thread (завершается при остановке основного процесса)

## FAQ

### Почему сначала открывается фьючерс, а не спот?

Фьючерс критичнее для арбитража:
- Если спот не купится, можно закрыть фьючерс без убытка
- Если фьючерс не откроется после покупки спота, будем держать спот с риском движения цены
- При ошибке спота после открытия фьючерса → критическое Telegram уведомление

### Как изменить размер позиции?

```python
# config.py
TRADE_AMOUNT_USD = 50.0  # Было 30.0
```

### Как увеличить количество одновременных позиций?

```python
# config.py
MAX_CONCURRENT_POSITIONS = 3  # Было 1
```

⚠️ **Внимание**: требуется больше баланса USDT и мониторинг rate limits!

### Что делать если бот упал?

1. Перезапустить бота: `python main.py`
2. Он автоматически восстановит мониторинг открытых позиций из БД
3. Проверить логи на ошибки
4. Проверить Telegram - придет уведомление о восстановлении

### Почему не приходят Telegram уведомления?

1. Проверить что бот запущен (логи: "✅ Telegram Bot polling запущен")
2. Проверить что добавлен chat_id в `ADMIN_CHAT_IDS`:
   - Написать `/start` боту
   - В логах найти свой chat_id
   - Добавить в `telegram_bot/config.py`
   - Перезапустить бота
3. Проверить что `ENABLE_NOTIFICATIONS = True` в config
4. Проверить что токен бота правильный в `.env`

### Как отключить Telegram уведомления?

```python
# telegram_bot/config.py
ENABLE_NOTIFICATIONS = False
```

Команды бота (/start, /status, /positions, /stats) продолжат работать.

### Как добавить нескольких администраторов?

```python
# telegram_bot/config.py
ADMIN_CHAT_IDS = [
    123456789,   # Админ 1
    987654321,   # Админ 2
    555777999,   # Админ 3
]
```

Все указанные пользователи будут получать уведомления.

### Как перенести данные на другой сервер?

```bash
# Скопировать файлы:
scp arbitrage.db user@server:/path/to/project/
scp -r migrations/ user@server:/path/to/project/
scp .env user@server:/path/to/project/

# На новом сервере:
pip install -r requirements.txt
alembic upgrade head
python main.py
```

---

**Версия документации**: 5.0 (Telegram Edition)  
**Дата обновления**: Январь 2026  
**Автор проекта**: Александр  
**Exchange**: Bybit  
**Strategy**: Spot-Futures Arbitrage (Cash & Carry)  
**Storage**: SQLite (SQLAlchemy ORM) + Alembic Migrations  
**Notifications**: Telegram Bot (python-telegram-bot v20+)
