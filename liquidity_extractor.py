#!/usr/bin/env python3

import pandas as pd
from web3 import Web3

# ==========================================================
# ADDRESSES
# ==========================================================

V2_PAIR = Web3.to_checksum_address(
    "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"
)

# V3 ETH/USDC pools
V3_POOL_005 = Web3.to_checksum_address(
    "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"  # 0.05%
)

V3_POOL_03 = Web3.to_checksum_address(
    "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"  # 0.3%
)

WETH = Web3.to_checksum_address(
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
)

USDC = Web3.to_checksum_address(
    "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
)

# ==========================================================
# ABIs
# ==========================================================

V2_ABI = [{
    "constant": True,
    "inputs": [],
    "name": "getReserves",
    "outputs": [
        {"name": "_reserve0", "type": "uint112"},
        {"name": "_reserve1", "type": "uint112"},
        {"name": "_blockTimestampLast", "type": "uint32"},
    ],
    "stateMutability": "view",
    "type": "function",
}]

V3_SLOT0_ABI = [{
    "inputs": [],
    "name": "slot0",
    "outputs": [
        {"name": "sqrtPriceX96", "type": "uint160"},
        {"name": "tick", "type": "int24"},
        {"name": "observationIndex", "type": "uint16"},
        {"name": "observationCardinality", "type": "uint16"},
        {"name": "observationCardinalityNext", "type": "uint16"},
        {"name": "feeProtocol", "type": "uint8"},
        {"name": "unlocked", "type": "bool"},
    ],
    "stateMutability": "view",
    "type": "function",
}]

ERC20_ABI = [{
    "constant": True,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "stateMutability": "view",
    "type": "function",
}]


# ==========================================================
# PRICE CONVERSION HELPER
# ==========================================================

def v3_price_from_slot0(sqrtPriceX96):
    """
    Convert V3 sqrtPriceX96 into USDC per ETH.
    token0 = USDC (6 decimals)
    token1 = WETH (18 decimals)
    """

    price_raw = (sqrtPriceX96 ** 2) / (2 ** 192)

    # raw = token1/token0 (WETH/USDC)
    price_eth_per_usdc = price_raw * (10**6) / (10**18)

    return 1 / price_eth_per_usdc if price_eth_per_usdc > 0 else 0.0


# ==========================================================
# MAIN EXTRACTION
# ==========================================================

def extract_liquidity_at_blocks(w3, block_list):

    v2 = w3.eth.contract(address=V2_PAIR, abi=V2_ABI)

    v3_005 = w3.eth.contract(address=V3_POOL_005, abi=V3_SLOT0_ABI)
    v3_03  = w3.eth.contract(address=V3_POOL_03, abi=V3_SLOT0_ABI)

    usdc_contract = w3.eth.contract(address=USDC, abi=ERC20_ABI)
    weth_contract = w3.eth.contract(address=WETH, abi=ERC20_ABI)

    rows = []

    for block in sorted(block_list):

        block_data = w3.eth.get_block(block)
        timestamp = block_data.timestamp

        # ---------------- V2 ----------------
        reserve0, reserve1, _ = v2.functions.getReserves().call(
            block_identifier=block
        )

        v2_usdc = reserve0 / 1e6
        v2_eth  = reserve1 / 1e18
        price_v2 = v2_usdc / v2_eth if v2_eth > 0 else 0.0

        # ---------------- V3 0.05% ----------------
        sqrt005 = v3_005.functions.slot0().call(block_identifier=block)[0]
        price_v3_005 = v3_price_from_slot0(sqrt005)

        v3_005_usdc = usdc_contract.functions.balanceOf(V3_POOL_005).call(
            block_identifier=block
        ) / 1e6

        v3_005_eth = weth_contract.functions.balanceOf(V3_POOL_005).call(
            block_identifier=block
        ) / 1e18

        # ---------------- V3 0.3% ----------------
        sqrt03 = v3_03.functions.slot0().call(block_identifier=block)[0]
        price_v3_03 = v3_price_from_slot0(sqrt03)

        v3_03_usdc = usdc_contract.functions.balanceOf(V3_POOL_03).call(
            block_identifier=block
        ) / 1e6

        v3_03_eth = weth_contract.functions.balanceOf(V3_POOL_03).call(
            block_identifier=block
        ) / 1e18

        rows.append({
            "block": block,
            "timestamp": timestamp,

            # V2
            "v2_usdc": v2_usdc,
            "v2_eth": v2_eth,
            "price_v2": price_v2,

            # V3 0.05%
            "v3_005_usdc": v3_005_usdc,
            "v3_005_eth": v3_005_eth,
            "price_v3_005": price_v3_005,

            # V3 0.3%
            "v3_03_usdc": v3_03_usdc,
            "v3_03_eth": v3_03_eth,
            "price_v3_03": price_v3_03,
        })

    return pd.DataFrame(rows)