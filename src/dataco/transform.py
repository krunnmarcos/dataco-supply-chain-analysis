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


STAR_DIR = ROOT / 'data' / 'processed' / 'star'


def _dim(df: pd.DataFrame, cols: dict, key: str) -> tuple[pd.DataFrame, pd.Series]:
    """Distinct rows of `cols` (source -> target name) with a surrogate key; returns (dim, key per fact row)."""
    src = list(cols)
    dim = df[src].astype(str).drop_duplicates().sort_values(src).reset_index(drop=True).rename(columns=cols)
    dim.insert(0, key, range(1, len(dim) + 1))
    fk = df[src].astype(str).merge(dim.rename(columns={v: k for k, v in cols.items()}), on=src, how='left')[key]
    return dim, fk.to_numpy()


def build_star(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Star schema for Power BI: one fact (order item grain) + dimensions. Column names in Portuguese for the report."""
    origem, origem_fk = _dim(df, {'Customer City': 'Cidade Saída', 'Customer State': 'Estado Saída',
                                  'Customer Country': 'País Saída'}, 'Saída Id')
    coords = df.groupby(origem_fk)[['Latitude', 'Longitude']].mean()
    origem = origem.join(coords, on='Saída Id')
    origem['Local Saída'] = origem['Cidade Saída'] + ', ' + origem['Estado Saída']

    destino, destino_fk = _dim(df, {'Order City': 'Cidade Entrega', 'Order State': 'Estado Entrega',
                                    'Order Country': 'País Entrega', 'Order Region': 'Região',
                                    'Market': 'Mercado'}, 'Entrega Id')
    destino['Local Entrega'] = destino['Cidade Entrega'] + ', ' + destino['País Entrega']

    sched = df.groupby('Shipping Mode', observed=True)['Days for shipment (scheduled)'].first()
    tipo = pd.DataFrame({'Modo Envio': ['Same Day', 'First Class', 'Second Class', 'Standard Class']})
    tipo.insert(0, 'Tipo Entrega Id', range(1, 5))
    tipo['Prazo (dias)'] = tipo['Modo Envio'].map(sched).astype('int64')
    tipo_fk = df['Shipping Mode'].astype(str).map(tipo.set_index('Modo Envio')['Tipo Entrega Id'])

    categoria = (df[['Category Id', 'Category Name', 'Department Id', 'Department Name']].drop_duplicates('Category Id')
                 .rename(columns={'Category Id': 'Categoria Id', 'Category Name': 'Categoria',
                                  'Department Id': 'Departamento Id', 'Department Name': 'Departamento'})
                 .astype({'Categoria': str, 'Departamento': str}).sort_values('Categoria Id'))
    produto = (df[['Product Card Id', 'Product Name', 'Product Price']].drop_duplicates('Product Card Id')
               .rename(columns={'Product Card Id': 'Produto Id', 'Product Name': 'Produto', 'Product Price': 'Preço'})
               .astype({'Produto': str}).sort_values('Produto Id'))
    produto['Produto'] = produto['Produto'].str.strip()
    cliente = (df.drop_duplicates('Customer Id')
               .assign(Cliente=lambda d: d['Customer Fname'].fillna('') + ' ' + d['Customer Lname'].fillna('')
                       + ' #' + d['Customer Id'].astype(str))
               [['Customer Id', 'Cliente', 'Customer Segment', 'Customer City', 'Customer State', 'Customer Country']]
               .rename(columns={'Customer Id': 'Cliente Id', 'Customer Segment': 'Segmento', 'Customer City': 'Cidade',
                                'Customer State': 'Estado', 'Customer Country': 'País'})
               .astype({c: str for c in ['Segmento', 'Cidade', 'Estado', 'País']}).sort_values('Cliente Id'))

    real, prev = df['Days for shipping (real)'], df['Days for shipment (scheduled)']
    od = df['order date (DateOrders)']
    fato = pd.DataFrame({
        'Item Id': df['Order Item Id'], 'Pedido Id': df['Order Id'],
        'Data Pedido': od.dt.normalize(), 'Data Hora Pedido': od, 'Hora Pedido': od.dt.hour,
        'Data Entrega': df['shipping date (DateOrders)'],
        'Categoria Id': df['Category Id'], 'Produto Id': df['Product Card Id'], 'Cliente Id': df['Customer Id'],
        'Saída Id': origem_fk, 'Entrega Id': destino_fk, 'Tipo Entrega Id': tipo_fk.to_numpy(),
        'Dias Reais': real, 'Dias Previstos': prev, 'Dias Atraso': (real - prev).clip(lower=0),
        'Atrasado': df['Late_delivery_risk'].astype('int64'),
        'Status Entrega': df['Delivery Status'].astype(str), 'Status Pedido': df['Order Status'].astype(str),
        'Tipo Pagamento': df['Type'].astype(str),
        'Quantidade': df['Order Item Quantity'], 'Preço Unitário': df['Order Item Product Price'],
        'Venda Bruta': df['Sales'], 'Desconto': df['Order Item Discount'], 'Taxa Desconto': df['Order Item Discount Rate'],
        'Faturamento': df['Order Item Total'], 'Lucro': df['Benefit per order'], 'Margem Item': df['Order Item Profit Ratio'],
    })
    star = {'fVendas': fato, 'dCategoria': categoria, 'dProduto': produto, 'dCliente': cliente,
            'dLocalSaida': origem, 'dLocalEntrega': destino, 'dTipoEntrega': tipo}
    _validate_star(star)
    return star


def _validate_star(star: dict[str, pd.DataFrame]) -> None:
    f = star['fVendas']
    links = {'dCategoria': 'Categoria Id', 'dProduto': 'Produto Id', 'dCliente': 'Cliente Id',
             'dLocalSaida': 'Saída Id', 'dLocalEntrega': 'Entrega Id', 'dTipoEntrega': 'Tipo Entrega Id'}
    for dim, key in links.items():
        assert star[dim][key].is_unique, f'{dim}.{key} not unique'
        assert f[key].notna().all() and f[key].isin(star[dim][key]).all(), f'fVendas.{key} has orphans vs {dim}'
    assert f['Item Id'].is_unique


def export_star(df: pd.DataFrame, folder: Path | str = STAR_DIR) -> Path:
    folder = Path(folder)
    for name, table in build_star(df).items():
        export_parquet(table, folder / f'{name}.parquet')
    return folder


if __name__ == '__main__':
    df = load_dataco()
    out = export_parquet(df)
    print(f'{out} written: {pd.read_parquet(out).shape}')
    star = export_star(df)
    for p in sorted(star.glob('*.parquet')):
        print(f'{p.name}: {pd.read_parquet(p).shape}')
