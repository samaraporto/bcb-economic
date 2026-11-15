-- IPCA mensal e acumulado em 12 meses (composição dos índices mensais).
with base as (
    select
        data_referencia as mes_referencia,
        cast(valor as double) as ipca_mensal
    from {{ ref('fct_indicadores') }}
    where id_serie = 433
),

janela as (
    select
        mes_referencia,
        ipca_mensal,
        count(*) over w as meses_na_janela,
        sum(ln(1 + ipca_mensal / 100)) over w as soma_ln
    from base
    window w as (order by mes_referencia rows between 11 preceding and current row)
)

select
    mes_referencia,
    ipca_mensal,
    case when meses_na_janela = 12 then (exp(soma_ln) - 1) * 100 end as ipca_acumulado_12m
from janela
