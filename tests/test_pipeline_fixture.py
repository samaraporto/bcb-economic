"""Teste de ponta a ponta: dbt build sobre dados de exemplo e verificação das regras de negócio."""

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "bronze" / "sgs" / "*" / "*" / "data.jsonl"
IPCA = [0.53, 0.84, 0.71, 0.61, 0.23, -0.08, 0.12, 0.23, 0.26, 0.24, 0.28, 0.56, 0.42, 0.83]


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    dbt = shutil.which("dbt")
    if not dbt:
        pytest.skip("dbt não instalado")
    tmp = tmp_path_factory.mktemp("pipeline")
    db = tmp / "test.duckdb"
    result = subprocess.run(
        [
            dbt,
            "build",
            "--profiles-dir",
            ".",
            "--vars",
            json.dumps({"bronze_glob": str(FIXTURES)}),
            "--target-path",
            str(tmp / "target"),
            "--log-path",
            str(tmp / "logs"),
        ],
        check=False,
        cwd=ROOT / "dbt_project",
        env={**os.environ, "DUCKDB_PATH": str(db)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
    connection = duckdb.connect(str(db), read_only=True)
    yield connection
    connection.close()


def test_dedup_mantem_o_valor_revisado_mais_recente(con):
    (valor,) = con.execute(
        "select valor from marts.fct_indicadores where id_serie = 1 and data_referencia = date '2024-03-28'"
    ).fetchone()
    assert float(valor) == pytest.approx(5.1329)  # valor revisado na 2ª ingestão (original: 5.1308)


def test_sem_linhas_duplicadas_na_fato(con):
    total, distintos = con.execute(
        "select count(*), count(distinct (id_serie, data_referencia)) from marts.fct_indicadores"
    ).fetchone()
    assert total == distintos


def test_alerta_dispara_apenas_no_salto_de_3_por_cento(con):
    datas = [
        str(r[0])
        for r in con.execute(
            "select data_referencia from marts.mart_indicadores_diarios where flag_alerta_variacao order by 1"
        ).fetchall()
    ]
    assert datas == ["2024-02-15"]


def test_selic_vigente_acompanha_as_mudancas(con):
    q = "select selic_meta from marts.mart_indicadores_diarios where data_referencia = date '{}'"
    assert con.execute(q.format("2024-01-02")).fetchone()[0] == pytest.approx(11.75)
    assert con.execute(q.format("2024-02-15")).fetchone()[0] == pytest.approx(11.25)
    assert con.execute(q.format("2024-03-28")).fetchone()[0] == pytest.approx(10.75)


def test_ipca_acumulado_12_meses(con):
    rows = con.execute(
        "select mes_referencia, ipca_acumulado_12m from marts.mart_ipca_mensal order by 1"
    ).fetchall()
    assert all(r[1] is None for r in rows[:11])  # menos de 12 meses de histórico
    esperado = (math.prod(1 + x / 100 for x in IPCA[-12:]) - 1) * 100
    assert rows[-1][1] == pytest.approx(esperado)
