-- Dólar e Selic por dia útil, com média móvel, variações e flag de alerta.
with dolar as (
    select data_referencia, cast(valor as double) as dolar
    from {{ ref('fct_indicadores') }}
    where id_serie = 1
),

selic as (
    select data_referencia, cast(valor as double) as selic
    from {{ ref('fct_indicadores') }}
    where id_serie = 432
),

juntos as (
    -- Selic vigente em cada data do dólar: última meta publicada até aquela data
    select
        d.data_referencia,
        d.dolar,
        (
            select s.selic
            from selic as s
            where s.data_referencia <= d.data_referencia
            order by s.data_referencia desc
            limit 1
        ) as selic_meta
    from dolar as d
),

calc as (
    select
        *,
        lag(dolar, 1) over w as dolar_anterior,
        lag(dolar, 21) over w as dolar_21_pregoes_atras,
        avg(dolar) over (order by data_referencia rows between 29 preceding and current row) as dolar_media_movel_30d
    from juntos
    window w as (order by data_referencia)
)

select
    data_referencia,
    dolar,
    selic_meta,
    dolar_media_movel_30d,
    (dolar - dolar_anterior) / nullif(dolar_anterior, 0) * 100 as var_pct_dia,
    (dolar - dolar_21_pregoes_atras) / nullif(dolar_21_pregoes_atras, 0) * 100 as var_pct_21_pregoes,
    coalesce(
        abs((dolar - dolar_anterior) / nullif(dolar_anterior, 0)) * 100 >= {{ var('limite_alerta_pct') }},
        false
    ) as flag_alerta_variacao
from calc
