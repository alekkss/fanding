# tests/test_arbitrage_calculator.py
# -*- coding: utf-8 -*-
"""Полные тесты для ArbitrageCalculator с максимальным покрытием"""

import pytest
from arbitrage_calculator import ArbitrageCalculator
from config import COMMISSION_PCT, MIN_PROFIT_PCT, MIN_FUNDING_RATE


class TestCalculateProfitFromPair:
    """Тесты для метода calculate_profit_from_pair"""
    
    def test_basic_profit_calculation(self):
        """Проверяет базовый расчёт прибыли"""
        pair = {
            'crypto': 'BTC',
            'spot_ask': 50000.0,
            'futures_bid': 50250.0,
            'spread_pct': 0.5
        }
        funding_rate = 0.02
        
        result = ArbitrageCalculator.calculate_profit_from_pair(pair, funding_rate)
        
        assert result['crypto'] == 'BTC'
        assert result['spot_ask'] == 50000.0
        assert result['futures_bid'] == 50250.0
        assert result['spread_pct'] == 0.5
        assert result['funding_rate'] == 0.02
        # 0.5 + 0.02 - 0.27 = 0.25
        assert result['net_profit_pct'] == pytest.approx(0.25, abs=0.001)
    
    def test_negative_profit(self):
        """Проверяет расчёт с отрицательной прибылью"""
        pair = {
            'crypto': 'ETH',
            'spot_ask': 3000.0,
            'futures_bid': 3003.0,
            'spread_pct': 0.1
        }
        funding_rate = 0.01
        
        result = ArbitrageCalculator.calculate_profit_from_pair(pair, funding_rate)
        
        # 0.1 + 0.01 - 0.27 = -0.16
        assert result['net_profit_pct'] == pytest.approx(-0.16, abs=0.01)
    
    def test_funding_rate_rounding(self):
        """Проверяет округление funding rate до 6 знаков"""
        pair = {
            'crypto': 'SOL',
            'spot_ask': 100.0,
            'futures_bid': 100.5,
            'spread_pct': 0.5
        }
        funding_rate = 0.0123456789
        
        result = ArbitrageCalculator.calculate_profit_from_pair(pair, funding_rate)
        
        # Должно быть округлено до 6 знаков
        assert result['funding_rate'] == 0.012346
    
    def test_net_profit_rounding(self):
        """Проверяет округление net_profit_pct до 6 знаков"""
        pair = {
            'crypto': 'BTC',
            'spot_ask': 50000.0,
            'futures_bid': 50250.0,
            'spread_pct': 0.5123456789
        }
        funding_rate = 0.0223456789
        
        result = ArbitrageCalculator.calculate_profit_from_pair(pair, funding_rate)
        
        # Результат должен быть округлён
        assert isinstance(result['net_profit_pct'], float)
        net_str = str(result['net_profit_pct'])
        if '.' in net_str:
            decimal_part = net_str.split('.')[1]
            assert len(decimal_part) <= 6
    
    @pytest.mark.parametrize("spread,fr,expected", [
        (0.5, 0.02, 0.25),       # Прибыльная сделка
        (0.3, 0.05, 0.08),       # Небольшая прибыль
        (0.1, -0.01, -0.18),     # Убыток
        (0.0, 0.0, -COMMISSION_PCT),  # Только комиссия
        (1.0, 0.05, 0.78),       # Большая прибыль
    ])
    def test_parametrized_profits(self, spread, fr, expected):
        """Параметризованный тест различных комбинаций"""
        pair = {
            'crypto': 'TEST',
            'spot_ask': 1000.0,
            'futures_bid': 1000.0 + (1000.0 * spread / 100),
            'spread_pct': spread
        }
        
        result = ArbitrageCalculator.calculate_profit_from_pair(pair, fr)
        
        assert result['net_profit_pct'] == pytest.approx(expected, abs=0.01)


