# historical_pipeline.py

import os
import time
import logging
from alchemy_client import AlchemyClient

from swap_extractor import extract_swaps
from liquidity_extractor import extract_liquidity_at_blocks
from bin_builder import build_bins
from failed_tx_extractor import extract_failed_transactions
from tolerance_inference import infer_tolerance
from uniswap_metrics_builder import compute_bin_uniswap_metrics

from config import *

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def main():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    logger.info("Starting full historical pipeline")
    logger.info(f"Block range: {START_BLOCK} → {END_BLOCK}")

    client = AlchemyClient(os.getenv("ALCHEMY_KEY"))
    w3 = client.w3

    # ---------------------------------------------------
    # 1. SWAPS
    # ---------------------------------------------------
    logger.info("Extracting swaps...")
    t0 = time.time()

    swaps_df = extract_swaps(w3, START_BLOCK, END_BLOCK)

    swaps_df.to_parquet(f"{OUTPUT_DIR}/swaps.parquet", engine="pyarrow", index=False)
    swaps_df.to_csv(f"{OUTPUT_DIR}/swaps.csv", index=False)

    logger.info(f"Swaps extracted: {len(swaps_df)}")
    logger.info(f"Swap extraction completed in {time.time() - t0:.2f}s")

    # ---------------------------------------------------
    # 2. BINS
    # ---------------------------------------------------
    logger.info("Building bins...")
    bins_df = build_bins(swaps_df, bin_seconds=600)

    bins_df.to_parquet(f"{OUTPUT_DIR}/bins.parquet", engine="pyarrow", index=False)
    bins_df.to_csv(f"{OUTPUT_DIR}/bins.csv", index=False)

    logger.info(f"Bins created: {len(bins_df)}")

    # ---------------------------------------------------
    # 3. LIQUIDITY
    # ---------------------------------------------------
    logger.info("Extracting liquidity at bin boundaries...")
    t1 = time.time()

    # IMPORTANT: we need both start and end blocks
    bin_start_blocks = bins_df["start_block"].tolist()
    bin_end_blocks   = bins_df["end_block"].tolist()

    # Merge and remove duplicates
    all_boundary_blocks = list(set(bin_start_blocks + bin_end_blocks))

    liquidity_df = extract_liquidity_at_blocks(w3, all_boundary_blocks)

    liquidity_df.to_parquet(f"{OUTPUT_DIR}/liquidity.parquet", engine="pyarrow", index=False)
    liquidity_df.to_csv(f"{OUTPUT_DIR}/liquidity.csv", index=False)

    logger.info(f"Liquidity extraction completed in {time.time() - t1:.2f}s")

    # ---------------------------------------------------
    # 4. FAILED TX
    # ---------------------------------------------------
    logger.info("Extracting failed router transactions...")
    t2 = time.time()

    failed_df = extract_failed_transactions(w3, START_BLOCK, END_BLOCK)

    failed_df.to_parquet(f"{OUTPUT_DIR}/failed_transactions.parquet", engine="pyarrow", index=False)
    failed_df.to_csv(f"{OUTPUT_DIR}/failed_transactions.csv", index=False)

    logger.info(f"Failed tx extraction completed in {time.time() - t2:.2f}s")

    # ---------------------------------------------------
    # 5. TOLERANCE INFERENCE
    # ---------------------------------------------------
    logger.info("Inferring tolerance per bin...")

    tolerance_df = infer_tolerance(swaps_df, failed_df, bins_df)

    tolerance_df.to_parquet(f"{OUTPUT_DIR}/tolerance_bins.parquet", engine="pyarrow", index=False)
    tolerance_df.to_csv(f"{OUTPUT_DIR}/tolerance_bins.csv", index=False)

    logger.info(f"Tolerance bins computed: {len(tolerance_df)}")

    logger.info("Full pipeline completed successfully.")

    # ---------------------------------------------------
    # 6. UNISWAP BIN METRICS
    # ---------------------------------------------------
    logger.info("Computing Uniswap bin metrics...")

    uni_metrics_df = compute_bin_uniswap_metrics(
        swaps_df,
        bins_df,
        liquidity_df
    )

    uni_metrics_df.to_parquet(f"{OUTPUT_DIR}/uniswap_bins.parquet", engine="pyarrow", index=False)
    uni_metrics_df.to_csv(f"{OUTPUT_DIR}/uniswap_bins.csv", index=False)

    logger.info(f"Uniswap metrics computed: {len(uni_metrics_df)} bins")


if __name__ == "__main__":
    main()
