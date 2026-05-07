#!/usr/bin/env python3
# ============================================================
# Part 1 — Instance Generation for VeltoraCore Experiments
# ============================================================

import math
import random
from dataclasses import dataclass, asdict
from typing import List, Dict

from config import (
    BIN_SECONDS,
    SECONDS_PER_YEAR,
    LIQUIDITY_USD,
    TOTAL_USER_DEMAND_USD,
    RISK_FREE_APR,
    MARKET_PREMIUM_TOP,
    MARKET_PREMIUM_FLOOR,
    FEE_GRID,
    ANNUAL_VOL
)

# -----------------------------
# Data classes
# -----------------------------
@dataclass
class User:
    q: float        # signed x
    p_min: float
    p_max: float

@dataclass
class LP:
    capitalUSD: float
    floorAPR: float

# -----------------------------
# User generation (volatility-based slippage)
# Most users tolerate 0.1%–1% slippage, with a long tail of more aggressive users
# -----------------------------
import math
import random
from typing import List

def generate_users(
    n_users: int,
    price_center: float,
    seed: int
) -> List[User]:

    random.seed(seed)
    users = []

    # Convert annual volatility to bin volatility
    sigma_bin = ANNUAL_VOL * math.sqrt(BIN_SECONDS / SECONDS_PER_YEAR)

    # Random weights to distribute total demand
    weights = [random.random() for _ in range(n_users)]
    s = sum(weights)
    weights = [w / s for w in weights]

    for w in weights:
        usd = TOTAL_USER_DEMAND_USD * w
        direction = random.choice([1, -1])
        q = direction * (usd / price_center)

        # Behavioral aggressiveness multiplier (lognormal → realistic skew)
        k = random.lognormvariate(-0.2, 0.4) # mean around 0.85, long tail above 1

        # Slippage tolerance scales with volatility
        impact_floor = TOTAL_USER_DEMAND_USD / LIQUIDITY_USD
        base_spread = 3 * max(sigma_bin, impact_floor)

        spread = k * base_spread
        spread = min(spread, 0.05)  # cap at 5%

        # Symmetric band (default)
        p_min = price_center * (1 - spread)
        p_max = price_center * (1 + spread)

        # Optional: directional asymmetry (more realistic microstructure)
        # Uncomment if desired:
        #
        # if direction == 1:  # buy
        #     p_min = price_center
        #     p_max = price_center * (1 + spread)
        # else:  # sell
        #     p_min = price_center * (1 - spread)
        #     p_max = price_center

        users.append(User(q=q, p_min=p_min, p_max=p_max))

    return users

# -----------------------------
# LP generation
# -----------------------------
def generate_lps(
    total_capital_usd: float,
    n_lps: int,
    seed: int
) -> List[LP]:
    random.seed(seed)

    # -----------------------------
    # Capital allocation (Dirichlet-like)
    # -----------------------------
    weights = [random.random() for _ in range(n_lps)]
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    lps = []
    for w in weights:
        # -----------------------------
        # Heterogeneous LP floor APR
        # Range: [RISK_FREE + premium_floor, RISK_FREE + premium_top]
        # -----------------------------
        premium = random.uniform(
            MARKET_PREMIUM_FLOOR,
            MARKET_PREMIUM_TOP
        )

        floor_apr = RISK_FREE_APR + premium

        lps.append(
            LP(
                capitalUSD=total_capital_usd * w,
                floorAPR=floor_apr
            )
        )

    return lps

# -----------------------------
# Price grid (user-centered, with extreme bounds)
# -----------------------------
def price_grid_from_users(users: List[User]) -> List[float]:
    # Volume-weighted central price
    total_q = sum(abs(u.q) for u in users)
    P_user = sum(
        abs(u.q) * ((u.p_min + u.p_max) / 2)
        for u in users
    ) / total_q

    multipliers = [
        0.85, 0.90, 0.95,
        0.97, 0.99,
        1.00,
        1.01, 1.03,
        1.05, 1.10, 1.15
    ]

    grid = {P_user * m for m in multipliers}

    # Global user bounds
    p_min = min(u.p_min for u in users)
    p_max = max(u.p_max for u in users)

    # Ensure extremes are explicitly tested
    grid.add(p_min)
    grid.add(p_max)

    # Clip + sort
    return sorted(p for p in grid if p_min <= p <= p_max)


# -----------------------------
# Fee grid (VeltoraCore)
# -----------------------------
def fee_grid() -> List[float]:
    return FEE_GRID

