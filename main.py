# -*- coding: utf-8 -*-

from orchestrator import MultiCryptoOrchestrator
from utils.logger_config import setup_logging

if __name__ == "__main__":
    setup_logging()
    bot = MultiCryptoOrchestrator()  # ← Изменено
    bot.run()