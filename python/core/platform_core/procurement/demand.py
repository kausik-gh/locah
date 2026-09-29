"""Deterministic buying math.

net = max(0, demand + safety stock − usable stock − confirmed inbound)

then the supplier pack size and minimum order lift the quantity. The
explanation keeps every input so a person can see why the number exists.
"""

from __future__ import annotations

from typing import Any


def net_requirement(*, demand: int, safety: int, usable: int, inbound: int) -> int:
    return max(0, demand + safety - usable - inbound)


def round_to_supplier(*, net: int, pack_size: int, moq: int) -> int:
    """Lift a net requirement to a whole pack that meets the minimum order."""
    if net <= 0:
        return 0
    pack = pack_size if pack_size > 1 else 1
    minimum = moq if moq > 0 else 1
    quantity = ((net + pack - 1) // pack) * pack
    if quantity < minimum:
        quantity = ((minimum + pack - 1) // pack) * pack
    return quantity


def explode_recipe(finished_quantity: int, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn finished demand into component demand. yield_ratio is output per input."""
    out: list[dict[str, Any]] = []
    for line in lines:
        per = float(line["quantity_per"])
        yield_ratio = float(line.get("yield_ratio") or 1)
        raw = finished_quantity * per / yield_ratio
        out.append({
            "component_offering_id": str(line["component_offering_id"]),
            "demand": int(raw + 0.999999) if raw > 0 else 0,
        })
    return out


def explain(
    *,
    demand: int,
    safety: int,
    usable: int,
    inbound: int,
    net: int,
    buy: int,
    pack_size: int,
    moq: int,
) -> str:
    return (
        f"Required {demand}. Safety stock {safety}. Usable {usable}. "
        f"Confirmed inbound {inbound}. Net {net}. "
        f"Pack {pack_size}, minimum {moq}, so buy {buy}."
    )
