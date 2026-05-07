# VeltoraCore -- Historical & Simulation Engine

## 1. System Requirements

-   Python 3.10+ (recommended 3.11 or 3.12)
-   Linux / macOS / Windows (Linux recommended)
-   Alchemy API Key (Ethereum Mainnet access)
-   Internet connection (for historical extraction phase)

------------------------------------------------------------------------

## 2. Python Installation

Check version:

    python3 --version

If not installed (Ubuntu):

    sudo apt update
    sudo apt install python3 python3-venv python3-pip

------------------------------------------------------------------------

## 3. Create Virtual Environment

From project root:

    python3 -m venv .venv

Activate:

Linux / macOS: source .venv/bin/activate

Windows: .venv`\Scripts`{=tex}`\activate`{=tex}

------------------------------------------------------------------------

## 4. Install Dependencies

If requirements.txt exists:

    pip install -r requirements.txt

Otherwise:

    pip install pandas numpy pyarrow requests web3 tqdm
    pip install gurobipy

------------------------------------------------------------------------

## 5. Configure Alchemy API Key

Linux / macOS:

    export ALCHEMY_KEY="your_alchemy_key_here"

Windows (PowerShell):

    setx ALCHEMY_KEY "your_alchemy_key_here"

Restart terminal after Windows setx.

Verify:

    echo $ALCHEMY_KEY

------------------------------------------------------------------------

## 6. Project Execution Flow

There are two main phases:

1.  Historical Data Extraction\
2.  Simulation / VeltoraCore Engine

------------------------------------------------------------------------

## 7. config.py -- Parameter Explanation

### Historical Block Configuration

    START_BLOCK = 19000000
    END_BLOCK = 19010000
    BIN_SIZE_BLOCKS = 50

-   START_BLOCK → first Ethereum block to analyze
-   END_BLOCK → last block
-   BIN_SIZE_BLOCKS → size of execution bins

Ethereum produces \~7200 blocks/day.

------------------------------------------------------------------------

### Simulation Parameters

    INITIAL_PRICE = 2000
    BIN_SECONDS = 600
    SECONDS_PER_YEAR = 31536000

-   INITIAL_PRICE → used only in stochastic mode
-   Historical mode uses first-bin VWAP
-   BIN_SECONDS → duration of each bin
-   SECONDS_PER_YEAR → annualization diagnostics

------------------------------------------------------------------------

### Fee Parameters

    FEE_UNISWAP_V2 = 0.003
    FEE_UNISWAP_V3_005 = 0.0005
    FEE_UNISWAP_V3_03 = 0.003

Used for fee reconstruction and comparisons.

------------------------------------------------------------------------

### Liquidity Drift Filter (Historical Mode)

    LIQ_DRIFT_THRESHOLD = 0.01
    LIQ_PRICE_MULTIPLIER = 2.0

Bins are excluded if liquidity movement exceeds threshold relative to
price movement.

------------------------------------------------------------------------

## 8. Step 1 -- Run Historical Pipeline

This downloads and processes:

-   swaps
-   liquidity snapshots
-   bin construction
-   Uniswap LP returns

Run:

    python historical_pipeline.py

Generated files:

    historical_data/
        swaps.parquet
        liquidity.parquet
        bins.parquet
        uniswap_bins.parquet

⚠ Slow and API-heavy.\
If data already exists, do NOT rerun.

------------------------------------------------------------------------

## 9. Step 2 -- Run Simulation (Historical Mode)

Ensure in config.py:

    RUN_HISTORICAL = True

Then run:

    python run_multibin.py

This will:

-   Build solver instances
-   Run VeltoraCore
-   Compare against Uniswap
-   Output summary CSV

------------------------------------------------------------------------

## 10. When to Rerun Historical Pipeline

Re-run ONLY if:

-   START_BLOCK changes
-   END_BLOCK changes
-   BIN_SIZE_BLOCKS changes

If adjusting solver parameters only:

    python run_multibin.py

------------------------------------------------------------------------

## 11. Output Files

After simulation:

    summary_HISTORICAL_*.csv

Containing:

-   Per-bin returns
-   Cumulative returns
-   VeltoraCore vs Uniswap comparison
-   Solver metrics

------------------------------------------------------------------------

## 12. Typical 7-Day Workflow

    source .venv/bin/activate
    export ALCHEMY_KEY="..."
    python historical_pipeline.py
    python run_multibin.py

------------------------------------------------------------------------

## 13. Notes

-   First bin is calibration only
-   Abnormal liquidity bins are filtered
-   Cumulative returns are recomputed locally
-   Net LP inflows/outflows assumed second-order within bins

------------------------------------------------------------------------

VeltoraCore -- Mechanism-Level Liquidity Optimization Framework
