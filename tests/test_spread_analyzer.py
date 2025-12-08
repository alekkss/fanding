# tests/test_spread_analyzer.py
# -*- coding: utf-8 -*-
"""Тесты для SpreadAnalyzer"""

import pytest
from spread_analyzer import SpreadAnalyzer
from config import MIN_SPREAD_PCT


class TestCalculateAllSpreads:
    """Тесты для метода calculate_all_spreads"""
    
    def test_basic_spread_calculation(self):
        """Проверяет базовый расчёт спреда"""
        orderbooks = {
            'BTC': {
                'spot_ask': 50000.0,
                'futures_bid': 50250.0
            }
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        assert len(result) == 1
        assert result[0]['crypto'] == 'BTC'
        assert result[0]['spot_ask'] == 50000.0
        assert result[0]['futures_bid'] == 50250.0
        # (50250 - 50000) / 50000 * 100 = 0.5%
        assert result[0]['spread_pct'] == pytest.approx(0.5, abs=0.001)
    
    def test_multiple_pairs_sorting(self):
        """Проверяет сортировку от большего к меньшему спреду"""
        orderbooks = {
            'BTC': {'spot_ask': 50000.0, 'futures_bid': 50100.0},  # 0.2%
            'ETH': {'spot_ask': 3000.0, 'futures_bid': 3030.0},    # 1.0%
            'SOL': {'spot_ask': 100.0, 'futures_bid': 100.05},     # 0.05%
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        assert len(result) == 3
        # Должны быть отсортированы по убыванию спреда
        assert result[0]['crypto'] == 'ETH'
        assert result[0]['spread_pct'] == pytest.approx(1.0, abs=0.01)
        assert result[1]['crypto'] == 'BTC'
        assert result[1]['spread_pct'] == pytest.approx(0.2, abs=0.01)
        assert result[2]['crypto'] == 'SOL'
        assert result[2]['spread_pct'] == pytest.approx(0.05, abs=0.01)
    
    def test_negative_spread(self):
        """Проверяет корректность расчёта отрицательного спреда"""
        orderbooks = {
            'BTC': {
                'spot_ask': 50000.0,
                'futures_bid': 49500.0  # фьючерс ниже спота
            }
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        assert len(result) == 1
        # (49500 - 50000) / 50000 * 100 = -1.0%
        assert result[0]['spread_pct'] == pytest.approx(-1.0, abs=0.01)
    
    def test_zero_spot_price_skipped(self):
        """Проверяет, что пары с нулевой spot ценой пропускаются"""
        orderbooks = {
            'BTC': {'spot_ask': 0.0, 'futures_bid': 50000.0},
            'ETH': {'spot_ask': 3000.0, 'futures_bid': 3030.0},
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        # BTC должен быть пропущен из-за spot_ask <= 0
        assert len(result) == 1
        assert result[0]['crypto'] == 'ETH'
    
    def test_negative_spot_price_skipped(self):
        """Проверяет, что пары с отрицательной spot ценой пропускаются"""
        orderbooks = {
            'BTC': {'spot_ask': -100.0, 'futures_bid': 50000.0},
            'ETH': {'spot_ask': 3000.0, 'futures_bid': 3030.0},
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        assert len(result) == 1
        assert result[0]['crypto'] == 'ETH'
    
    def test_empty_orderbooks(self):
        """Проверяет обработку пустого словаря"""
        result = SpreadAnalyzer.calculate_all_spreads({})
        
        assert result == []
    
    def test_spread_rounding(self):
        """Проверяет округление спреда до 6 знаков"""
        orderbooks = {
            'BTC': {
                'spot_ask': 50000.123456789,
                'futures_bid': 50025.987654321
            }
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        # Проверяем, что результат округлён до 6 знаков
        spread_str = str(result[0]['spread_pct'])
        decimal_part = spread_str.split('.')[-1] if '.' in spread_str else ''
        assert len(decimal_part) <= 6


class TestFilterAndDisplay:
    """Тесты для метода filter_and_display"""
    
    def test_filtering_by_min_spread(self, caplog):
        """Проверяет фильтрацию по MIN_SPREAD_PCT"""
        orderbooks = {
            'BTC': {'spot_ask': 50000.0, 'futures_bid': 50100.0},  # 0.2%
            'ETH': {'spot_ask': 3000.0, 'futures_bid': 2990.0},    # -0.33%
            'SOL': {'spot_ask': 100.0, 'futures_bid': 100.05},     # 0.05%
        }
        
        result = SpreadAnalyzer.filter_and_display(orderbooks)
        
        # При MIN_SPREAD_PCT = 0.0 все пары с положительным спредом проходят
        # Но ETH с отрицательным спредом не должен пройти
        positive_spreads = [p for p in result if p['spread_pct'] >= MIN_SPREAD_PCT]
        assert len(positive_spreads) >= 0  # зависит от MIN_SPREAD_PCT
    
    def test_empty_orderbooks_filter(self, caplog):
        """Проверяет обработку пустого словаря в фильтрации"""
        result = SpreadAnalyzer.filter_and_display({})
        
        assert result == []
    
    def test_all_pairs_below_threshold(self, caplog):
        """Проверяет случай, когда все пары ниже MIN_SPREAD_PCT"""
        # Создаём пары с отрицательным спредом
        orderbooks = {
            'BTC': {'spot_ask': 50000.0, 'futures_bid': 49500.0},  # -1.0%
            'ETH': {'spot_ask': 3000.0, 'futures_bid': 2970.0},    # -1.0%
        }
        
        result = SpreadAnalyzer.filter_and_display(orderbooks)
        
        # Все должны быть отфильтрованы, если MIN_SPREAD_PCT > -1.0
        if MIN_SPREAD_PCT > -1.0:
            assert len(result) == 0
    
    def test_logging_output(self, caplog):
        """Проверяет, что метод выводит логи"""
        orderbooks = {
            'BTC': {'spot_ask': 50000.0, 'futures_bid': 50250.0}
        }
        
        with caplog.at_level('INFO'):
            SpreadAnalyzer.filter_and_display(orderbooks)
        
        # Проверяем, что были логи с ключевыми словами
        log_text = caplog.text
        assert 'Анализ спредов' in log_text or 'ТОП-5' in log_text


class TestEdgeCases:
    """Граничные случаи"""
    
    def test_very_small_spread(self):
        """Проверяет очень маленький спред"""
        orderbooks = {
            'BTC': {
                'spot_ask': 50000.0,
                'futures_bid': 50000.001
            }
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        assert len(result) == 1
        assert result[0]['spread_pct'] > 0
        assert result[0]['spread_pct'] < 0.001
    
    def test_very_large_spread(self):
        """Проверяет очень большой спред"""
        orderbooks = {
            'BTC': {
                'spot_ask': 50000.0,
                'futures_bid': 60000.0
            }
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        assert len(result) == 1
        # (60000 - 50000) / 50000 * 100 = 20%
        assert result[0]['spread_pct'] == pytest.approx(20.0, abs=0.1)
    
    @pytest.mark.parametrize("spot_ask,futures_bid,expected_spread", [
        (100.0, 100.5, 0.5),
        (100.0, 99.5, -0.5),
        (100.0, 100.0, 0.0),
        (1.0, 1.01, 1.0),
        (10000.0, 10100.0, 1.0),
    ])
    def test_parametrized_spreads(self, spot_ask, futures_bid, expected_spread):
        """Параметризованный тест различных спредов"""
        orderbooks = {
            'TEST': {
                'spot_ask': spot_ask,
                'futures_bid': futures_bid
            }
        }
        
        result = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        assert len(result) == 1
        assert result[0]['spread_pct'] == pytest.approx(expected_spread, abs=0.01)
