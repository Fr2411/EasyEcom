from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockDeltas:
    on_hand: float = 0.0
    incoming: float = 0.0
    reserved: float = 0.0


ON_HAND_INBOUND_TYPES = {"IN", "ADJUST+", "ADJUST"}
ON_HAND_OUTBOUND_TYPES = {"OUT"}
PENDING_INBOUND_TYPES = {"INBOUND_PENDING"}
PENDING_INBOUND_RELEASE_TYPES = {"INBOUND_RECEIVED"}


def stock_deltas(txn_type: str, qty: float) -> StockDeltas:
    normalized = str(txn_type or "").strip().upper()
    value = float(qty or 0.0)

    if normalized in ON_HAND_INBOUND_TYPES:
        return StockDeltas(on_hand=value)
    if normalized in ON_HAND_OUTBOUND_TYPES:
        return StockDeltas(on_hand=-value)
    if normalized in PENDING_INBOUND_TYPES:
        return StockDeltas(incoming=value)
    if normalized in PENDING_INBOUND_RELEASE_TYPES:
        return StockDeltas(incoming=-value)
    return StockDeltas()

