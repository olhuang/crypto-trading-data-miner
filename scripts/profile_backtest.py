import cProfile
import pstats
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from models.backtest import BacktestRunConfig, StrategySessionConfig
from models.market import BarEvent
from backtest.runner import BacktestRunnerSkeleton
from strategy import StrategyRegistry, build_default_registry
from strategy.examples import MovingAverageCrossStrategy
from storage.repositories.strategy import StrategySignalRepository
from backtest.fills import DeterministicBarsFillModel, StaticFeeModel

def synth_bars(count=100000):
    bars = []
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        bars.append(BarEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            bar_interval="1m",
            bar_time=base_time + timedelta(minutes=i),
            event_time=base_time + timedelta(minutes=i),
            ingest_time=base_time + timedelta(minutes=i),
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal(50000 + (i % 100)),
            volume=Decimal("100"),
        ))
    return bars

def run_prof():
    session = StrategySessionConfig(
        session_code="test_prof",
        environment="backtest",
        account_code="test_account",
        exchange_code="binance",
        strategy_code="btc_momentum",
        strategy_version="v1.0.0",
        universe=["BTCUSDT_PERP"]
    )
    # create 100k bars window (approx 70 days)
    config = BacktestRunConfig(
        run_name="prof_run",
        session=session,
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=100000),
        initial_cash=Decimal("10000"),
        strategy_params_json={"short_window": 10, "long_window": 30, "target_qty": "0.1"}
    )
    
    registry = build_default_registry()
    
    runner = BacktestRunnerSkeleton(
        run_config=config,
        registry=registry,
        signal_repository=StrategySignalRepository(),
        fill_model=DeterministicBarsFillModel(fee_model=StaticFeeModel()),
    )
    
    print("Generating synthetic bars...")
    bars = synth_bars(100000)
    
    print(f"Starting runner.run_bars ({len(bars)} bars)")
    t0 = time.time()
    res = runner.run_bars(bars, capture_steps=False, capture_debug_traces=False)
    t1 = time.time()
    
    print(f"Done in {t1 - t0:.2f} seconds.")
    print(f"Total steps: {len(res.steps)}")
    print(f"Total fills: {len(res.fills)}")
    print(f"Total performance points: {len(res.performance_points)}")

if __name__ == "__main__":
    cProfile.run("run_prof()", "tmp/perf.prof")
    p = pstats.Stats("tmp/perf.prof")
    p.sort_stats("tottime").print_stats(30)
