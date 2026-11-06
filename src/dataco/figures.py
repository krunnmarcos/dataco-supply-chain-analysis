"""Generate the report figures in docs/figures/ (python -m dataco.figures from src/)."""
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from dataco.transform import ROOT, load_dataco

OUT = ROOT / 'docs' / 'figures'
INK, MUTED, GRID, NEUTRAL = '#0b0b0b', '#52514e', '#e4e3df', '#b8b7b0'
BLUE, ORANGE, RED, GREEN = '#2a78d6', '#eb6834', '#e34948', '#008300'
REAL, SCHED = 'Days for shipping (real)', 'Days for shipment (scheduled)'

plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': MUTED,
                     'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'text.color': INK, 'font.size': 9, 'figure.dpi': 150})


def _grid(ax, axis='y'):
    ax.grid(axis=axis, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def _save(fig, name):
    fig.savefig(OUT / name, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def prazos_por_modo(shipped):
    dist = pd.crosstab(shipped['Shipping Mode'], shipped[REAL], normalize='index')
    sched = shipped.groupby('Shipping Mode', observed=True)[SCHED].first()
    fig, axes = plt.subplots(1, len(dist), figsize=(12, 3.2), sharey=True)
    for ax, (mode, row) in zip(axes, dist.iterrows()):
        s = sched[mode]
        ax.bar(row.index, row.values, width=0.7, color=[RED if d > s else NEUTRAL for d in row.index])
        ax.axvline(s + 0.5, color=MUTED, lw=1, ls='--')
        ax.set_title(f'{mode}\nprazo {s} dia(s) · {row[row.index > s].sum():.0%} atrasam', loc='left', fontsize=10)
        ax.set_xticks(range(7))
        _grid(ax)
    axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(1))
    fig.suptitle('Dias reais de envio por modo: First Class sempre leva 2 dias; Second Class leva o mesmo que Standard',
                 x=0.01, ha='left', fontsize=11)
    fig.supxlabel('dias reais de envio (cinza = dentro do prazo, vermelho = atrasado, tracejado = prazo)',
                  fontsize=9, color=MUTED)
    fig.tight_layout()
    _save(fig, '01_prazos_por_modo.png')


def same_day_por_hora(shipped):
    sd = shipped[shipped['Shipping Mode'] == 'Same Day']
    rate = sd.groupby(sd['order date (DateOrders)'].dt.hour)['Late_delivery_risk'].mean()
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.bar(rate.index, rate.values, width=0.7, color=[RED if h >= 12 else NEUTRAL for h in rate.index])
    ax.axvline(11.5, color=MUTED, lw=1, ls='--')
    ax.text(11.6, 1.02, '12h', color=MUTED)
    ax.set_xticks(range(24))
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1))
    ax.set_xlabel('hora do pedido')
    ax.set_title('Same Day (pedidos enviados): antes das 12h nunca atrasam; a partir das 12h, todos atrasam',
                 loc='left', fontsize=11)
    _grid(ax)
    fig.tight_layout()
    _save(fig, '02_same_day_por_hora.png')


def impacto_acoes(orders):
    """Late rate (all orders) under each cumulative SLA change, simulated on history."""
    shipped = orders['Delivery Status'] != 'Shipping canceled'
    mode, hour = orders['Shipping Mode'], orders['order date (DateOrders)'].dt.hour
    sched = orders[SCHED].copy()
    # rate over shipped orders: canceled/fraud orders never ship, so they cannot be late or on time
    late = lambda s: (orders[REAL] > s)[shipped].mean()
    steps = {'Hoje': late(sched)}
    sched = sched + ((mode == 'Same Day') & (hour >= 12)).astype(int)
    steps['+ Same Day: +1 dia após 12h'] = late(sched)
    sched = sched.where(mode != 'First Class', 2)
    steps['+ First Class: prazo 2 dias'] = late(sched)
    steps['+ Second Class: prazo 4 dias'] = late(sched.where(mode != 'Second Class', 4))
    steps['+ Second Class: prazo 6 dias (alternativa)'] = late(sched.where(mode != 'Second Class', 6))
    # shortcut: late() recomputes from real vs scheduled days; matches Late_delivery_risk on today's SLA (asserted below)
    assert abs(steps['Hoje'] - orders.loc[shipped, 'Late_delivery_risk'].mean()) < 1e-9

    s = pd.Series(steps)
    fig, ax = plt.subplots(figsize=(9, 3))
    y = range(len(s))
    ax.barh(y, s.values, height=0.6, color=[NEUTRAL] + [BLUE] * (len(s) - 2) + [NEUTRAL])
    for i, v in enumerate(s.values):
        ax.text(v + 0.01, i, f'{v:.1%}', va='center', color=INK)
    ax.set_yticks(list(y), s.index)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.65)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
    ax.set_title('Atraso registrado se o prazo prometido refletir a operação real (simulação no histórico)',
                 loc='left', fontsize=11)
    _grid(ax, 'x')
    fig.tight_layout()
    _save(fig, '03_impacto_acoes.png')
    return s


