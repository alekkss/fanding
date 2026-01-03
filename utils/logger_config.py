# -*- coding: utf-8 -*-
"""Настройка логирования"""
import logging
import sys

TITLE = """
╔═════════════════════════════════════════════════════════════════╗
║      FUNDING RATE ARBITRAGE TRADER v2.0 + POSITION MANAGEMENT  ║
╚═════════════════════════════════════════════════════════════════╝
"""

class UTF8StreamHandler(logging.StreamHandler):
    """UTF-8 handler для корректного отображения в консоли Windows"""
    def __init__(self):
        super().__init__(sys.stdout)
        if sys.stdout.encoding != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')

def setup_logging():
    """Настраивает логирование"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('arbitrage_funding.log', encoding='utf-8'),
            UTF8StreamHandler()
        ]
    )
    print(TITLE)
    return logging.getLogger(__name__)
