#!/usr/bin/env python3
# ============================================================
# Uniswap V2 – Single-bin Sequential Execution Simulator
# (Correct volume + explicit fee accounting)
# ============================================================

import random
from copy import deepcopy
import math

from instances import (
    BIN_SECONDS,
    SECONDS_PER_YEAR
)

def run_uniswap_bin(
    *,
    x0: float,                 # initial base-asset reserve
    y0: float,                 # initial quote (USD) reserve
    users: list,               # list of user dicts {q, p_min, p_max}
    fee: float,                # e.g. 0.003 for 0.30%
    seed: int | None = None,
    P0 : float | None = None,   
    P_market : float | None = None, # current market price which differs from y0/x0
):
    """
    Sequential Uniswap V2 execution for a single bin.

    Conventions:
      x : base (risky) asset
      y : USD / quote asset
      P = y / x

    User convention:
      q > 0 : user buys x (LP sells x)
      q < 0 : user sells x (LP buys x)
    """

    if seed is not None:
        random.seed(seed)

    # --------------------------------------------------------
    # Initial state
    # --------------------------------------------------------
    x = float(x0)
    y = float(y0)

    if x <= 0 or y <= 0:
        return {"status": "INFEASIBLE", "reason": "invalid_initial_reserves"}

    k = x * y

    executed_users = []
    dropped_users = []

    executed_volume = 0.0
    fee_income_usd = 0.0

    # --------------------------------------------------------
    # Shuffle users to simulate gas-order randomness
    # --------------------------------------------------------
    users_seq = deepcopy(users)
    random.shuffle(users_seq)

    # --------------------------------------------------------
    # Sequential execution
    # --------------------------------------------------------
    for u in users_seq:
        q = float(u.get("q", 0.0))
        p_min = u.get("p_min", None)
        p_max = u.get("p_max", None)

        if q == 0:
            dropped_users.append(u)
            continue

        P_before = y / x

        # ====================================================
        # Buy x (q > 0): user pays y, LP gives x
        # ====================================================
        if q > 0:
            dx = q
            x_after = x - dx

            if x_after <= 0:
                dropped_users.append(u)
                continue


            # Solve invariant with fee-adjusted input
            # (x - dx) * (y + dy_effective) = k
            dy_effective = k / x_after - y
            if dy_effective <= 0:
                dropped_users.append(u)
                continue

            dy_in = dy_effective / (1 - fee)
            fee_paid = dy_in - dy_effective

            P_user = dy_in / dx

            if p_max is not None and P_user > p_max:
                dropped_users.append(u)
                continue

            # Apply trade
            x = x_after
            y = y + dy_in
            k = x * y

            executed_volume += abs(q)
            fee_income_usd += fee_paid
            executed_users.append(u)

        # ====================================================
        # Sell x (q < 0): user gives x, LP pays y
        # ====================================================
        else:
            dx = -q
            x_after = x + dx

            dy_effective = y - k / x_after
            if dy_effective <= 0:
                dropped_users.append(u)
                continue

            dy_out = dy_effective * (1 - fee)
            fee_paid = dy_effective - dy_out

            P_user = dy_out / dx

            if p_min is not None and P_user < p_min:
                dropped_users.append(u)
                continue

            # Apply trade
            x = x_after
            y = y - dy_out
            k = x * y

            executed_volume += abs(q)
            fee_income_usd += fee_paid
            executed_users.append(u)


    # --------------------------------------------------------
    # Arbitrage step: align pool to external market price
    # --------------------------------------------------------
    ''' # the following block is invalid due to simulation premises
        # if arbitrage is allowed, fees should also be collected during the arbitrage step, which is not currently modeled
        # it is assumed that the current inventory mismatch to P_market is due to random execution order
        # differences from Market Price to current P_Final are corrected in the following bin execution
    if P_market is not None:

        # Preserve invariant
        k = x * y

        # Solve:
        # y_new / x_new = P_market
        # x_new * y_new = k

        x = math.sqrt(k / P_market)
        y = math.sqrt(k * P_market)

        # After arbitrage, pool price equals market
    '''
    # --------------------------------------------------------
    # LP accounting
    # --------------------------------------------------------
    P_final = y / x if x > 0 else float("inf")

    if P_market is None : P_market = P_final

    wallet_hold = y0 + x0 * P_market
    wallet_now  = y  + x  * P_market
    
    # Impermanent loss (<=0 → loss to LP)
    # wallet_now_without_fee = wallet_now -fee_income_usd
    # this is required for not double-counting fee income as part of IL
    # since fees are a transfer from users to LPs
    IL_USD = (wallet_now - fee_income_usd) - wallet_hold

    # --------------------------------------------------------
    # Result bundle
    # --------------------------------------------------------
    return {
        "status": "OK",
        "x0": x0,
        "y0": y0,
        "x1": x,
        "y1": y,
        "Previous_market_price": P0,
        "Price_start_bin_previous_inventory": y0 / x0 if x0 > 0 else None,
        "P_end": P_final,
        "executed_volume_usd": executed_volume*P_market if x0 > 0 else 0.0,  # approximate USD volume using initial price
        "kept_volume": executed_volume,
        "fee_income_usd": fee_income_usd,
        "IL_USD": IL_USD,
        "IL_USD_percent": (IL_USD / wallet_hold) * 100 if wallet_hold > 0 else None,
        #"active_users": executed_users,
        #"dropped_users": dropped_users,
        "count_active_users": len(executed_users),
        "count_dropped_users": len(dropped_users),
        "fee": fee,
        "return_LP": (fee_income_usd + IL_USD)/wallet_hold if wallet_hold > 0 else None, #* SECONDS_PER_YEAR/BIN_SECONDS
        "check_return": (wallet_now - wallet_hold)/wallet_hold if wallet_hold > 0 else None, #* SECONDS_PER_YEAR/BIN_SECONDS
    }