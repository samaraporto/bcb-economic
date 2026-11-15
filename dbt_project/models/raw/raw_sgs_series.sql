-- Camada raw: leitura direta dos arquivos JSONL da camada bronze, sem transformação.
select
    serie_codigo,
    data,
    valor,
    ingested_at
from read_json(
    '{{ var("bronze_glob") }}',
    format = 'newline_delimited',
    columns = {
        'serie_codigo': 'INTEGER',
        'data': 'VARCHAR',
        'valor': 'VARCHAR',
        'ingested_at': 'TIMESTAMPTZ'
    }
)
