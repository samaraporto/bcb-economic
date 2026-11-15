select
    codigo as id_serie,
    nome,
    descricao,
    unidade,
    frequencia
from {{ ref('indicadores') }}
