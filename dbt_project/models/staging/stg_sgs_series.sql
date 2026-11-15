-- Deduplica a camada raw: mantém, por série e data, o registro ingerido mais recentemente.
-- É isso que torna o pipeline idempotente (reexecutar não duplica dados) e absorve revisões da API.
with ranked as (
    select
        serie_codigo as id_serie,
        strptime(data, '%d/%m/%Y')::date as data_referencia,
        try_cast(valor as decimal(18, 6)) as valor,
        ingested_at,
        row_number() over (
            partition by serie_codigo, data
            order by ingested_at desc
        ) as rn
    from {{ ref('raw_sgs_series') }}
)

select id_serie, data_referencia, valor, ingested_at
from ranked
where rn = 1
