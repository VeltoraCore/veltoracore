#!/usr/bin/env python3
# ============================================================
# VeltoraCore Solver with LP Fixed-Point Participation
# (Price-sweep aware, market valuation at swept price)
# ============================================================

import json
import sys
import time
from copy import deepcopy
from ortools.linear_solver import pywraplp


def sum_capital(lps):
    return sum(float(lp.get("capitalUSD", 0.0)) for lp in lps)

# ------------------------------------------------------------
# Single execution solve (conditional on swept price P)
# ------------------------------------------------------------

# Conventions:
#   x : base (risky) asset
#   y : USD / quote asset
#   P : USD per unit of x (y/x)
#   q (always on x) : user order size (signed x) - positive buy(negative for bin), negative sell (positive for bin)

def solve_execution_once(inst, fee, time_limit=None):
    users = inst.get("users", [])
    lps   = inst.get("lps", [])

    #fee = float(inst.get("fee", 0.0))

    # Prices must be provided by orchestrator
    P0 = float(inst["p0"])      # previous-bin market price
    P  = float(inst["price"])   # swept market price

    # --------------------------------------------------------
    # LP capital (USD)
    # --------------------------------------------------------
    total_cap = sum_capital(lps)
    if total_cap <= 0:
        return {"status": "INFEASIBLE", "reason": "no_lp_capital"}

    # Balanced LP inventory at previous-bin price
    y0 = total_cap / 2.0                  # USD
    x0 = (total_cap / 2.0) / P0           # asset

    # --------------------------------------------------------
    # Solver
    # --------------------------------------------------------
    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        return {"status": "INFEASIBLE", "reason": "solver_init_failed"}

    w, dx, dy = [], [], []

    # --------------------------------------------------------
    # User execution constraints
    # --------------------------------------------------------
    for i, u in enumerate(users):
        wi  = solver.BoolVar(f"w_{i}")
        dxi = solver.NumVar(-solver.infinity(), solver.infinity(), f"dx_{i}")
        dyi = solver.NumVar(-solver.infinity(), solver.infinity(), f"dy_{i}")

        q = float(u.get("q", 0.0))   # signed: +buy x, -sell x
        p_min = u.get("p_min", None)
        p_max = u.get("p_max", None)

        # Enforce user price feasibility at swept price P
        # Buy (q>0): require P <= p_max
        # Sell (q<0): require P >= p_min
        P_fee = P * (1 + fee)

        # Buy (q > 0): user pays P_user, must be ≤ p_max
        if q > 0 and p_max is not None and P_fee > p_max:
            solver.Add(wi == 0)

        # Sell (q < 0): user receives P_user, must be ≥ p_min
        if q < 0 and p_min is not None and P_fee < p_min:
            solver.Add(wi == 0)

        if q > 0:
        # LP-perspective inventory deltas
        # Buy x  (q>0): LP loses x, gains y
        # Sell x (q<0): LP gains x, loses y
            solver.Add(dxi == -wi * q)
            solver.Add(dyi ==  wi * q * P * (1 + fee))
        elif q < 0:
            solver.Add(dxi == -wi * q)
            solver.Add(dyi ==  wi * q * P * (1 - fee))

        w.append(wi)
        dx.append(dxi)
        dy.append(dyi)

    # LP inventory must remain non-negative
    # Block below is important because joins dx and dy to optimization regarding LP inventory
    solver.Add(x0 + solver.Sum(dx) >= 0)
    solver.Add(y0 + solver.Sum(dy) >= 0)

    # --------------------------------------------------------
    # Objective: maximize executed volume (absolute)
    # --------------------------------------------------------
    obj = solver.Objective()
    for i, u in enumerate(users):
        obj.SetCoefficient(w[i], abs(float(u.get("q", 0.0))))
    obj.SetMaximization()

    
    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        return {"status": "INFEASIBLE", "reason": "no_optimal_solution"}

    # --------------------------------------------------------
    # Post-execution accounting
    # --------------------------------------------------------
    kept_volume = sum(
        abs(float(users[i].get("q", 0.0)))
        for i in range(len(users))
        if w[i].solution_value() > 0.5
    )

    kept_users = [
    users[i]
    for i in range(len(users))
    if w[i].solution_value() > 0.5
    ]

    x1 = x0 + sum(dx[i].solution_value() for i in range(len(dx)))
    y1 = y0 + sum(dy[i].solution_value() for i in range(len(dy)))

    # Diagnostic effective ratio (not a market price)
    P_eff = y1 / x1 if x1 > 0 else 0.0

    # --- User executed value (USD)
    user_value_usd = kept_volume * P

    # --- LP fee income (USD)
    lp_fee_income_usd = user_value_usd * fee

     # Remove fees from y1 before computing IL
    wallet_now_no_fee = (y1 - lp_fee_income_usd) + x1 * P
    wallet_hold = y0 + x0 * P

    # IL <= 0 means loss to LP
    IL_USD = wallet_now_no_fee - wallet_hold
    IL_percent = ((wallet_now_no_fee - wallet_hold) / wallet_hold)*100 if wallet_hold > 0 else 0.0

    # --- LP surplus before floor (USD)
    # IL_USD is negative when LPs lose
    lp_surplus_usd = lp_fee_income_usd + IL_USD

    lp_surplus_volume = lp_surplus_usd / fee if fee > 0 else 0.0

    # --- Protocol objective (USD)
    # Protocol objective expressed in execution-volume-equivalent units:
    #   user USD value + (LP surplus USD normalized by fee)
    protocol_objective = user_value_usd + lp_surplus_volume

    return {
        "status": "OPTIMAL",
        "total_users": len(users),
        "count_dropped_users": len([u for u in users if u not in kept_users]),
        "total_users_original_demand_usd": sum(abs(float(u.get("q", 0.0))) * P0 for u in users),
        "kept_volume_P0": kept_volume * P0,
        "kept_volume_P": user_value_usd,
        "kept_volume": kept_volume,
        "lp_fee_usd": lp_fee_income_usd,
        "IL_USD": IL_USD,
        "IL_percent": IL_percent,
        "lp_surplus_income": lp_surplus_usd,
        "lp_surplus_volume": lp_surplus_volume,
        "protocol_objective": protocol_objective,
        "x0": x0,
        "x1": x1,
        "y0": y0,
        "y1": y1,
        "P0": P0,
        "P": P,
        #"P_eff": P_eff,
        "fee": fee,
        "income_check": (y1 + x1 * P) - (y0 + x0 * P),
        #"active_users": kept_users
    }

