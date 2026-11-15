{{ config(severity='warn') }}
-- Avisa se a última cotação do dólar tem mais de 7 dias.
select max(data_referencia) as ultima_data
from {{ ref('fct_indicadores') }}
where id_serie = 1
having max(data_referencia) < current_date - interval 7 day
