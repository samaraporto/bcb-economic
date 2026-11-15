-- Falha se a Selic estiver fora de uma faixa plausível.
select * from {{ ref('fct_indicadores') }}
where id_serie = 432 and (valor < 0 or valor > 50)
