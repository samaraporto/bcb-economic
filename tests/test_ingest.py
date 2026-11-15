import itertools
import json
from datetime import date

from ingestion.ingest import to_records, windows, write_jsonl


def test_windows_cobre_todo_o_periodo_sem_sobreposicao():
    start, end = date(2015, 1, 1), date(2026, 11, 13)
    ws = list(windows(start, end))
    assert ws[0][0] == start and ws[-1][1] == end
    for (_, prev_end), (nxt_start, _) in itertools.pairwise(ws):
        assert (nxt_start - prev_end).days == 1
    assert all((e - s).days < 10 * 365 for s, e in ws)


def test_windows_periodo_curto_gera_uma_janela():
    assert list(windows(date(2026, 10, 1), date(2026, 11, 13))) == [(date(2026, 10, 1), date(2026, 11, 13))]


def test_windows_inicio_29_de_fevereiro():
    ws = list(windows(date(2016, 2, 29), date(2030, 1, 1)))
    assert ws[0][0] == date(2016, 2, 29) and ws[-1][1] == date(2030, 1, 1)


def test_to_records_formato_da_camada_bronze():
    rows = [{"data": "02/01/2026", "valor": "5.41"}]
    assert to_records(1, rows, "2026-11-13T11:00:00+00:00") == [
        {"serie_codigo": 1, "data": "02/01/2026", "valor": "5.41", "ingested_at": "2026-11-13T11:00:00+00:00"}
    ]


def test_write_jsonl_e_idempotente_no_mesmo_dia(tmp_path):
    recs = to_records(1, [{"data": "02/01/2026", "valor": "5.41"}], "2026-11-13T11:00:00+00:00")
    p1 = write_jsonl(tmp_path, 1, recs, date(2026, 11, 13))
    p2 = write_jsonl(tmp_path, 1, recs, date(2026, 11, 13))
    assert p1 == p2 and p1.parent.name == "ingestion_date=2026-11-13"
    assert [json.loads(line) for line in p1.read_text().splitlines()] == recs


def test_backfill_nao_sobrescreve_a_particao_diaria(tmp_path):
    recs = to_records(1, [{"data": "02/01/2026", "valor": "5.41"}], "2026-11-13T11:00:00+00:00")
    historica = write_jsonl(tmp_path, 1, recs, date(2026, 11, 13), "-backfill")
    diaria = write_jsonl(tmp_path, 1, recs, date(2026, 11, 13))
    assert historica != diaria and historica.exists() and diaria.exists()
    assert historica.parent.name == "ingestion_date=2026-11-13-backfill"
