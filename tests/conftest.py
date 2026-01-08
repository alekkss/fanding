# -*- coding: utf-8 -*-

"""
Общие fixtures для всех тестов.
Используется pytest для автоматического обнаружения.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any


@pytest.fixture
def mock_config():
    """Mock для config модуля."""
    with patch('orchestrator.MAX_CONCURRENT_POSITIONS', 1), \
         patch('orchestrator.MAX_TRADING_THREADS', 5), \
         patch('orchestrator.SCAN_INTERVAL_SEC', 180), \
         patch('orchestrator.MIN_SPREAD_PCT', 0.0):
        yield


@pytest.fixture
def mock_db_connection():
    """Mock для проверки подключения к БД."""
    with patch('orchestrator.check_db_connection', return_value=True) as mock:
        yield mock


@pytest.fixture
def mock_repositories():
    """Mock для всех репозиториев."""
    with patch('orchestrator.PositionRepository') as pos_repo, \
         patch('orchestrator.HistoryRepository') as hist_repo, \
         patch('orchestrator.BlacklistRepository') as black_repo:
        
        # Настройка моков репозиториев
        pos_repo_instance = Mock()
        hist_repo_instance = Mock()
        black_repo_instance = Mock()
        
        pos_repo.return_value = pos_repo_instance
        hist_repo.return_value = hist_repo_instance
        black_repo.return_value = black_repo_instance
        
        yield {
            'position': pos_repo_instance,
            'history': hist_repo_instance,
            'blacklist': black_repo_instance
        }


@pytest.fixture
def mock_managers():
    """Mock для менеджеров позиций и blacklist."""
    with patch('orchestrator.MultiPositionManager') as pos_mgr, \
         patch('orchestrator.BlacklistManager') as black_mgr:
        
        pos_mgr_instance = Mock()
        black_mgr_instance = Mock()
        
        # 🆕 Настройка default значений
        pos_mgr_instance.get_open_cryptos.return_value = []
        pos_mgr_instance.get_positions_count.return_value = 0
        pos_mgr_instance.has_position.return_value = False
        
        black_mgr_instance.get_blacklist.return_value = []  # 🆕 ДОБАВИТЬ
        black_mgr_instance.is_blacklisted.return_value = False
        
        pos_mgr.return_value = pos_mgr_instance
        black_mgr.return_value = black_mgr_instance
        
        yield {
            'position_manager': pos_mgr_instance,
            'blacklist_manager': black_mgr_instance
        }


@pytest.fixture
def mock_telegram():
    """Mock для Telegram интеграции."""
    with patch('orchestrator.initialize_telegram_integration') as mock:
        telegram_instance = Mock()
        telegram_instance.start.return_value = True
        telegram_instance.stop.return_value = None
        mock.return_value = telegram_instance
        yield telegram_instance


@pytest.fixture
def sample_position() -> Dict[str, Any]:
    """Пример данных позиции для тестов."""
    return {
        'crypto': 'BTC',
        'spot_entry_price': 50000.0,
        'futures_entry_price': 50100.0,
        'spot_qty': 0.1,
        'futures_qty': 0.1,
        'entry_spread_pct': 0.2,
        'total_entries': 1
    }


@pytest.fixture
def sample_opportunity() -> Dict[str, Any]:
    """Пример данных возможности арбитража."""
    return {
        'crypto': 'ETH',
        'spot_ask': 3000.0,
        'futures_bid': 3015.0,
        'spread_pct': 0.5,
        'funding_rate': 0.03,
        'net_profit': 0.25
    }
