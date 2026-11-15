-- Fato em formato longo: uma linha por indicador e data.
select
    md5(cast(id_serie as varchar) || '|' || cast(data_referencia as varchar)) as sk_indicador_dia,
    id_serie,
    data_referencia,
    valor,
    ingested_at
from {{ ref('stg_sgs_series') }}