# ------------------------------------------------------------
# Solver with LP fixed-point participation
# ------------------------------------------------------------
def solve_with_lp_fixed_point(inst, fee, time_limit=None, opts=None):
    t_fp_start = time.perf_counter()
    if opts is None:
        opts = {}

    active_lps = deepcopy(inst.get("lps", []))
    bin_seconds = float(opts.get("binSeconds", 0.0))
    seconds_per_year = float(opts.get("secondsPerYear", 31536000))

    # Guard: APR-based floors require positive bin length
    if bin_seconds <= 0 and not opts.get("ignoreMin", False):
        return None

    while True:
        if not active_lps:
            return None

        inst_fp = deepcopy(inst)
        inst_fp["lps"] = active_lps

        sol = solve_execution_once(inst_fp, fee, time_limit)
        if sol is None:
            return None

        total_cap = sum_capital(active_lps)
        lp_surplus_income = sol["lp_surplus_income"]

        worst_lp = None
        worst_margin = float("inf")

        for lp in active_lps:
            C = float(lp.get("capitalUSD", 0.0))
            if C <= 0:
                continue

            w = C / total_cap if total_cap > 0 else 0.0
            net_i = w * lp_surplus_income

            net_apr = (net_i / C) * (seconds_per_year / bin_seconds)
            floor_apr = float(lp.get("floorAPR", 0.0))
            margin = net_apr - floor_apr

            if margin < worst_margin:
                worst_margin = margin
                worst_lp = lp

        # Fixed-point condition: all LPs satisfy floors
        if worst_margin >= 0 or opts.get("ignoreMin", False):
            break

        # Remove the LP that violates the constraint the most
        active_lps = [lp for lp in active_lps if lp is not worst_lp]

    sol["total_count_lps"] = len(inst.get("lps", []))
    #sol["total_count_active_lps"] = len(active_lps)
    sol["dropped_count_lps"] = len(inst.get("lps", [])) - len(active_lps)
    sol["total_cap_original_lps"] = sum_capital(inst.get("lps", []))
    sol["total_cap_active_lps"] = sum_capital(active_lps)
    #sol["dropped_volume_lps"] = [lp for lp in inst.get("lps", []) if lp not in active_lps]
    sol["lp_net"] = lp_surplus_income/(sum_capital(active_lps)) if sum_capital(active_lps) > 0 else 0.0 
    #* (seconds_per_year / bin_seconds)
    
    # return check (can be removed in production)
    sol["return_check"] = sol["income_check"]/(sum_capital(active_lps)) if sum_capital(active_lps) > 0 else 0.0

    # --- measure full fixed-point solve time
    solve_time_ms = (time.perf_counter() - t_fp_start) * 1000.0
    sol["solve_time_ms"] = solve_time_ms
    return sol

def main():
    inst = json.load(sys.stdin)

    time_limit = inst.get("timeLimit", None)
    opts       = inst.get("opts", {})

    price_grid = inst.get("price_grid", None)
    fee_grid   = inst.get("fee_grid", None)

    # --------------------------------------------------
    # Mode A: single-shot (used by smoke tests)
    # --------------------------------------------------
    if not price_grid and not fee_grid:
        fee = float(inst.get("fee", 0.0))
        sol = solve_with_lp_fixed_point(inst, fee, time_limit, opts)

        if sol is None:
            print(json.dumps({"status": "INFEASIBLE"}))
        else:
            sol["status"] = "OPTIMAL"
            print(json.dumps(sol))
        return

    # --------------------------------------------------
    # Mode B: sweep (used by orchestrator)
    # --------------------------------------------------
    best_sol = None
    best_obj = float("-inf")

    t_sweep_start = time.perf_counter()

    for fee in fee_grid:
        for P in price_grid:
            inst_try = deepcopy(inst)
            inst_try["fee"] = fee
            inst_try["price"] = P

            sol = solve_with_lp_fixed_point(inst_try, fee, time_limit, opts)
            if sol is None:
                continue

            obj = sol.get("protocol_objective", float("-inf"))
            if obj > best_obj:
                best_obj = obj
                best_sol = sol

    total_sweep_time_ms = (time.perf_counter() - t_sweep_start) * 1000.0

    if best_sol is None:
        print(json.dumps({"status": "INFEASIBLE"}))
        return

    best_sol["status"] = "OPTIMAL"
    best_sol["total_sweep_time_ms"] = total_sweep_time_ms
    print(json.dumps(best_sol))

if __name__ == "__main__":
    main()
