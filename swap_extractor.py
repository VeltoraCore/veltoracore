# swap_extract# swap_extractor.py
import pandas as pd
import numpy as np
from web3 import Web3

V2_PAIR = Web3.to_checksum_address("0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc")

V3_POOLS = [
    ("0.05%", Web3.to_checksum_address("0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640")),
    ("0.30%", Web3.to_checksum_address("0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8")),
]

V2_SWAP_TOPIC = Web3.keccak(
    text="Swap(address,uint256,uint256,uint256,uint256,address)"
).hex()

V3_SWAP_TOPIC = Web3.keccak(
    text="Swap(address,address,int256,int256,uint160,uint128,int24)"
).hex()

if not V2_SWAP_TOPIC.startswith("0x"):
    V2_SWAP_TOPIC = "0x" + V2_SWAP_TOPIC

if not V3_SWAP_TOPIC.startswith("0x"):
    V3_SWAP_TOPIC = "0x" + V3_SWAP_TOPIC

MIN_ETH_THRESHOLD = 0.001  # 0.001 ETH (~$2–3) avoiding garbage from low transactions

def safe_price(usdc_delta, eth_delta):
    if eth_delta == 0:
        return None
    return abs(usdc_delta / eth_delta)


def extract_swaps(w3, start_block, end_block):

    rows = []

    for block in range(start_block, end_block + 1):

        block_data = w3.eth.get_block(block)
        timestamp = block_data.timestamp

        # -----------------------
        # V2 swaps
        # -----------------------
        v2_logs = w3.eth.get_logs({
            "fromBlock": block,
            "toBlock": block,
            "address": V2_PAIR,
            "topics": [V2_SWAP_TOPIC],
        })

        for log in v2_logs:

            raw_data = log["data"]
            data = Web3.to_bytes(hexstr=raw_data) if isinstance(raw_data, str) else raw_data

            amount0In  = int.from_bytes(data[0:32], "big")
            amount1In  = int.from_bytes(data[32:64], "big")
            amount0Out = int.from_bytes(data[64:96], "big")
            amount1Out = int.from_bytes(data[96:128], "big")

            # token0 = USDC, token1 = WETH
            usdc_delta = amount0In - amount0Out
            eth_delta  = amount1In - amount1Out

            eth_amount = abs(eth_delta) / 1e18
            if eth_amount < MIN_ETH_THRESHOLD:
                continue

            usdc_amount = abs(usdc_delta) / 1e6

            price = usdc_amount / eth_amount if eth_amount > 0 else None


            rows.append({
                "block": block,
                "timestamp": timestamp,
                "pool": "v2",
                "eth_amount": eth_amount,
                "usdc_amount": usdc_amount,
                "price": price,
                "direction": "buy" if eth_delta > 0 else "sell",
                "tx_hash": log["transactionHash"].hex()
            })

        # -----------------------
        # V3 swaps (all fee tiers)
        # -----------------------
        for fee_label, pool_address in V3_POOLS:

            v3_logs = w3.eth.get_logs({
                "fromBlock": block,
                "toBlock": block,
                "address": pool_address,
                "topics": [V3_SWAP_TOPIC],
            })

            for log in v3_logs:

                raw_data = log["data"]
                data = Web3.to_bytes(hexstr=raw_data) if isinstance(raw_data, str) else raw_data

                amount0 = int.from_bytes(data[0:32], "big", signed=True)
                amount1 = int.from_bytes(data[32:64], "big", signed=True)

                # token0 = USDC, token1 = WETH
                usdc_delta = amount0
                eth_delta  = amount1

                eth_amount = abs(eth_delta) / 1e18
                if eth_amount < MIN_ETH_THRESHOLD:
                    continue

                usdc_amount = abs(usdc_delta) / 1e6

                price = usdc_amount / eth_amount if eth_amount > 0 else None

                rows.append({
                    "block": block,
                    "timestamp": timestamp,
                    "pool": f"v3_{fee_label}",
                    "eth_amount": eth_amount,
                    "usdc_amount": usdc_amount,
                    "price": price,
                    "direction": "buy" if eth_delta > 0 else "sell",
                    "tx_hash": log["transactionHash"].hex()
                })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # -----------------------------------------
    # Clean invalid price rows
    # -----------------------------------------
    df = df[df["price"].notna()]
    df = df[df["price"] > 0]

    # -----------------------------------------
    # Block-level price statistics
    # -----------------------------------------
    block_stats = df.groupby("block")["price"].agg(
        block_price_min="min",
        block_price_max="max",
        block_price_mean="mean",
        block_price_std="std"
    ).reset_index()

    df = df.merge(block_stats, on="block", how="left")

    # -----------------------------------------
    # Block dispersion
    # -----------------------------------------
    df["block_price_range"] = (
        df["block_price_max"] - df["block_price_min"]
    )

    df["block_relative_range"] = (
        df["block_price_range"] / df["block_price_mean"]
    )

    # -----------------------------------------
    # Slippage vs block mean
    # -----------------------------------------
    df["block_slippage"] = (
        (df["price"] - df["block_price_mean"]) / df["block_price_mean"]
    )

    # -----------------------------------------
    # Intra-block rolling slippage
    # -----------------------------------------
    df = df.sort_values(["block", "timestamp"])

    df["prev_price"] = df.groupby("block")["price"].shift(1)

    df["local_slippage"] = (
        (df["price"] - df["prev_price"]) / df["prev_price"]
    )

    df["local_slippage"] = df["local_slippage"].replace([np.inf, -np.inf], np.nan)

    return df.reset_index(drop=True)
