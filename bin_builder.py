# bin_builder.py

import pandas as pd
from config import *

def build_bins(swaps_df, bin_seconds=BIN_SECONDS):

    if swaps_df.empty:
        raise ValueError("Swaps dataframe is empty")

    df = swaps_df.copy()

    # Normalize timestamps
    df["bin_id"] = (df["timestamp"] // bin_seconds) * bin_seconds

    grouped = df.groupby("bin_id")

    rows = []

    for bin_id, group in grouped:

        rows.append({
            "bin_start_ts": bin_id,
            "start_block": group["block"].min(),
            "end_block": group["block"].max(),
            "num_swaps": len(group),
            "total_eth": group["eth_amount"].sum(),
            "total_usdc": group["usdc_amount"].sum(),
            "vwap": (
                (group["price"] * group["eth_amount"]).sum()
                / group["eth_amount"].sum()
                if group["eth_amount"].sum() > 0 else None
            )
        })

    bins_df = pd.DataFrame(rows).sort_values("bin_start_ts").reset_index(drop=True)

    return bins_df
