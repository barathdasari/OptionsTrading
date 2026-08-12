"""
Zone dataclass and related types.

A Zone is a price region — not a point — with defined midpoint and width.
Width is always ATR-normalised: zone_width = k * ATR(14).

Causal invariant: formed_at is the bar AFTER which this zone becomes visible
to a trading system. No zone input to any signal may use data after formed_at.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class ZoneType(Enum):
    PREV_DAY_HIGH   = "prev_day_high"
    PREV_DAY_LOW    = "prev_day_low"
    WEEKLY_HIGH     = "weekly_high"
    WEEKLY_LOW      = "weekly_low"
    SWING_HIGH      = "swing_high"
    SWING_LOW       = "swing_low"
    VOLUME_POC      = "volume_poc"   # requires volume data
    VOLUME_VAH      = "volume_vah"   # requires volume data
    VOLUME_VAL      = "volume_val"   # requires volume data

    @property
    def is_resistance(self) -> bool:
        return self in {
            ZoneType.PREV_DAY_HIGH,
            ZoneType.WEEKLY_HIGH,
            ZoneType.SWING_HIGH,
            ZoneType.VOLUME_VAH,
        }

    @property
    def is_support(self) -> bool:
        return self in {
            ZoneType.PREV_DAY_LOW,
            ZoneType.WEEKLY_LOW,
            ZoneType.SWING_LOW,
            ZoneType.VOLUME_VAL,
        }

    @property
    def is_neutral(self) -> bool:
        return self in {ZoneType.VOLUME_POC}


@dataclass
class Zone:
    """
    A single price zone active at a given timestamp.

    Attributes
    ----------
    level       : midpoint price of zone
    zone_low    : level - zone_width / 2
    zone_high   : level + zone_width / 2
    zone_type   : category of zone
    formed_at   : timestamp of the bar after which this zone is valid
                  (causal: zone cannot be used on the bar that formed it)
    atr_at_formation : ATR value used to set zone width
    k           : ATR multiplier used (zone_width = k * atr)
    touch_count : how many times price has entered this zone (updated by EventEngine)
    score       : composite significance score (0–3 scale, see ZoneScorer)
    """
    level: float
    zone_low: float
    zone_high: float
    zone_type: ZoneType
    formed_at: pd.Timestamp
    atr_at_formation: float
    k: float = 0.5
    touch_count: int = 0
    score: float = 0.0

    @property
    def width(self) -> float:
        return self.zone_high - self.zone_low

    def contains(self, price: float) -> bool:
        """True if price is inside [zone_low, zone_high]."""
        return self.zone_low <= price <= self.zone_high

    def distance_to(self, price: float) -> float:
        """Absolute distance from price to zone midpoint."""
        return abs(price - self.level)

    def distance_normalised(self, price: float, atr: float) -> float:
        """Distance to midpoint expressed in ATR units."""
        if atr <= 0:
            return float("inf")
        return self.distance_to(price) / atr

    def __repr__(self) -> str:
        return (
            f"Zone({self.zone_type.value} "
            f"[{self.zone_low:.1f}–{self.zone_high:.1f}] "
            f"formed={self.formed_at.date()} "
            f"score={self.score:.2f} touches={self.touch_count})"
        )


@dataclass
class ZoneSet:
    """
    Collection of zones active at a single bar timestamp.

    Used as the output of ZoneDetector.zones_at(t).
    """
    timestamp: pd.Timestamp
    zones: list[Zone] = field(default_factory=list)

    def zones_by_type(self, zone_type: ZoneType) -> list[Zone]:
        return [z for z in self.zones if z.zone_type == zone_type]

    def nearest_zone(self, price: float) -> Zone | None:
        if not self.zones:
            return None
        return min(self.zones, key=lambda z: z.distance_to(price))

    def zones_containing(self, price: float) -> list[Zone]:
        return [z for z in self.zones if z.contains(price)]

    def __len__(self) -> int:
        return len(self.zones)

    def __repr__(self) -> str:
        return f"ZoneSet(t={self.timestamp.date()} n_zones={len(self.zones)})"
