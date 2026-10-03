"""Bout en bout : CLI -> HTTP -> pipeline factice (autre processus logique, sans import de ragbench)."""
import json
import threading

import pytest

from mock_pipeline import make_server
from ragbench.cli import main


@pytest.fixture
def mock_url():
    chunks = [json.loads(l) for l in open("datasets/sample_corpus.jsonl", encoding="utf-8")]
    srv = make_server(chunks, top_k=5)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/query"
    srv.shutdown()


def test_run_report_analyze_compare(tmp_path, mock_url, capsys):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f'pipeline: {{name: mock, version: v1, endpoint: "{mock_url}"}}\n')
    res = str(tmp_path / "results")
    base = ["--results-dir", res]

    assert main(base + ["run", "--dataset", "datasets/sample.jsonl", "--config", str(cfg), "--run-id", "r1"]) == 0
    out = capsys.readouterr().out
    assert "BENCHMARK RESULTS" in out and "Recall@5" in out and "WHY DO ANSWERS FAIL?" in out

    run_dir = tmp_path / "results" / "r1"
    assert len((run_dir / "traces.jsonl").read_text().splitlines()) == 10
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["run"]["pipeline"] == "mock" and summary["retrieval"]["recall_at_10"] == 1.0

    assert main(base + ["report", "--run", "r1"]) == 0
    assert main(base + ["analyze", "--run", "r1", "--metric", "token_f1", "--worst", "3"]) == 0
    assert "#1" in capsys.readouterr().out
    assert main(base + ["analyze", "--run", "r1", "--metric", "nope"]) == 2

    # run_id explicite : pas d'écrasement ; run_id auto : suffixe
    assert main(base + ["run", "--dataset", "datasets/sample.jsonl", "--config", str(cfg), "--run-id", "r1"]) == 2
    assert main(base + ["run", "--dataset", "datasets/sample.jsonl", "--config", str(cfg), "--limit", "3"]) == 0
    assert main(base + ["run", "--dataset", "datasets/sample.jsonl", "--config", str(cfg), "--limit", "3"]) == 0
    names = sorted(d.name for d in (tmp_path / "results").iterdir())
    assert len(names) == 3 and names[0].endswith("_mock_v1") and names[1].endswith("_mock_v1_2") and "r1" in names
    assert main(base + ["compare", "r1", "r1"]) == 0
    assert main(base + ["report", "--run", "absent"]) == 2


def test_pipeline_down_does_not_crash(tmp_path, capsys):
    cfg = tmp_path / "c.yaml"
    cfg.write_text('pipeline: {name: down, endpoint: "http://127.0.0.1:9/q", max_retries: 0}\n')
    rc = main(["--results-dir", str(tmp_path / "r"), "run", "--dataset", "datasets/sample.jsonl",
               "--config", str(cfg), "--limit", "2", "--run-id", "down"])
    assert rc == 1  # toutes les questions en erreur
    assert "PIPELINE_ERROR" in capsys.readouterr().out
