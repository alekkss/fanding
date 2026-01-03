# -*- coding: utf-8 -*-

from orchestrator import MultiCryptoOrchestrator
from utils.logger_config import setup_logger

if __name__ == "__main__":
    setup_logger()
    bot = MultiCryptoOrchestrator()  # ← Изменено
    bot.run()