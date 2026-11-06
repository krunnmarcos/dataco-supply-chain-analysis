"""Load the original DataCo Supply Chain CSV (Kaggle) and return a typed DataFrame."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_CSV = ROOT / 'data' / 'raw' / 'DataCoSupplyChainDataset.csv'
PARQUET = ROOT / 'data' / 'processed' / 'dataco.parquet'

MONEY = ['Benefit per order', 'Sales per customer', 'Order Item Discount', 'Order Item Product Price',
         'Order Item Profit Ratio', 'Sales', 'Order Item Total', 'Order Profit Per Order', 'Product Price']
DATES = ['order date (DateOrders)', 'shipping date (DateOrders)']
ZIPS = ['Customer Zipcode', 'Order Zipcode']
DROP = ['Product Image']

DTYPES = {
    'category': ['Type', 'Delivery Status', 'Category Name', 'Customer City', 'Customer Country',
                 'Customer Segment', 'Customer State', 'Department Name', 'Market', 'Order City',
                 'Order Country', 'Order Region', 'Order State', 'Order Status', 'Product Name', 'Shipping Mode'],
    'string': ['Customer Email', 'Customer Fname', 'Customer Lname', 'Customer Password',
               'Customer Street', 'Product Description'],
    'int64': ['Days for shipping (real)', 'Days for shipment (scheduled)', 'Category Id', 'Customer Id',
              'Department Id', 'Order Customer Id', 'Order Id', 'Order Item Cardprod Id', 'Order Item Id',
              'Order Item Quantity', 'Product Card Id', 'Product Category Id'],
    'bool': ['Late_delivery_risk', 'Product Status'],
    'float64': MONEY + ['Order Item Discount Rate', 'Latitude', 'Longitude'],
}


def load_dataco(path: Path | str = RAW_CSV) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding='latin-1')  # Kaggle file is not UTF-8
    raw.columns = raw.columns.str.strip()
    df = raw.drop(columns=DROP)

    mapped = [c for cols in DTYPES.values() for c in cols] + DATES + ZIPS
    assert sorted(mapped) == sorted(df.columns), f'unmapped/missing columns: {set(mapped) ^ set(df.columns)}'

    for c in DATES:
        df[c] = pd.to_datetime(df[c], format='%m/%d/%Y %H:%M')
    for c in ZIPS:
        df[c] = df[c].astype('Int64').astype('string').str.zfill(5)
    # astype(str): Customer State has 2 numeric zipcodes in the source
    df[DTYPES['category']] = df[DTYPES['category']].astype(str).astype('category')
    df[DTYPES['string']] = df[DTYPES['string']].astype('string')
    df[DTYPES['int64']] = df[DTYPES['int64']].astype('int64')
    df[DTYPES['bool']] = df[DTYPES['bool']].astype(bool)
    df[DTYPES['float64']] = df[DTYPES['float64']].astype('float64')

    _validate(df)
    return df


def _validate(df: pd.DataFrame) -> None:
    def close(a, b):
        return np.isclose(a, b, rtol=1e-3, atol=0.02).all()

    assert close(df['Product Price'], df['Order Item Product Price'])
    assert close(df['Sales'], df['Product Price'] * df['Order Item Quantity'])
    assert close(df['Sales per customer'], df['Order Item Total'])
    assert close(df['Benefit per order'], df['Order Profit Per Order'])
    days = (df[DATES[1]].dt.normalize() - df[DATES[0]].dt.normalize()).dt.days
    assert (days == df['Days for shipping (real)']).all()


def export_parquet(df: pd.DataFrame, path: Path | str = PARQUET) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # ms timestamps: safest precision for the Power BI Parquet connector
    df.to_parquet(path, index=False, engine='pyarrow', coerce_timestamps='ms', allow_truncated_timestamps=True)
    return path


if __name__ == '__main__':
    out = export_parquet(load_dataco())
    print(f'{out} written: {pd.read_parquet(out).shape}')