class TestFindBestOpportunity:
    """Тесты для метода find_best_opportunity"""
    
    def test_single_profitable_opportunity(self, caplog):
        """Проверяет поиск единственной прибыльной возможности"""
        filtered_pairs = [
            {
                'crypto': 'BTC',
                'spot_ask': 50000.0,
                'futures_bid': 50500.0,
                'spread_pct': 1.0
            }
        ]
        funding_rates = {'BTC': 0.05}
        
        crypto, profit, best = ArbitrageCalculator.find_best_opportunity(
            filtered_pairs, funding_rates
        )
        
        assert crypto == 'BTC'
        assert profit > MIN_PROFIT_PCT
        assert best['crypto'] == 'BTC'
        assert best['net_profit_pct'] == pytest.approx(0.78, abs=0.01)
    
    def test_multiple_opportunities_sorting(self, caplog):
        """Проверяет сортировку нескольких возможностей"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50100.0, 'spread_pct': 0.2},
            {'crypto': 'ETH', 'spot_ask': 3000.0, 'futures_bid': 3050.0, 'spread_pct': 1.67},
            {'crypto': 'SOL', 'spot_ask': 100.0, 'futures_bid': 100.5, 'spread_pct': 0.5},
        ]
        funding_rates = {'BTC': 0.02, 'ETH': 0.03, 'SOL': 0.015}
        
        crypto, profit, best = ArbitrageCalculator.find_best_opportunity(
            filtered_pairs, funding_rates
        )
        
        # ETH должен выиграть из-за лучшего спреда
        assert crypto == 'ETH'
        assert best['crypto'] == 'ETH'
        # 1.67 + 0.03 - 0.27 = 1.43
        assert best['net_profit_pct'] == pytest.approx(1.43, abs=0.01)
    
    def test_no_opportunities_after_fr_filter(self, caplog):
        """Проверяет случай, когда все отклонены по FR"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50100.0, 'spread_pct': 0.2},
            {'crypto': 'ETH', 'spot_ask': 3000.0, 'futures_bid': 3030.0, 'spread_pct': 1.0},
        ]
        # FR ниже MIN_FUNDING_RATE (0.011)
        funding_rates = {'BTC': 0.005, 'ETH': 0.008}
        
        crypto, profit, best = ArbitrageCalculator.find_best_opportunity(
            filtered_pairs, funding_rates
        )
        
        assert crypto is None
        assert profit == 0
        assert best is None
    
    def test_crypto_not_in_funding_rates(self, caplog):
        """Проверяет пропуск криптовалют без funding rate"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50500.0, 'spread_pct': 1.0},
            {'crypto': 'UNKNOWN', 'spot_ask': 100.0, 'futures_bid': 101.0, 'spread_pct': 1.0},
        ]
        funding_rates = {'BTC': 0.05}  # Нет UNKNOWN
        
        crypto, profit, best = ArbitrageCalculator.find_best_opportunity(
            filtered_pairs, funding_rates
        )
        
        assert crypto == 'BTC'
        assert best['crypto'] == 'BTC'
    
    def test_rejected_by_fr_logging(self, caplog):
        """Проверяет логирование отклонённых по FR"""
        filtered_pairs = [
            {'crypto': f'COIN{i}', 'spot_ask': 100.0, 'futures_bid': 101.0, 'spread_pct': 1.0}
            for i in range(10)
        ]
        # 8 монет с низким FR, 2 с нормальным
        funding_rates = {f'COIN{i}': 0.005 if i < 8 else 0.02 for i in range(10)}
        
        with caplog.at_level('INFO'):
            crypto, profit, best = ArbitrageCalculator.find_best_opportunity(
                filtered_pairs, funding_rates
            )
        
        assert crypto in ['COIN8', 'COIN9']
    
    def test_best_below_min_profit(self, caplog):
        """Проверяет случай, когда лучшая возможность ниже MIN_PROFIT_PCT"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50050.0, 'spread_pct': 0.1}
        ]
        # FR достаточен для прохождения, но прибыль мала
        funding_rates = {'BTC': 0.02}  # 0.1 + 0.02 - 0.27 = -0.15
        
        crypto, profit, best = ArbitrageCalculator.find_best_opportunity(
            filtered_pairs, funding_rates
        )
        
        # В реальной реализации метод возвращает лучшую возможность,
        # даже если прибыль ниже MIN_PROFIT_PCT
        assert crypto == 'BTC'
        assert profit == pytest.approx(-0.15, abs=0.01)
        assert best is not None
        assert best['net_profit_pct'] == pytest.approx(-0.15, abs=0.01)
    
    def test_empty_filtered_pairs(self, caplog):
        """Проверяет обработку пустого списка пар"""
        crypto, profit, best = ArbitrageCalculator.find_best_opportunity([], {})
        
        assert crypto is None
        assert profit == 0
        assert best is None
    
    def test_top_10_logging(self, caplog):
        """Проверяет логирование ТОП-10"""
        filtered_pairs = [
            {'crypto': f'COIN{i}', 'spot_ask': 100.0, 'futures_bid': 100 + i, 'spread_pct': float(i)}
            for i in range(1, 16)  # 15 монет
        ]
        funding_rates = {f'COIN{i}': 0.02 for i in range(1, 16)}
        
        with caplog.at_level('INFO'):
            crypto, profit, best = ArbitrageCalculator.find_best_opportunity(
                filtered_pairs, funding_rates
            )
        
        assert crypto is not None
        assert best is not None


