from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from itertools import count
from typing import Protocol

from models.common import LiquidityFlag, OrderSide, OrderStatus, OrderType
from models.market import BarEvent
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .lifecycle import ExecutionIntent


@dataclass(slots=True)
class SimulatedOrder:
    order_id: str
    exchange_code: str
    unified_symbol: str
    order_time: datetime
    side: OrderSide
    order_type: OrderType
    requested_price: Decimal | None
    qty: Decimal
    reduce_only: bool
    status: OrderStatus
    metadata_json: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class SimulatedFill:
    fill_id: str
    order_id: str
    exchange_code: str
    unified_symbol: str
    fill_time: datetime
    side: OrderSide
    liquidity_flag: LiquidityFlag
    reference_price: Decimal
    fill_price: Decimal
    qty: Decimal
    fee: Decimal
    slippage_cost: Decimal
    metadata_json: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class SimulatedOrderUpdate:
    order: SimulatedOrder
    fill: SimulatedFill | None = None


class FeeModel(Protocol):
    def compute_fee(
        self,
        *,
        connection: Connection | None,
        order: SimulatedOrder,
        fill_time: datetime,
        fill_price: Decimal,
        qty: Decimal,
        liquidity_flag: LiquidityFlag,
    ) -> Decimal: ...


class SlippageModel(Protocol):
    def apply(
        self,
        *,
        order: SimulatedOrder,
        reference_price: Decimal,
    ) -> tuple[Decimal, Decimal]: ...


@dataclass(slots=True)
class FeeScheduleQuote:
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal


class DatabaseFeeScheduleModel:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], FeeScheduleQuote] = {}

    def compute_fee(
        self,
        *,
        connection: Connection | None,
        order: SimulatedOrder,
        fill_time: datetime,
        fill_price: Decimal,
        qty: Decimal,
        liquidity_flag: LiquidityFlag,
    ) -> Decimal:
        if connection is None:
            raise ValueError("database-backed fee model requires a SQLAlchemy connection")

        quote = self._lookup_quote(connection, order.exchange_code, order.unified_symbol, fill_time)
        fee_bps = quote.maker_fee_bps if liquidity_flag == LiquidityFlag.MAKER else quote.taker_fee_bps
        notional = fill_price * qty
        return (notional * fee_bps) / Decimal("10000")

    def _lookup_quote(
        self,
        connection: Connection,
        exchange_code: str,
        unified_symbol: str,
        as_of: datetime,
    ) -> FeeScheduleQuote:
        cache_key = (exchange_code, unified_symbol)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        row = connection.execute(
            text(
                """
                select
                    f.maker_fee_bps,
                    f.taker_fee_bps
                from ref.fee_schedules f
                join ref.exchanges e on e.exchange_id = f.exchange_id
                join ref.instruments i
                  on i.exchange_id = e.exchange_id
                 and i.instrument_type = f.instrument_type
                where e.exchange_code = :exchange_code
                  and i.unified_symbol = :unified_symbol
                  and f.vip_tier = 'default'
                  and f.effective_from <= :as_of
                order by f.effective_from desc
                limit 1
                """
            ),
            {
                "exchange_code": exchange_code,
                "unified_symbol": unified_symbol,
                "as_of": as_of,
            },
        ).mappings().first()
        if row is None:
            raise LookupError(
                f"no fee schedule found for exchange_code={exchange_code} unified_symbol={unified_symbol}"
            )

        quote = FeeScheduleQuote(
            maker_fee_bps=Decimal(row["maker_fee_bps"]),
            taker_fee_bps=Decimal(row["taker_fee_bps"]),
        )
        self._cache[cache_key] = quote
        return quote


class StaticFeeModel:
    def __init__(self, *, maker_fee_bps: DecimalLike = "0", taker_fee_bps: DecimalLike = "0") -> None:
        self.maker_fee_bps = Decimal(str(maker_fee_bps))
        self.taker_fee_bps = Decimal(str(taker_fee_bps))

    def compute_fee(
        self,
        *,
        connection: Connection | None,
        order: SimulatedOrder,
        fill_time: datetime,
        fill_price: Decimal,
        qty: Decimal,
        liquidity_flag: LiquidityFlag,
    ) -> Decimal:
        fee_bps = self.maker_fee_bps if liquidity_flag == LiquidityFlag.MAKER else self.taker_fee_bps
        return (fill_price * qty * fee_bps) / Decimal("10000")


