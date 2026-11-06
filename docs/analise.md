# Análise DataCo Supply Chain: atrasos e lucratividade

**Resumo.** 55% dos pedidos atrasam porque os prazos prometidos para First Class, Second Class e Same Day estão abaixo do que a operação entrega. Ajustar esses prazos, sem mudar a operação, reduz a taxa de atraso de 54,8% para 30,3%. A operação fecha com lucro líquido de $3,97M, margem de 12%.

**Dados:** CSV original do [Kaggle](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis), com 180.519 itens em 65.752 pedidos, de jan/2015 a jan/2018. O dataset é sintético.

## 1. O atraso vem do prazo prometido, não da operação

Cada modo de envio tem um tempo real de entrega fixo ou previsível. O prazo prometido ao cliente é que está abaixo dele.

![Dias reais de envio por modo](figures/01_prazos_por_modo.png)

| Modo | Prazo atual | Dias reais | Pedidos atrasados |
| --- | --- | --- | --- |
| First Class | 1 dia | sempre 2 | 100% |
| Second Class | 2 dias | 2 a 6 (média 4) | 80% |
| Same Day | 0 dia | 0 ou 1 | 48% |
| Standard Class | 4 dias | 2 a 6 (média 4) | 40% |

- O First Class nunca cumpre o prazo, porque leva sempre exatamente 2 dias.
- O Second Class tem o mesmo tempo real do Standard Class. Hoje ele não entrega mais rápido.

### Same Day: o horário do pedido decide o atraso

![Same Day por hora do pedido](figures/02_same_day_por_hora.png)

Pedidos Same Day feitos antes das 12h saem no mesmo dia. Os feitos a partir das 12h saem no dia seguinte e são todos registrados como atraso. Existe um horário de corte ao meio-dia que não é comunicado ao cliente.

### O que não explica o atraso

- **Distância e destino:** a taxa de atraso fica entre 54% e 55% em todos os mercados (África, Europa, LATAM, Ásia-Pacífico, EUA/Canadá).
- **Categoria e produto:** a taxa varia só entre 52% e 60% entre categorias.
- **Dia da semana:** nos modos First, Second e Standard Class, a variação é menor que 2 pontos.
- **Volume:** os pedidos sobem cerca de 20% a partir de out/2017, e a taxa de atraso não muda.

![Pedidos e atraso por mês](figures/06_pedidos_atraso_mes.png)

## 2. Probabilidade de atraso

Uma árvore de decisão rasa (`src/dataco/model.py`) usa só o que se sabe no momento do pedido. Ela chega a 5 regras:

| Regra | P(atraso) prevista | Taxa real no teste |
| --- | --- | --- |
| First Class | 100% | 100% |
| Same Day, pedido a partir das 12h | 100% | 100% |
| Second Class | 79,8% | 80,5% |
| Standard Class | 39,9% | 39,5% |
| Same Day, pedido antes das 12h | 0% | 0% |

- **Validação:** treino com pedidos até jun/2017 e teste no período seguinte. O AUC é 0,777 no teste e 0,774 no treino, sem sinal de overfit.
- **Estabilidade:** em quatro cortes de tempo diferentes, o AUC ficou entre 0,767 e 0,777.
- **Variáveis sem efeito:** tipo de pagamento, mercado, segmento e dia da semana não entraram na árvore.

## 3. Lucro e prejuízo

| Indicador | Valor |
| --- | --- |
| Receita | $33,05M |
| Lucro bruto (itens com benefit positivo) | $7,85M |
| Prejuízo (itens com benefit negativo) | −$3,88M |
| Resultado líquido | $3,97M (12,0%) |

- 81% dos itens dão lucro e 19% dão prejuízo. A proporção é a mesma em todas as categorias, produtos, mercados, faixas de desconto e modos de envio.
- O prejuízo é concentrado: os itens que perdem mais do que o próprio valor de venda são 18,7% dos itens negativos e respondem por 53% do prejuízo.
- Pedidos `SUSPECTED_FRAUD` e `CANCELED` nunca são enviados, mas registram $1,41M de receita e $160K de benefit. Esses valores inflam o resultado em cerca de 4%.

As mesmas 8 categorias concentram 80% do lucro e 80% do prejuízo, ou seja, o prejuízo acompanha o volume vendido.

![Pareto do lucro bruto](figures/04_pareto_lucro.png)

![Pareto do prejuízo](figures/05_pareto_prejuizo.png)

## 4. Próximas ações

![Impacto das ações](figures/03_impacto_acoes.png)

1. **Same Day:** somar 1 dia ao prazo para pedidos feitos a partir das 12h e comunicar esse horário de corte ao cliente. No histórico, o atraso do Same Day cai de 48% para 0%.
2. **First Class:** mudar o prazo de 1 para 2 dias. O atraso cai de 100% para 0%.
3. **Second Class:** mudar o prazo de 2 para 4 dias, o que reduz o atraso de 80% para 40%. Um prazo de 6 dias zera o atraso, mas iguala o Second Class ao Standard. A outra opção é tornar a operação do Second Class mais rápida que a do Standard.
4. **Relatórios de resultado:** excluir os pedidos `CANCELED` e `SUSPECTED_FRAUD` do faturamento e do lucro, porque não foram enviados.
5. **Monitoramento:** acompanhar no Power BI (`bi/`) a taxa de atraso por modo e por faixa de horário depois da mudança de prazos.

---

Para reproduzir: `cd src && ../.venv/bin/python -m dataco.figures` gera os gráficos em `docs/figures/`. Os notebooks `notebooks/02_eda.ipynb` e `notebooks/03_modelo_atraso.ipynb` trazem as análises completas.