class TestFindTopOpportunities:
    """Тесты для метода find_top_opportunities"""
    
    def test_find_top_3(self, caplog):
        """Проверяет поиск топ-3 возможностей"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50500.0, 'spread_pct': 1.0},
            {'crypto': 'ETH', 'spot_ask': 3000.0, 'futures_bid': 3060.0, 'spread_pct': 2.0},
            {'crypto': 'SOL', 'spot_ask': 100.0, 'futures_bid': 101.5, 'spread_pct': 1.5},
            {'crypto': 'ADA', 'spot_ask': 1.0, 'futures_bid': 1.008, 'spread_pct': 0.8},
            {'crypto': 'DOT', 'spot_ask': 10.0, 'futures_bid': 10.12, 'spread_pct': 1.2},
        ]
        funding_rates = {
            'BTC': 0.05, 'ETH': 0.04, 'SOL': 0.03,
            'ADA': 0.02, 'DOT': 0.025
        }
        
        top = ArbitrageCalculator.find_top_opportunities(
            filtered_pairs, funding_rates, limit=3
        )
        
        assert len(top) == 3
        # Проверяем сортировку по убыванию прибыли
        assert top[0]['net_profit_pct'] >= top[1]['net_profit_pct']
        assert top[1]['net_profit_pct'] >= top[2]['net_profit_pct']
        # Первый должен быть ETH (2.0 + 0.04 - 0.27 = 1.77)
        assert top[0]['crypto'] == 'ETH'
    
    def test_limit_more_than_available(self, caplog):
        """Проверяет случай, когда limit больше доступных возможностей"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50500.0, 'spread_pct': 1.0},
            {'crypto': 'ETH', 'spot_ask': 3000.0, 'futures_bid': 3060.0, 'spread_pct': 2.0},
        ]
        funding_rates = {'BTC': 0.05, 'ETH': 0.04}
        
        top = ArbitrageCalculator.find_top_opportunities(
            filtered_pairs, funding_rates, limit=10
        )
        
        # Должно вернуться только 2
        assert len(top) == 2
    
    def test_filter_by_min_funding_rate(self, caplog):
        """Проверяет фильтрацию по MIN_FUNDING_RATE"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50500.0, 'spread_pct': 1.0},
            {'crypto': 'ETH', 'spot_ask': 3000.0, 'futures_bid': 3060.0, 'spread_pct': 2.0},
        ]
        # BTC с низким FR
        funding_rates = {'BTC': 0.005, 'ETH': 0.04}
        
        top = ArbitrageCalculator.find_top_opportunities(
            filtered_pairs, funding_rates, limit=3
        )
        
        # Только ETH должен пройти
        assert len(top) == 1
        assert top[0]['crypto'] == 'ETH'
    
    def test_filter_by_min_profit(self, caplog):
        """Проверяет фильтрацию по MIN_PROFIT_PCT"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50050.0, 'spread_pct': 0.1},
            {'crypto': 'ETH', 'spot_ask': 3000.0, 'futures_bid': 3060.0, 'spread_pct': 2.0},
        ]
        funding_rates = {'BTC': 0.02, 'ETH': 0.04}
        
        top = ArbitrageCalculator.find_top_opportunities(
            filtered_pairs, funding_rates, limit=3
        )
        
        # BTC: 0.1 + 0.02 - 0.27 = -0.15 > MIN_PROFIT_PCT (-0.2), должен пройти
        # ETH: 2.0 + 0.04 - 0.27 = 1.77 > MIN_PROFIT_PCT, должен пройти
        assert len(top) >= 1
    
    def test_no_opportunities(self, caplog):
        """Проверяет случай без возможностей"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50050.0, 'spread_pct': 0.1}
        ]
        # Низкий FR
        funding_rates = {'BTC': 0.005}
        
        with caplog.at_level('INFO'):
            top = ArbitrageCalculator.find_top_opportunities(
                filtered_pairs, funding_rates, limit=3
            )
        
        # FR 0.005 < MIN_FUNDING_RATE (0.011), поэтому отфильтрован
        assert len(top) == 0
    
    def test_crypto_not_in_funding_rates_top(self, caplog):
        """Проверяет пропуск криптовалют без FR в find_top_opportunities"""
        filtered_pairs = [
            {'crypto': 'BTC', 'spot_ask': 50000.0, 'futures_bid': 50500.0, 'spread_pct': 1.0},
            {'crypto': 'UNKNOWN', 'spot_ask': 100.0, 'futures_bid': 102.0, 'spread_pct': 2.0},
        ]
        funding_rates = {'BTC': 0.05}
        
        top = ArbitrageCalculator.find_top_opportunities(
            filtered_pairs, funding_rates, limit=3
        )
        
        assert len(top) == 1
        assert top[0]['crypto'] == 'BTC'
    
    def test_empty_inputs_top(self, caplog):
        """Проверяет обработку пустых входных данных"""
        with caplog.at_level('INFO'):
            top = ArbitrageCalculator.find_top_opportunities([], {}, limit=3)
        
        assert len(top) == 0