class FixedBpsSlippageModel:
    def __init__(
        self,
        *,
        market_order_bps: DecimalLike = "1",
        limit_order_bps: DecimalLike = "0",
    ) -> None:
        self.market_order_bps = Decimal(str(market_order_bps))
        self.limit_order_bps = Decimal(str(limit_order_bps))

    def apply(
        self,
        *,
        order: SimulatedOrder,
        reference_price: Decimal,
    ) -> tuple[Decimal, Decimal]:
        if order.order_type == OrderType.MARKET:
            slippage_bps = self.market_order_bps
        else:
            slippage_bps = self.limit_order_bps

        if slippage_bps == 0:
            return reference_price, Decimal("0")

        direction = Decimal("1") if order.side == OrderSide.BUY else Decimal("-1")
        adjustment = (reference_price * slippage_bps) / Decimal("10000")
        fill_price = reference_price + (direction * adjustment)
        slippage_cost = abs(fill_price - reference_price) * order.qty
        return fill_price, slippage_cost


DecimalLike = Decimal | str | int | float


class DeterministicBarsFillModel:
    def __init__(
        self,
        *,
        fee_model: FeeModel | None = None,
        slippage_model: SlippageModel | None = None,
    ) -> None:
        self.fee_model = fee_model or DatabaseFeeScheduleModel()
        self.slippage_model = slippage_model or FixedBpsSlippageModel()
        self._order_sequence = count(1)
        self._fill_sequence = count(1)

    def create_order(
        self,
        intent: ExecutionIntent,
        *,
        current_bar: BarEvent,
    ) -> SimulatedOrder:
        requested_price = self._derive_requested_price(intent, current_bar)
        return SimulatedOrder(
            order_id=f"bt_order_{next(self._order_sequence):06d}",
            exchange_code=intent.exchange_code,
            unified_symbol=intent.unified_symbol,
            order_time=intent.generated_at,
            side=intent.side,
            order_type=intent.order_type,
            requested_price=requested_price,
            qty=abs(intent.delta_qty),
            reduce_only=intent.reduce_only,
            status=OrderStatus.SUBMITTED,
            metadata_json=dict(intent.metadata_json),
        )

    def process_open_order(
        self,
        order: SimulatedOrder,
        *,
        current_bar: BarEvent,
        connection: Connection | None = None,
    ) -> SimulatedOrderUpdate:
        if order.status not in {OrderStatus.NEW, OrderStatus.SUBMITTED, OrderStatus.PARTIAL}:
            return SimulatedOrderUpdate(order=order)
        if order.unified_symbol != current_bar.unified_symbol:
            return SimulatedOrderUpdate(order=order)

        fill_basis = self._resolve_fill_basis(order, current_bar)
        if fill_basis is None:
            return SimulatedOrderUpdate(order=order)

        reference_price, liquidity_flag = fill_basis
        fill_price, slippage_cost = self.slippage_model.apply(order=order, reference_price=reference_price)
        fee = self.fee_model.compute_fee(
            connection=connection,
            order=order,
            fill_time=current_bar.bar_time,
            fill_price=fill_price,
            qty=order.qty,
            liquidity_flag=liquidity_flag,
        )
        order.status = OrderStatus.FILLED
        fill = SimulatedFill(
            fill_id=f"bt_fill_{next(self._fill_sequence):06d}",
            order_id=order.order_id,
            exchange_code=order.exchange_code,
            unified_symbol=order.unified_symbol,
            fill_time=current_bar.bar_time,
            side=order.side,
            liquidity_flag=liquidity_flag,
            reference_price=reference_price,
            fill_price=fill_price,
            qty=order.qty,
            fee=fee,
            slippage_cost=slippage_cost,
            metadata_json={"order_type": order.order_type},
        )
        return SimulatedOrderUpdate(order=order, fill=fill)

    @staticmethod
    def expire_open_order(order: SimulatedOrder) -> SimulatedOrder:
        if order.status in {OrderStatus.NEW, OrderStatus.SUBMITTED, OrderStatus.PARTIAL}:
            order.status = OrderStatus.EXPIRED
        return order

    def _derive_requested_price(self, intent: ExecutionIntent, current_bar: BarEvent) -> Decimal | None:
        if intent.order_type == OrderType.LIMIT:
            limit_price = intent.limit_price
            if limit_price is None:
                limit_price = Decimal(str(intent.metadata_json.get("limit_price", current_bar.close)))
            return Decimal(limit_price)
        return None

    def _resolve_fill_basis(
        self,
        order: SimulatedOrder,
        current_bar: BarEvent,
    ) -> tuple[Decimal, LiquidityFlag] | None:
        if order.order_type == OrderType.MARKET:
            return current_bar.open, LiquidityFlag.TAKER

        if order.order_type == OrderType.LIMIT:
            limit_price = order.requested_price
            if limit_price is None:
                return None
            if order.side == OrderSide.BUY and current_bar.low <= limit_price:
                return limit_price, LiquidityFlag.MAKER
            if order.side == OrderSide.SELL and current_bar.high >= limit_price:
                return limit_price, LiquidityFlag.MAKER
            return None

        raise ValueError(f"unsupported deterministic fill order_type: {order.order_type}")
