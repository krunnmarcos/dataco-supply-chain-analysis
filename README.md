# DataCo Supply Chain Analysis

EDA, ETL and visualization of the DataCo Smart Supply Chain dataset.

## Data

The data is **not included in this repository**. Download it from Kaggle:
[DataCo Smart Supply Chain for Big Data Analysis](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis)

Place the original CSV files in `data/raw/`:

```
data/raw/DataCoSupplyChainDataset.csv
data/raw/DescriptionDataCoSupplyChain.csv
```

Use the original CSV (latin-1 encoded). Do not use an `.xlsx` version opened or saved in Excel: in non-US locales Excel drops decimal separators and swaps day/month in dates.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/jupyter lab notebooks/
```

## Project layout

```
data/raw/                     original Kaggle CSVs (not versioned)
data/processed/dataco.parquet ETL output for Power BI (not versioned)
src/dataco/transform.py       ETL: load_dataco() -> typed, validated DataFrame; export_parquet()
src/dataco/model.py           shallow decision tree for late-delivery probability
src/dataco/figures.py         generates the report figures in docs/figures/
notebooks/02_eda.ipynb        EDA: late deliveries, delay, profit and loss, Pareto, time series
notebooks/03_modelo_atraso.ipynb  model training, metrics, tree and calibration
docs/analise.md               analysis report (findings and next actions, in Portuguese)
bi/                           Power BI files
```

## Run

```bash
cd src
../.venv/bin/python -m dataco.transform   # writes data/processed/dataco.parquet
../.venv/bin/python -m dataco.model       # prints metrics and tree rules
```

In Power BI: Get Data > Parquet > `data/processed/dataco.parquet`.
