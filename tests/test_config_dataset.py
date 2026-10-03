import pytest

from ragbench.config import ConfigError, load_config
from ragbench.dataset import DatasetError, load_dataset


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_config_env_expansion_and_redaction(tmp_path, monkeypatch):
    monkeypatch.setenv("URL", "http://x/q")
    monkeypatch.setenv("TOK", "secret")
    p = write(tmp_path, "c.yaml", 'pipeline:\n  name: p\n  endpoint: "${URL}"\n  headers: {Authorization: "Bearer ${TOK}"}\n')
    cfg = load_config(p)
    assert cfg.pipeline.endpoint == "http://x/q" and cfg.benchmark.top_k == [1, 5, 10]
    assert "secret" not in str(cfg.redacted())


def test_config_errors(tmp_path):
    with pytest.raises(ConfigError, match="MISSING_VAR"):
        load_config(write(tmp_path, "a.yaml", 'pipeline: {name: p, endpoint: "${MISSING_VAR}"}'))
    with pytest.raises(ConfigError):  # clé inconnue (faute de frappe)
        load_config(write(tmp_path, "b.yaml", "pipeline: {name: p, endpoint: u, timeot: 3}"))
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "c.yaml", "pipeline: {name: p, endpoint: u}\nbenchmark: {retrieval_metrics: [bogus]}"))


def test_dataset_loading_and_errors(tmp_path):
    row = '{"id": "a", "question": "q", "reference_answer": "r", "relevant_chunks": ["c"]}'
    ds = load_dataset(write(tmp_path, "d.jsonl", row + "\n\n" + row.replace('"a"', '"b"') + "\n"))
    assert [s.id for s in ds.samples] == ["a", "b"] and ds.name == "d" and len(ds.sha256) == 64
    assert len(load_dataset(tmp_path / "d.jsonl", limit=1).samples) == 1
    with pytest.raises(DatasetError, match="dupliqué"):
        load_dataset(write(tmp_path, "dup.jsonl", row + "\n" + row))
    with pytest.raises(DatasetError, match=":2:"):
        load_dataset(write(tmp_path, "bad.jsonl", row + "\n" + '{"id": "z"}'))
    with pytest.raises(DatasetError):
        load_dataset(write(tmp_path, "norel.jsonl", row.replace('["c"]', "[]")))


def test_sample_dataset_is_valid():
    ds = load_dataset("datasets/sample.jsonl")
    assert len(ds.samples) == 10
