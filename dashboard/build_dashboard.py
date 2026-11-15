"""Gera um dashboard HTML estático a partir das tabelas marts do DuckDB.

Uso:
    python dashboard/build_dashboard.py --db warehouse/indicadores.duckdb --out site/index.html
    python dashboard/build_dashboard.py --sample --out site/index.html   # dados fictícios, só para ver o layout
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PLOTLY = "https://cdn.plot.ly/plotly-2.35.2.min.js"


def _rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [c[0] for c in cur.description]
    return [
        {k: (v.isoformat() if isinstance(v, date) else v) for k, v in zip(cols, row, strict=True)}
        for row in cur.fetchall()
    ]


def load_duckdb(db_path: str) -> dict:
    import duckdb

    con = duckdb.connect(db_path, read_only=True)
    daily = _rows(
        con,
        """select data_referencia, dolar, selic_meta, dolar_media_movel_30d,
                  var_pct_dia, var_pct_21_pregoes, flag_alerta_variacao
           from marts.mart_indicadores_diarios order by data_referencia""",
    )
    ipca = _rows(
        con,
        """select mes_referencia, ipca_mensal, ipca_acumulado_12m
           from marts.mart_ipca_mensal order by mes_referencia""",
    )
    con.close()
    return {"daily": daily, "ipca": ipca, "sample": False}


def load_sample() -> dict:
    """Dados FICTÍCIOS, apenas para pré-visualizar o layout."""
    rnd = random.Random(7)
    daily, dolar, d = [], 5.0, date.today() - timedelta(days=900)
    window: list[float] = []
    while d <= date.today():
        if d.weekday() < 5:
            prev = dolar
            dolar = max(3.5, dolar * (1 + rnd.gauss(0, 0.009)))
            window = (window + [dolar])[-30:]
            var = (dolar / prev - 1) * 100
            daily.append(
                {
                    "data_referencia": d.isoformat(),
                    "dolar": round(dolar, 4),
                    "selic_meta": 14.75 if d.year >= 2026 else 13.25,
                    "dolar_media_movel_30d": sum(window) / len(window),
                    "var_pct_dia": var,
                    "var_pct_21_pregoes": None,
                    "flag_alerta_variacao": abs(var) >= 2,
                }
            )
        d += timedelta(days=1)
    ipca, vals = [], []
    for i in range(36):
        m = date.today().replace(day=1) - timedelta(days=30 * (36 - i))
        v = round(rnd.uniform(0.0, 0.8), 2)
        vals = (vals + [v])[-12:]
        acum = (math.exp(sum(math.log(1 + x / 100) for x in vals)) - 1) * 100 if len(vals) == 12 else None
        ipca.append(
            {"mes_referencia": m.replace(day=1).isoformat(), "ipca_mensal": v, "ipca_acumulado_12m": acum}
        )
    return {"daily": daily, "ipca": ipca, "sample": True}


TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indicadores econômicos do Brasil</title>
<script src="__PLOTLY__"></script>
<style>
:root{--bg:#f7f7f5;--card:#fff;--fg:#1c1c1a;--muted:#6b6b66;--grid:#e6e6e1;--accent:#1d6fa5;--warn:#c2410c;--line:#ddd}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#201f1e;--fg:#ecece8;--muted:#9a9a94;--grid:#33322f;--accent:#5aa9e0;--warn:#fb923c;--line:#3a3935}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.45}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.5rem;margin:0 0 4px}
.sub{color:var(--muted);font-size:.9rem;margin:0 0 20px}
.banner{background:var(--warn);color:#fff;padding:8px 12px;border-radius:8px;margin-bottom:16px;font-size:.9rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .l{color:var(--muted);font-size:.8rem}.kpi .v{font-size:1.7rem;font-weight:600}.kpi .s{font-size:.8rem;color:var(--muted)}
h2{font-size:1rem;margin:0 0 8px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:800px){.grid{grid-template-columns:1fr}}
.full{grid-column:1/-1}
.chart{height:300px}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:500}
footer{color:var(--muted);font-size:.8rem;margin-top:20px}
</style>
</head>
<body>
<main>
<h1>Indicadores econômicos do Brasil</h1>
<p class="sub">Dólar, Selic e IPCA, atualizados automaticamente a partir da API do Banco Central.</p>
<div id="banner"></div>
<div class="kpis" id="kpis"></div>
<div class="grid">
  <div class="card full"><h2>Dólar (venda) e média móvel de 30 pregões</h2><div id="c-dolar" class="chart"></div></div>
  <div class="card"><h2>Meta Selic (% a.a.)</h2><div id="c-selic" class="chart"></div></div>
  <div class="card"><h2>IPCA mensal e acumulado em 12 meses (%)</h2><div id="c-ipca" class="chart"></div></div>
  <div class="card full"><h2>Maiores variações diárias do dólar</h2>
    <div class="scroll"><table id="t-alertas"><thead><tr><th>Data</th><th>Dólar (R$)</th><th>Variação no dia</th></tr></thead><tbody></tbody></table></div></div>
</div>
<footer id="foot"></footer>
</main>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fmt = (v, d = 2) => v == null ? "–" : Number(v).toLocaleString("pt-BR", {minimumFractionDigits: d, maximumFractionDigits: d});
const last = a => a[a.length - 1];
const br = s => s.split("-").reverse().join("/");

function layout(extra) {
  return Object.assign({
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: {color: css("--fg"), family: "system-ui, sans-serif"},
    margin: {t: 8, r: 12, b: 40, l: 48},
    xaxis: {gridcolor: css("--grid")}, yaxis: {gridcolor: css("--grid")},
    legend: {orientation: "h", y: -0.2}
  }, extra || {});
}
const cfg = {displayModeBar: false, responsive: true};

if (D.sample) document.getElementById("banner").innerHTML = '<div class="banner">Pré-visualização com dados fictícios.</div>';

const dl = D.daily, ip = D.ipca;
const ld = last(dl), li = ip.filter(r => r.ipca_acumulado_12m != null).pop();
const alertas12m = dl.filter(r => r.flag_alerta_variacao && r.data_referencia >= new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10)).length;
const kpi = (l, v, s) => '<div class="card kpi"><div class="l">' + l + '</div><div class="v">' + v + '</div><div class="s">' + s + '</div></div>';
document.getElementById("kpis").innerHTML =
  kpi("Dólar (venda)", "R$ " + fmt(ld.dolar), br(ld.data_referencia)) +
  kpi("Variação em 21 pregões", ld.var_pct_21_pregoes == null ? "–" : fmt(ld.var_pct_21_pregoes) + "%", "dólar") +
  kpi("Meta Selic", fmt(ld.selic_meta) + "% a.a.", "vigente na última data do dólar") +
  kpi("IPCA acumulado 12m", li ? fmt(li.ipca_acumulado_12m) + "%" : "–", li ? "até " + br(li.mes_referencia).slice(3) : "") +
  kpi("Dias com alerta (12m)", alertas12m, "variação diária acima do limite");

Plotly.newPlot("c-dolar", [
  {x: dl.map(r => r.data_referencia), y: dl.map(r => r.dolar), name: "Dólar", type: "scatter", mode: "lines", line: {color: css("--accent"), width: 1.5}},
  {x: dl.map(r => r.data_referencia), y: dl.map(r => r.dolar_media_movel_30d), name: "Média móvel 30", type: "scatter", mode: "lines", line: {color: css("--warn"), width: 2, dash: "dot"}}
], layout(), cfg);

Plotly.newPlot("c-selic", [
  {x: dl.map(r => r.data_referencia), y: dl.map(r => r.selic_meta), type: "scatter", mode: "lines", line: {color: css("--accent"), shape: "hv", width: 2}, showlegend: false}
], layout(), cfg);

Plotly.newPlot("c-ipca", [
  {x: ip.map(r => r.mes_referencia), y: ip.map(r => r.ipca_mensal), name: "Mensal", type: "bar", marker: {color: css("--accent")}},
  {x: ip.map(r => r.mes_referencia), y: ip.map(r => r.ipca_acumulado_12m), name: "Acumulado 12m", type: "scatter", mode: "lines", line: {color: css("--warn"), width: 2}}
], layout(), cfg);

const maiores = dl.filter(r => r.var_pct_dia != null).slice().sort((a, b) => Math.abs(b.var_pct_dia) - Math.abs(a.var_pct_dia)).slice(0, 10);
document.querySelector("#t-alertas tbody").innerHTML = maiores.map(r =>
  "<tr><td>" + br(r.data_referencia) + "</td><td>" + fmt(r.dolar) + "</td><td>" + (r.var_pct_dia > 0 ? "+" : "") + fmt(r.var_pct_dia) + "%</td></tr>").join("");

document.getElementById("foot").textContent = "Fonte: Banco Central do Brasil (SGS). Atualizado em __UPDATED__ (UTC).";
</script>
</body>
</html>
"""


def render(data: dict) -> str:
    updated = datetime.now(UTC).strftime("%d/%m/%Y %H:%M")
    return (
        TEMPLATE.replace("__PLOTLY__", PLOTLY)
        .replace("__UPDATED__", updated)
        .replace("__DATA__", json.dumps(data, default=str))
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", help="caminho do arquivo DuckDB")
    p.add_argument("--out", default="site/index.html")
    p.add_argument("--sample", action="store_true", help="usa dados fictícios")
    args = p.parse_args()
    if not args.sample and not args.db:
        p.error("informe --db ou use --sample")

    data = load_sample() if args.sample else load_duckdb(args.db)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    print(f"Dashboard gerado em {out} ({len(data['daily'])} dias, {len(data['ipca'])} meses)")


if __name__ == "__main__":
    main()
