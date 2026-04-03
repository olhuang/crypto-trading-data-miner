from __future__ import annotations

from sqlalchemy.engine import Connection

from models.backtest import BacktestRunConfig
from models.market import BarEvent
from storage.repositories.market_data import BarRepository


class BacktestBarLoader:
    def __init__(self, bar_repository: BarRepository | None = None) -> None:
        self.bar_repository = bar_repository or BarRepository()

    def load_bars(self, connection: Connection, run_config: BacktestRunConfig) -> list[BarEvent]:
        bars: list[BarEvent] = []
        for unified_symbol in run_config.session.universe:
            bars.extend(
                self.bar_repository.list_window(
                    connection,
                    exchange_code=run_config.session.exchange_code,
                    unified_symbol=unified_symbol,
                    start_time=run_config.start_time,
                    end_time=run_config.end_time,
                )
            )
        bars.sort(key=lambda bar: (bar.bar_time, bar.unified_symbol))
        return bars
