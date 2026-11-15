"""Ingestão incremental de séries do SGS (Banco Central) para a camada bronze.

A camada bronze é um conjunto de arquivos JSONL versionados no próprio repositório:
data/bronze/sgs/serie=<codigo>/ingestion_date=<AAAA-MM-DD>/data.jsonl

Os arquivos são imutáveis na prática (um por série e dia de ingestão); reexecutar no mesmo dia
sobrescreve o arquivo do dia, e a deduplicação entre dias é feita no dbt (staging).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("ingest")

# Códigos das séries no SGS. Os metadados ficam em dbt_project/seeds/indicadores.csv
SERIES = {1: "dolar_venda", 432: "selic_meta", 433: "ipca_mensal"}
URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
BACKFILL_START = date(2015, 1, 1)
# O IPCA mensal é divulgado com defasagem; 90 dias garante que a janela o capture.
DEFAULT_LOOKBACK_DAYS = 90
# A API limita consultas de séries diárias a janelas de até 10 anos.
WINDOW_YEARS = 5


def windows(start: date, end: date, years: int = WINDOW_YEARS):
    """Divide [start, end] em janelas de `years` anos."""
    cur = start
    while cur <= end:
        nxt = min(date(cur.year + years, cur.month, min(cur.day, 28)) - timedelta(days=1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "bcb-economic-indicators/1.0"
    return session


def fetch_series(session: requests.Session, code: int, start: date, end: date) -> list[dict]:
    rows: list[dict] = []
    for w_start, w_end in windows(start, end):
        resp = session.get(
            URL.format(code=code),
            params={
                "formato": "json",
                "dataInicial": w_start.strftime("%d/%m/%Y"),
                "dataFinal": w_end.strftime("%d/%m/%Y"),
            },
            timeout=30,
        )
        if resp.status_code == 404:
            log.warning("Série %s sem dados em %s..%s", code, w_start, w_end)
            continue
        resp.raise_for_status()
        rows.extend(resp.json())
    return rows


def to_records(code: int, rows: list[dict], ingested_at: str) -> list[dict]:
    return [
        {"serie_codigo": code, "data": r["data"], "valor": r["valor"], "ingested_at": ingested_at}
        for r in rows
    ]


def write_jsonl(out_dir: Path, code: int, records: list[dict], run_date: date, suffix: str = "") -> Path:
    """Grava a partição do dia. `suffix` separa a carga histórica da diária (evita sobrescrita)."""
    partition = f"ingestion_date={run_date.isoformat()}{suffix}"
    path = out_dir / "sgs" / f"serie={code}" / partition / "data.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backfill", action="store_true", help=f"carga histórica desde {BACKFILL_START}")
    p.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="janela de reprocessamento")
    p.add_argument("--out-dir", type=Path, default=Path("data/bronze"), help="pasta da camada bronze")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    today = date.today()
    start = BACKFILL_START if args.backfill else today - timedelta(days=args.days)
    ingested_at = datetime.now(UTC).isoformat()
    session = build_session()

    # A carga histórica vai para uma partição própria, para a execução diária não sobrescrevê-la.
    suffix = "-backfill" if args.backfill else ""
    written: list[Path] = []
    for code, name in SERIES.items():
        rows = fetch_series(session, code, start, today)
        log.info("Série %s (%s): %s registros", code, name, len(rows))
        if rows:
            records = to_records(code, rows, ingested_at)
            written.append(write_jsonl(args.out_dir, code, records, today, suffix))

    if not written:
        log.error("Nenhum dado retornado pela API em %s..%s", start, today)
        return 1
    log.info("Arquivos gravados: %s", ", ".join(str(p) for p in written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
