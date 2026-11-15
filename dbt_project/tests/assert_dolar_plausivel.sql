-- Falha se houver cotação do dólar fora de uma faixa plausível.
select * from {{ ref('fct_indicadores') }}
where id_serie = 1 and (valor <= 0.5 or valor > 20)
