{{ config(severity='warn') }}
-- Avisa se a última ingestão tem mais de 3 dias (o pipeline pode ter parado).
select max(ingested_at) as ultima_ingestao
from {{ ref('raw_sgs_series') }}
having max(ingested_at) < now() - interval 3 day
