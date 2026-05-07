# historical_backtest/alchemy_client.py

from web3 import Web3
from typing import List, Dict, Any, Optional
import time


class AlchemyClient:
    """
    Thin RPC wrapper for historical Ethereum data retrieval.
    Designed for VeltoraCore backtesting.
    """

    def __init__(self, api_key: str, network: str = "mainnet"):
        self.api_key = api_key
        self.network = network

        self.w3 = Web3(Web3.HTTPProvider(
            f"https://eth-{network}.g.alchemy.com/v2/{api_key}"
        ))

        if not self.w3.is_connected():
            raise Exception("Failed to connect to Alchemy")

    # -------------------------------------------------------
    # Basic Block Retrieval
    # -------------------------------------------------------

    def get_block(self, block_number: int) -> Dict[str, Any]:
        """
        Returns full block with transactions included.
        """
        return self.w3.eth.get_block(
            block_number,
            full_transactions=True
        )

    def get_block_timestamp(self, block_number: int) -> int:
        return self.w3.eth.get_block(block_number).timestamp

    # -------------------------------------------------------
    # Transaction / Receipt
    # -------------------------------------------------------

    def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        return self.w3.eth.get_transaction_receipt(tx_hash)

    # -------------------------------------------------------
    # Range Retrieval
    # -------------------------------------------------------

    def get_blocks_in_range(
        self,
        start_block: int,
        end_block: int,
        sleep: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Sequentially retrieves blocks.
        Safe for large ranges.
        """
        blocks = []

        for block_number in range(start_block, end_block + 1):
            block = self.get_block(block_number)
            blocks.append(block)

            if sleep > 0:
                time.sleep(sleep)

        return blocks

    # -------------------------------------------------------
    # Router Transaction Filter
    # -------------------------------------------------------

    @staticmethod
    def filter_transactions_by_to(
        block: Dict[str, Any],
        addresses: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Filters block transactions by destination address.
        """
        addr_set = {a.lower() for a in addresses}

        filtered = []
        for tx in block.transactions:
            if tx.to and tx.to.lower() in addr_set:
                filtered.append(tx)

        return filtered
