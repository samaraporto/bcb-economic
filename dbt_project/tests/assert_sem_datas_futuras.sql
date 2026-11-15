select * from {{ ref('fct_indicadores') }}
where data_referencia > current_date()
