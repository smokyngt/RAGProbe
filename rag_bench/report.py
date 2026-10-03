"""Rapport HTML autonome (scorecard + chaque essai) à partir de un ou plusieurs results.json."""
from __future__ import annotations

import html
import json
from pathlib import Path

CSS = """body{font:15px/1.5 system-ui;max-width:980px;margin:2rem auto;padding:0 1rem;color:#1d2433}
table{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem}td,th{border-bottom:1px solid #e3e6ec;padding:.4rem .6rem;text-align:left;vertical-align:top}
.chip{padding:.1rem .5rem;border-radius:99px;font-size:12px;color:#fff}.pass{background:#2a9d5c}.partial{background:#d89b1d}
.fail{background:#d64545}.app_error{background:#7a4fd6}code{background:#f1f3f7;padding:0 .25rem;border-radius:4px}"""


def _status(row: dict) -> str:
    if "status" in row:
        return row["status"]
    d = row.get("diagnosis")
    return "pass" if d == "ok" else "app_error" if d == "pipeline_error" else "fail"


def _chip(s: str) -> str:
    return f'<span class="chip {s}">{s}</span>'


def render(reports: list[dict]) -> str:
    e = html.escape
    out = ["<!doctype html><meta charset=utf-8><title>Prosperify benchmark</title>", f"<style>{CSS}</style>",
           "<h1>Prosperify · benchmark report</h1>", "<h2>Scorecard</h2>",
           "<table><tr><th>Track</th><th>Pipeline</th><th>Date</th><th>N</th><th>Pass</th><th>Partial</th>"
           "<th>Fail</th><th>App error</th><th>Métriques clés</th></tr>"]
    for r in reports:
        st = {s: sum(_status(x) == s for x in r["results"]) for s in ("pass", "partial", "fail", "app_error")}
        a = r["aggregate"]
        keys = ("syntax_valid", "constraint_score", "recall@5", "precision@5", "mrr") if r.get("track") == "dorking" \
            else tuple(f"retrieval.{k}" for k in ("recall@5", "mrr")) + ("qa.f1",)
        metrics = []
        for k in keys:
            v = a
            for part in k.split(".") if r.get("track") != "dorking" else [k]:
                v = v.get(part, {}) if isinstance(v, dict) else {}
            if isinstance(v, (int, float)):
                metrics.append(f"{k}={v:.3f}")
        out.append(f"<tr><td>{e(r.get('track', 'qa'))}</td><td>{e(r['pipeline'])}</td><td>{e(r['timestamp'])}</td>"
                   f"<td>{len(r['results'])}</td>" + "".join(f"<td>{st[s]}</td>" for s in st)
                   + f"<td>{e(', '.join(metrics))}</td></tr>")
    out.append("</table><h2>Chaque essai</h2>")
    for r in reports:
        out.append(f"<h3>{e(r.get('track', 'qa'))} · {e(r['pipeline'])}</h3><table><tr><th>ID</th><th>Statut</th><th>Détail</th></tr>")
        for x in r["results"]:
            if r.get("track") == "dorking":
                detail = (f"<b>{e(x['goal'])}</b><br><code>{e(x.get('query', x.get('error', '')))}</code><br>"
                          f"contraintes {x.get('constraint_score', 0):.2f} · recall@5 {x.get('recall@5', 0):.2f}")
            else:
                detail = f"<b>{e(x['question'])}</b><br>diagnostic : {e(x['diagnosis'])}"
            out.append(f"<tr><td>{e(x['id'])}</td><td>{_chip(_status(x))}</td><td>{detail}</td></tr>")
        out.append("</table>")
    out.append("<p>Généré depuis les résultats sauvegardés ; données synthétiques.</p>")
    return "\n".join(out)


def write_report(paths: list[str], out: str) -> None:
    reports = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(render(reports), encoding="utf-8")
