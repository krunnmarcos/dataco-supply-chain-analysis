"""Shallow decision tree for late-delivery probability, using only data known when the order is placed."""
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.tree import DecisionTreeClassifier, export_text

TARGET = 'Late_delivery_risk'
CATEGORICAL = ['Shipping Mode', 'Type', 'Market', 'Customer Segment']
NUMERIC = ['order_hour', 'order_weekday']
SPLIT_DATE = '2017-07-01'


def order_features(df: pd.DataFrame) -> pd.DataFrame:
    """One row per shipped order (canceled orders never deliver, so they carry no late signal)."""
    orders = df.drop_duplicates('Order Id')
    orders = orders[orders['Delivery Status'] != 'Shipping canceled']
    od = orders['order date (DateOrders)']
    return orders.assign(order_hour=od.dt.hour, order_weekday=od.dt.day_of_week)


def design_matrix(orders: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([orders[NUMERIC], pd.get_dummies(orders[CATEGORICAL].astype(str), prefix_sep='=')], axis=1)


def train(df: pd.DataFrame, max_depth: int = 3, min_samples_leaf: int = 500,
          min_impurity_decrease: float = 1e-4) -> dict:
    """min_impurity_decrease prunes splits worth < ~1 p.p. of late rate (e.g. Market/Type inside Standard Class)."""
    orders = order_features(df)
    X, y = design_matrix(orders), orders[TARGET]
    is_train = orders['order date (DateOrders)'] < SPLIT_DATE

    tree = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_samples_leaf,
                                  min_impurity_decrease=min_impurity_decrease, random_state=0)
    tree.fit(X[is_train], y[is_train])
    p_tree = tree.predict_proba(X[~is_train])[:, 1]

    # baseline: historical late rate per shipping mode
    rate = y[is_train].groupby(orders.loc[is_train, 'Shipping Mode'], observed=True).mean()
    p_base = orders.loc[~is_train, 'Shipping Mode'].map(rate).astype(float)

    y_test = y[~is_train]
    metrics = pd.DataFrame({
        'AUC': [roc_auc_score(y_test, p_base), roc_auc_score(y_test, p_tree)],
        'Brier': [brier_score_loss(y_test, p_base), brier_score_loss(y_test, p_tree)],
    }, index=['baseline (modo de envio)', f'árvore ({tree.get_n_leaves()} folhas)'])

    # calibration: predicted probability per leaf vs observed late rate in the test period
    leaves = pd.DataFrame({'folha': tree.apply(X[~is_train]), 'p_prevista': p_tree, 'atrasou': y_test.to_numpy()})
    calibration = leaves.groupby('folha').agg(pedidos=('atrasou', 'size'), p_prevista=('p_prevista', 'first'),
                                              taxa_real=('atrasou', 'mean'))

    return {'tree': tree, 'features': list(X.columns), 'metrics': metrics, 'calibration': calibration,
            'rules': export_text(tree, feature_names=list(X.columns), show_weights=True),
            'n_train': int(is_train.sum()), 'n_test': int((~is_train).sum())}


if __name__ == '__main__':
    from dataco.transform import load_dataco
    result = train(load_dataco())
    print(result['metrics'], result['rules'], sep='\n\n')
