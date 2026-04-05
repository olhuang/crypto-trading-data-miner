from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from ingestion.base import JsonHttpClient
from models.market import (
    BarEvent,
    FundingRateEvent,
    GlobalLongShortAccountRatioEvent,
    IndexPriceEvent,
    InstrumentMetadata,
    MarkPriceEvent,
    OpenInterestEvent,
    TakerLongShortRatioEvent,
    TopTraderLongShortAccountRatioEvent,
    TopTraderLongShortPositionRatioEvent,
)


SPOT_REST_BASE_URL = "https://api.binance.com"
FUTURES_REST_BASE_URL = "https://fapi.binance.com"


def _utc_from_millis(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "null"):
        return None
    return Decimal(str(value))


def _pair_from_symbol(symbol: str) -> str:
    return symbol


@dataclass(slots=True)
class InstrumentSyncSummary:
    instruments_seen: int
    inserted: int
    updated: int
    unchanged: int
    diffs: list[dict[str, Any]]


class BinancePublicRestClient:
    def __init__(
        self,
        http_client: JsonHttpClient | None = None,
        *,
        spot_base_url: str = SPOT_REST_BASE_URL,
        futures_base_url: str = FUTURES_REST_BASE_URL,
    ) -> None:
        self.http = http_client or JsonHttpClient()
        self.spot_base_url = spot_base_url.rstrip("/")
        self.futures_base_url = futures_base_url.rstrip("/")

    def fetch_spot_exchange_info(self) -> dict[str, Any]:
        return self.http.get_json(f"{self.spot_base_url}/api/v3/exchangeInfo")

    def fetch_futures_exchange_info(self) -> dict[str, Any]:
        return self.http.get_json(f"{self.futures_base_url}/fapi/v1/exchangeInfo")

    def fetch_klines(
        self,
        symbol: str,
        *,
        interval: str = "1m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
        market_type: str = "perp",
    ) -> list[list[Any]]:
        base_url = f"{self.spot_base_url}/api/v3/klines" if market_type == "spot" else f"{self.futures_base_url}/fapi/v1/klines"
        if start_time is None or end_time is None:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": int(start_time.timestamp() * 1000) if start_time else None,
                "endTime": int(end_time.timestamp() * 1000) if end_time else None,
                "limit": limit,
            }
            return list(self.http.get_json(base_url, params))

        rows: list[list[Any]] = []
        next_start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        while next_start_ms <= end_ms:
            page = list(
                self.http.get_json(
                    base_url,
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "startTime": next_start_ms,
                        "endTime": end_ms,
                        "limit": limit,
                    },
                )
            )
            if not page:
                break
            rows.extend(page)
            if len(page) < limit:
                break
            next_start_ms = int(page[-1][6]) + 1
        return rows

    def fetch_funding_rate_history(
        self,
        symbol: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        base_url = f"{self.futures_base_url}/fapi/v1/fundingRate"
        if start_time is None or end_time is None:
            params = {
                "symbol": symbol,
                "startTime": int(start_time.timestamp() * 1000) if start_time else None,
                "endTime": int(end_time.timestamp() * 1000) if end_time else None,
                "limit": limit,
            }
            return list(self.http.get_json(base_url, params))

        rows: list[dict[str, Any]] = []
        next_start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        while next_start_ms <= end_ms:
            page = list(
                self.http.get_json(
                    base_url,
                    {
                        "symbol": symbol,
                        "startTime": next_start_ms,
                        "endTime": end_ms,
                        "limit": limit,
                    },
                )
            )
            if not page:
                break
            rows.extend(page)
            if len(page) < limit:
                break
            next_start_ms = int(page[-1]["fundingTime"]) + 1
        return rows

    def fetch_open_interest(self, symbol: str) -> dict[str, Any]:
        return self.http.get_json(f"{self.futures_base_url}/fapi/v1/openInterest", {"symbol": symbol})

    def fetch_open_interest_history(
        self,
        symbol: str,
        *,
        period: str = "5m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        base_url = f"{self.futures_base_url}/futures/data/openInterestHist"
        if start_time is None or end_time is None:
            params = {
                "symbol": symbol,
                "period": period,
                "startTime": int(start_time.timestamp() * 1000) if start_time else None,
                "endTime": int(end_time.timestamp() * 1000) if end_time else None,
                "limit": limit,
            }
            return list(self.http.get_json(base_url, params))

        rows: list[dict[str, Any]] = []
        next_start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        while next_start_ms <= end_ms:
            page = list(
                self.http.get_json(
                    base_url,
                    {
                        "symbol": symbol,
                        "period": period,
                        "startTime": next_start_ms,
                        "endTime": end_ms,
                        "limit": limit,
                    },
                )
            )
            if not page:
                break
            rows.extend(page)
            if len(page) < limit:
                break
            next_start_ms = int(page[-1]["timestamp"]) + 1
        return rows

    def _fetch_futures_data_series(
        self,
        endpoint_path: str,
        symbol: str,
        *,
        period: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        base_url = f"{self.futures_base_url}{endpoint_path}"
        if start_time is None or end_time is None:
            params = {
                "symbol": symbol,
                "period": period,
                "startTime": int(start_time.timestamp() * 1000) if start_time else None,
                "endTime": int(end_time.timestamp() * 1000) if end_time else None,
                "limit": limit,
            }
            return list(self.http.get_json(base_url, params))

        rows: list[dict[str, Any]] = []
        next_start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        while next_start_ms <= end_ms:
            page = list(
                self.http.get_json(
                    base_url,
                    {
                        "symbol": symbol,
                        "period": period,
                        "startTime": next_start_ms,
                        "endTime": end_ms,
                        "limit": limit,
                    },
                )
            )
            if not page:
                break
            rows.extend(page)
            if len(page) < limit:
                break
            next_start_ms = int(page[-1]["timestamp"]) + 1
        return rows

    def fetch_global_long_short_account_ratio_history(
        self,
        symbol: str,
        *,
        period: str = "5m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._fetch_futures_data_series(
            "/futures/data/globalLongShortAccountRatio",
            symbol,
            period=period,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def fetch_top_trader_long_short_account_ratio_history(
        self,
        symbol: str,
        *,
        period: str = "5m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._fetch_futures_data_series(
            "/futures/data/topLongShortAccountRatio",
            symbol,
            period=period,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def fetch_top_trader_long_short_position_ratio_history(
        self,
        symbol: str,
        *,
        period: str = "5m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._fetch_futures_data_series(
            "/futures/data/topLongShortPositionRatio",
            symbol,
            period=period,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def fetch_taker_long_short_ratio_history(
        self,
        symbol: str,
        *,
        period: str = "5m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._fetch_futures_data_series(
            "/futures/data/takerlongshortRatio",
            symbol,
            period=period,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def fetch_premium_index(self, symbol: str) -> dict[str, Any]:
        return self.http.get_json(f"{self.futures_base_url}/fapi/v1/premiumIndex", {"symbol": symbol})

    def fetch_mark_price_klines(
        self,
        symbol: str,
        *,
        interval: str = "1m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[list[Any]]:
        base_url = f"{self.futures_base_url}/fapi/v1/markPriceKlines"
        if start_time is None or end_time is None:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": int(start_time.timestamp() * 1000) if start_time else None,
                "endTime": int(end_time.timestamp() * 1000) if end_time else None,
                "limit": limit,
            }
            return list(self.http.get_json(base_url, params))

        rows: list[list[Any]] = []
        next_start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        while next_start_ms <= end_ms:
            page = list(
                self.http.get_json(
                    base_url,
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "startTime": next_start_ms,
                        "endTime": end_ms,
                        "limit": limit,
                    },
                )
            )
            if not page:
                break
            rows.extend(page)
            if len(page) < limit:
                break
            next_start_ms = int(page[-1][6]) + 1
        return rows

    def fetch_index_price_klines(
        self,
        symbol: str,
        *,
        interval: str = "1m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[list[Any]]:
        base_url = f"{self.futures_base_url}/fapi/v1/indexPriceKlines"
        pair = _pair_from_symbol(symbol)
        if start_time is None or end_time is None:
            params = {
                "pair": pair,
                "interval": interval,
                "startTime": int(start_time.timestamp() * 1000) if start_time else None,
                "endTime": int(end_time.timestamp() * 1000) if end_time else None,
                "limit": limit,
            }
            return list(self.http.get_json(base_url, params))

        rows: list[list[Any]] = []
        next_start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        while next_start_ms <= end_ms:
            page = list(
                self.http.get_json(
                    base_url,
                    {
                        "pair": pair,
                        "interval": interval,
                        "startTime": next_start_ms,
                        "endTime": end_ms,
                        "limit": limit,
                    },
                )
            )
            if not page:
                break
            rows.extend(page)
            if len(page) < limit:
                break
            next_start_ms = int(page[-1][6]) + 1
        return rows

    def normalize_spot_instruments(self, payload: dict[str, Any]) -> list[InstrumentMetadata]:
        instruments: list[InstrumentMetadata] = []
        for symbol in payload.get("symbols", []):
            if symbol.get("quoteAsset") not in {"USDT", "USDC"}:
                continue
            filters = {item["filterType"]: item for item in symbol.get("filters", [])}
            instruments.append(
                InstrumentMetadata(
                    exchange_code="binance",
                    venue_symbol=symbol["symbol"],
                    unified_symbol=f"{symbol['symbol']}_SPOT",
                    instrument_type="spot",
                    base_asset=symbol["baseAsset"],
                    quote_asset=symbol["quoteAsset"],
                    settlement_asset=symbol["quoteAsset"],
                    tick_size=_decimal_or_none(filters.get("PRICE_FILTER", {}).get("tickSize")),
                    lot_size=_decimal_or_none(filters.get("LOT_SIZE", {}).get("stepSize")),
                    min_qty=_decimal_or_none(filters.get("LOT_SIZE", {}).get("minQty")),
                    min_notional=_decimal_or_none(filters.get("MIN_NOTIONAL", {}).get("minNotional")),
                    status=str(symbol.get("status", "trading")).lower(),
                    payload_json=symbol,
                )
            )
        return instruments

    def normalize_futures_instruments(self, payload: dict[str, Any]) -> list[InstrumentMetadata]:
        instruments: list[InstrumentMetadata] = []
        for symbol in payload.get("symbols", []):
            if symbol.get("contractType") not in {"PERPETUAL", "PERPETUAL_DELIVERING"}:
                continue
            filters = {item["filterType"]: item for item in symbol.get("filters", [])}
            instruments.append(
                InstrumentMetadata(
                    exchange_code="binance",
                    venue_symbol=symbol["symbol"],
                    unified_symbol=f"{symbol['symbol']}_PERP",
                    instrument_type="perp",
                    base_asset=symbol["baseAsset"],
                    quote_asset=symbol["quoteAsset"],
                    settlement_asset=symbol.get("marginAsset") or symbol.get("quoteAsset"),
                    tick_size=_decimal_or_none(filters.get("PRICE_FILTER", {}).get("tickSize")),
                    lot_size=_decimal_or_none(filters.get("LOT_SIZE", {}).get("stepSize")),
                    min_qty=_decimal_or_none(filters.get("LOT_SIZE", {}).get("minQty")),
                    min_notional=_decimal_or_none(filters.get("MIN_NOTIONAL", {}).get("notional")),
                    contract_size=Decimal("1"),
                    status=str(symbol.get("status", "trading")).lower(),
                    launch_time=_utc_from_millis(symbol["onboardDate"]) if symbol.get("onboardDate") else None,
                    payload_json=symbol,
                )
            )
        return instruments

    def fetch_instruments(self) -> list[InstrumentMetadata]:
        return [
            *self.normalize_spot_instruments(self.fetch_spot_exchange_info()),
            *self.normalize_futures_instruments(self.fetch_futures_exchange_info()),
        ]

    def normalize_klines(
        self,
        symbol: str,
        rows: Iterable[list[Any]],
        *,
        unified_symbol: str | None = None,
        interval: str = "1m",
    ) -> list[BarEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        events: list[BarEvent] = []
        for row in rows:
            events.append(
                BarEvent(
                    exchange_code="binance",
                    unified_symbol=normalized_symbol,
                    bar_interval=interval,
                    bar_time=_utc_from_millis(row[0]),
                    open=Decimal(str(row[1])),
                    high=Decimal(str(row[2])),
                    low=Decimal(str(row[3])),
                    close=Decimal(str(row[4])),
                    volume=Decimal(str(row[5])),
                    quote_volume=Decimal(str(row[7])),
                    trade_count=int(row[8]),
                    event_time=_utc_from_millis(row[6]),
                    ingest_time=datetime.now(timezone.utc),
                    payload_json={"kline": row},
                )
            )
        return events

    def normalize_funding_rates(
        self,
        symbol: str,
        rows: Iterable[dict[str, Any]],
        *,
        unified_symbol: str | None = None,
    ) -> list[FundingRateEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        return [
            FundingRateEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                funding_time=_utc_from_millis(row["fundingTime"]),
                funding_rate=Decimal(str(row["fundingRate"])),
                mark_price=_decimal_or_none(row.get("markPrice")),
                ingest_time=datetime.now(timezone.utc),
                payload_json=row,
            )
            for row in rows
        ]

    def normalize_open_interest(
        self,
        symbol: str,
        payload: dict[str, Any],
        *,
        observed_at: datetime | None = None,
        unified_symbol: str | None = None,
    ) -> OpenInterestEvent:
        event_time = observed_at or datetime.now(timezone.utc)
        return OpenInterestEvent(
            exchange_code="binance",
            unified_symbol=unified_symbol or f"{symbol}_PERP",
            event_time=event_time,
            ingest_time=event_time,
            open_interest=Decimal(str(payload["openInterest"])),
            payload_json=payload,
        )

    def normalize_open_interest_history(
        self,
        symbol: str,
        rows: Iterable[dict[str, Any]],
        *,
        unified_symbol: str | None = None,
    ) -> list[OpenInterestEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        return [
            OpenInterestEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=_utc_from_millis(row["timestamp"]),
                ingest_time=datetime.now(timezone.utc),
                open_interest=Decimal(str(row["sumOpenInterest"])),
                payload_json=row,
            )
            for row in rows
        ]

    def normalize_global_long_short_account_ratios(
        self,
        symbol: str,
        rows: Iterable[dict[str, Any]],
        *,
        period: str,
        unified_symbol: str | None = None,
    ) -> list[GlobalLongShortAccountRatioEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        ingest_time = datetime.now(timezone.utc)
        return [
            GlobalLongShortAccountRatioEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=_utc_from_millis(row["timestamp"]),
                ingest_time=ingest_time,
                period_code=period,
                long_short_ratio=Decimal(str(row["longShortRatio"])),
                long_account_ratio=_decimal_or_none(row.get("longAccount")),
                short_account_ratio=_decimal_or_none(row.get("shortAccount")),
                payload_json=row,
            )
            for row in rows
        ]

    def normalize_top_trader_long_short_account_ratios(
        self,
        symbol: str,
        rows: Iterable[dict[str, Any]],
        *,
        period: str,
        unified_symbol: str | None = None,
    ) -> list[TopTraderLongShortAccountRatioEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        ingest_time = datetime.now(timezone.utc)
        return [
            TopTraderLongShortAccountRatioEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=_utc_from_millis(row["timestamp"]),
                ingest_time=ingest_time,
                period_code=period,
                long_short_ratio=Decimal(str(row["longShortRatio"])),
                long_account_ratio=_decimal_or_none(row.get("longAccount")),
                short_account_ratio=_decimal_or_none(row.get("shortAccount")),
                payload_json=row,
            )
            for row in rows
        ]

    def normalize_top_trader_long_short_position_ratios(
        self,
        symbol: str,
        rows: Iterable[dict[str, Any]],
        *,
        period: str,
        unified_symbol: str | None = None,
    ) -> list[TopTraderLongShortPositionRatioEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        ingest_time = datetime.now(timezone.utc)
        return [
            TopTraderLongShortPositionRatioEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=_utc_from_millis(row["timestamp"]),
                ingest_time=ingest_time,
                period_code=period,
                long_short_ratio=Decimal(str(row["longShortRatio"])),
                long_account_ratio=_decimal_or_none(row.get("longAccount")),
                short_account_ratio=_decimal_or_none(row.get("shortAccount")),
                payload_json=row,
            )
            for row in rows
        ]

    def normalize_taker_long_short_ratios(
        self,
        symbol: str,
        rows: Iterable[dict[str, Any]],
        *,
        period: str,
        unified_symbol: str | None = None,
    ) -> list[TakerLongShortRatioEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        ingest_time = datetime.now(timezone.utc)
        return [
            TakerLongShortRatioEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=_utc_from_millis(row["timestamp"]),
                ingest_time=ingest_time,
                period_code=period,
                buy_sell_ratio=Decimal(str(row["buySellRatio"])),
                buy_vol=_decimal_or_none(row.get("buyVol")),
                sell_vol=_decimal_or_none(row.get("sellVol")),
                payload_json=row,
            )
            for row in rows
        ]

    def normalize_premium_index(
        self,
        symbol: str,
        payload: dict[str, Any],
        *,
        observed_at: datetime | None = None,
        unified_symbol: str | None = None,
    ) -> tuple[MarkPriceEvent, IndexPriceEvent]:
        event_time = _utc_from_millis(payload["time"])
        ingest_time = observed_at or datetime.now(timezone.utc)
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        return (
            MarkPriceEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=event_time,
                ingest_time=ingest_time,
                mark_price=Decimal(str(payload["markPrice"])),
                funding_basis_bps=(
                    (Decimal(str(payload["markPrice"])) - Decimal(str(payload["indexPrice"])))
                    / Decimal(str(payload["indexPrice"]))
                    * Decimal("10000")
                    if Decimal(str(payload["indexPrice"])) != 0
                    else None
                ),
                payload_json=payload,
            ),
            IndexPriceEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=event_time,
                ingest_time=ingest_time,
                index_price=Decimal(str(payload["indexPrice"])),
                payload_json=payload,
            ),
        )

    def normalize_mark_price_klines(
        self,
        symbol: str,
        rows: Iterable[list[Any]],
        *,
        unified_symbol: str | None = None,
    ) -> list[MarkPriceEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        events: list[MarkPriceEvent] = []
        for row in rows:
            events.append(
                MarkPriceEvent(
                    exchange_code="binance",
                    unified_symbol=normalized_symbol,
                    event_time=_utc_from_millis(row[0]),
                    ingest_time=datetime.now(timezone.utc),
                    mark_price=Decimal(str(row[4])),
                    funding_basis_bps=None,
                    payload_json={"mark_price_kline": row},
                )
            )
        return events

    def normalize_index_price_klines(
        self,
        symbol: str,
        rows: Iterable[list[Any]],
        *,
        unified_symbol: str | None = None,
    ) -> list[IndexPriceEvent]:
        normalized_symbol = unified_symbol or f"{symbol}_PERP"
        return [
            IndexPriceEvent(
                exchange_code="binance",
                unified_symbol=normalized_symbol,
                event_time=_utc_from_millis(row[0]),
                ingest_time=datetime.now(timezone.utc),
                index_price=Decimal(str(row[4])),
                payload_json={"index_price_kline": row},
            )
            for row in rows
        ]
