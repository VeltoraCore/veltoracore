import pandas as pd
import math


# --------------------------------------------------
# Compute pool normalized and raw returns
# --------------------------------------------------

def compute_pool_returns(start_liq, end_liq,
                         eth_col, usdc_col, price_col):

    x0 = start_liq[eth_col]
    y0 = start_liq[usdc_col]
    P0 = start_liq[price_col]

    x1 = end_liq[eth_col]
    y1 = end_liq[usdc_col]
    P1 = end_liq[price_col]

    V0 = x0 * P0 + y0
    V1 = x1 * P1 + y1

    if V0 == 0:
        return 0.0, 0.0

    # --- Raw return ---
    raw_return = (V1 / V0) - 1

    # --- Normalized return ---
    L0 = math.sqrt(x0 * y0) if x0 > 0 and y0 > 0 else 0
    L1 = math.sqrt(x1 * y1) if x1 > 0 and y1 > 0 else 0

    if L0 == 0 or L1 == 0:
        norm_return = 0.0
    else:
        norm_return = ((V1 / L1) / (V0 / L0)) - 1

    return norm_return, raw_return


# --------------------------------------------------
# Main Uniswap bin metrics
# --------------------------------------------------

def compute_bin_uniswap_metrics(swaps_df, bins_df, liquidity_df):

    results = []

    # cumulative trackers
    cum_log_norm = 0.0
    cum_simple_norm = 1.0

    cum_log_raw = 0.0
    cum_simple_raw = 1.0

    for idx, (_, bin_row) in enumerate(bins_df.iterrows()):

        start_block = bin_row["start_block"]
        end_block   = bin_row["end_block"]

        start_liq = liquidity_df[liquidity_df["block"] == start_block]
        end_liq   = liquidity_df[liquidity_df["block"] == end_block]

        if start_liq.empty or end_liq.empty:
            continue

        start_liq = start_liq.iloc[0]
        end_liq   = end_liq.iloc[0]

        # -------- V2 --------
        v2_norm, v2_raw = compute_pool_returns(
            start_liq, end_liq,
            "v2_eth", "v2_usdc", "price_v2"
        )

        # -------- V3 0.05% --------
        v3_005_norm, v3_005_raw = compute_pool_returns(
            start_liq, end_liq,
            "v3_005_eth", "v3_005_usdc", "price_v3_005"
        )

        # -------- V3 0.3% --------
        v3_03_norm, v3_03_raw = compute_pool_returns(
            start_liq, end_liq,
            "v3_03_eth", "v3_03_usdc", "price_v3_03"
        )

        # --- Liquidity weights ---
        weights = []

        for eth_col, usdc_col in [
            ("v2_eth", "v2_usdc"),
            ("v3_005_eth", "v3_005_usdc"),
            ("v3_03_eth", "v3_03_usdc"),
        ]:
            x = start_liq[eth_col]
            y = start_liq[usdc_col]
            weights.append(math.sqrt(x * y) if x > 0 and y > 0 else 0)

        total_weight = sum(weights)

        if total_weight == 0:
            continue

        # --- Weighted aggregate ---
        total_norm = (
            v2_norm     * weights[0] +
            v3_005_norm * weights[1] +
            v3_03_norm  * weights[2]
        ) / total_weight

        total_raw = (
            v2_raw     * weights[0] +
            v3_005_raw * weights[1] +
            v3_03_raw  * weights[2]
        ) / total_weight

        # ----------------------
        # Cumulative returns
        # Exclude first bin
        # ----------------------
        if idx > 0:

            if total_norm > -1:
                cum_log_norm += math.log(1 + total_norm)
            cum_simple_norm *= (1 + total_norm)

            if total_raw > -1:
                cum_log_raw += math.log(1 + total_raw)
            cum_simple_raw *= (1 + total_raw)

        results.append({
            "start_block": start_block,
            "end_block": end_block,

            # Per-bin returns
            "uni_lp_return": total_norm,
            "uni_lp_return_raw": total_raw,

            # Cumulative log
            "uni_log_cum_return": cum_log_norm,
            "uni_log_cum_return_raw": cum_log_raw,

            # Cumulative simple
            "uni_cum_simple_return": cum_simple_norm - 1,
            "uni_cum_simple_return_raw": cum_simple_raw - 1,
        })

    return pd.DataFrame(results)