def pareto(values, title, color, name, cutoff=0.95):
    s = values.sort_values(ascending=False)
    share = s / s.sum()
    keep = share.cumsum().shift(fill_value=0) < cutoff
    share = pd.concat([share[keep], pd.Series({f'Outras ({(~keep).sum()})': share[~keep].sum()})])
    cum = share.cumsum()
    k = int((cum < 0.8).sum()) + 1
    y = range(len(share))
    fig, ax = plt.subplots(figsize=(9, 0.3 * len(share) + 1.2))
    ax.barh(y, share, height=0.6, color=[color if i < k else NEUTRAL for i in y], label='participação')
    ax.plot(cum, y, color=MUTED, lw=1.5, marker='o', ms=3, label='acumulado')
    ax.axvline(0.8, color=MUTED, lw=1, ls='--')
    for i, v in enumerate(share):
        if i < k:
            ax.text(1.03, i, f'{v:.0%}', va='center', color=MUTED, fontsize=8)
    ax.set_yticks(list(y), share.index)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
    ax.set_title(f'{k} categorias concentram 80% do {title} (${s.sum() / 1e6:,.2f}M)', loc='left', fontsize=11)
    ax.legend(loc='lower right', frameon=False)
    _grid(ax, 'x')
    fig.tight_layout()
    _save(fig, name)


def pedidos_e_atraso_mes(orders):
    m = orders.set_index('order date (DateOrders)').resample('MS').agg(
        pedidos=('Order Id', 'size'), late_rate=('Late_delivery_risk', 'mean'))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    a1.plot(m.index, m['pedidos'], color=BLUE, lw=2)
    a1.set_ylim(0, m['pedidos'].max() * 1.15)
    a1.set_title('Pedidos enviados por mês', loc='left', fontsize=10)
    a2.plot(m.index, m['late_rate'], color=MUTED, lw=2)
    a2.axhline(orders['Late_delivery_risk'].mean(), color=MUTED, lw=1, ls='--')
    a2.set_ylim(0, 1)
    a2.yaxis.set_major_formatter(mtick.PercentFormatter(1))
    a2.set_title('Taxa de atraso por mês, pedidos enviados (tracejado = média)', loc='left', fontsize=10)
    for ax in (a1, a2):
        _grid(ax)
    fig.suptitle('O volume sobe a partir de out/2017 e a taxa de atraso não muda: o atraso não vem de sobrecarga',
                 x=0.01, ha='left', fontsize=11)
    fig.tight_layout()
    _save(fig, '06_pedidos_atraso_mes.png')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_dataco()
    orders = df.drop_duplicates('Order Id')
    shipped = orders[orders['Delivery Status'] != 'Shipping canceled']
    prazos_por_modo(shipped)
    same_day_por_hora(shipped)
    print(impacto_acoes(orders).round(3))
    valid = df[~df['Order Status'].isin(['CANCELED', 'SUSPECTED_FRAUD'])]  # never shipped: not real revenue
    b = valid['Benefit per order']
    by_cat = valid.assign(lucro=b.clip(lower=0), prejuizo=-b.clip(upper=0)).groupby('Category Name', observed=True)
    pareto(by_cat['lucro'].sum(), 'lucro bruto', BLUE, '04_pareto_lucro.png')
    pareto(by_cat['prejuizo'].sum(), 'prejuízo', ORANGE, '05_pareto_prejuizo.png')
    pedidos_e_atraso_mes(shipped)


if __name__ == '__main__':
    main()
