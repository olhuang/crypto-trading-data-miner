from __future__ import annotations

from dataclasses import dataclass

from storage.repositories.backtest import BacktestRunRepository


@dataclass(slots=True)
class ArtifactReference:
    artifact_type: str
    status: str
    record_count: int | None = None
    description: str | None = None


@dataclass(slots=True)
class BacktestArtifactBundle:
    run_id: int
    artifacts: list[ArtifactReference]


class BacktestArtifactCatalogProjector:
    def __init__(self, run_repository: BacktestRunRepository | None = None) -> None:
        self.run_repository = run_repository or BacktestRunRepository()

    def build(self, connection, *, run_id: int) -> BacktestArtifactBundle | None:
        run_row = self.run_repository.get_run(connection, run_id)
        if run_row is None:
            return None

        timeseries_records = self.run_repository.list_timeseries(connection, run_id=run_id)
        fill_records = self.run_repository.list_fill_records(connection, run_id=run_id)
        signal_records = self.run_repository.list_signal_records(connection, run_id=run_id)

        artifacts = [
            ArtifactReference(
                artifact_type="run_metadata",
                status="available",
                record_count=1,
                description="canonical persisted run metadata and lineage baseline",
            ),
            ArtifactReference(
                artifact_type="signals",
                status="available" if signal_records else "empty",
                record_count=len(signal_records),
                description="persisted canonical strategy signals linked to this run",
            ),
            ArtifactReference(
                artifact_type="simulated_fills",
                status="available" if fill_records else "empty",
                record_count=len(fill_records),
                description="simulated fills produced by the deterministic bars-based execution model",
            ),
            ArtifactReference(
                artifact_type="performance_timeseries",
                status="available" if timeseries_records else "empty",
                record_count=len(timeseries_records),
                description="equity, cash, exposure, and drawdown timeseries",
            ),
            ArtifactReference(
                artifact_type="diagnostics_summary",
                status="available",
                record_count=1,
                description="Stage A run-level diagnostics summary",
            ),
            ArtifactReference(
                artifact_type="period_breakdown",
                status="available",
                record_count=3,
                description="derived year/quarter/month performance breakdown projections",
            ),
        ]
        return BacktestArtifactBundle(run_id=run_id, artifacts=artifacts)
