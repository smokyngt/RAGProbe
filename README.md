# ragbench + FinanceBench

**Measure a document-QA / RAG pipeline objectively, and find out _why_ it fails.**

This repository contains two independent pieces:

| | What it is | Where |
|---|---|---|
| **ragbench** | A benchmark runner that calls any RAG pipeline over HTTP, scores retrieval and answers, keeps a full trace per question and tells retrieval failures apart from generation failures. | `ragbench/`, `benchmark.py` |
| **FinanceBench V1.1** | An English financial QA benchmark: 113 independently checked questions over a frozen corpus of 17 public financial PDFs (1,995 pages), with evidence pointing to the original document and page. | `finance_benchmark/` |

The runner contains no RAG pipeline, and the dataset was built without using the pipeline it will evaluate.

---

## The question it answers

> When the system gives a wrong answer, did it **not find** the information, or **not use** it correctly?

```mermaid
flowchart LR
    D[(dataset<br/>question + ground truth)] --> R[ragbench runner]
    R -- "POST {question}" --> P[RAG pipeline<br/>under test]
    P -- "answer + retrieved chunks" --> R
    R --> M1[retrieval metrics<br/>Recall@K · MRR · nDCG]
    R --> M2[answer metrics<br/>EM · F1 · LLM judge]
    M1 & M2 --> DG{diagnosis}
    DG --> O[(results/run_id/<br/>summary.json · traces.jsonl)]
```

| evidence retrieved? | answer | diagnosis |
|---|---|---|
| no | wrong | `RETRIEVAL_FAILURE` — the information was not found |
| yes | wrong | `GENERATION_FAILURE` — it was found but not used correctly |
| — | right, not supported by the retrieved text | `GROUNDING_FAILURE` (needs the judge) |
| — | right | `SUCCESS` |
| — | HTTP error / timeout / invalid payload | `PIPELINE_ERROR` |

Unanswerable questions have nothing to retrieve: answering "this cannot be established" is a success, an invented
answer is a `GENERATION_FAILURE`. Every report ends with the 2×2 table *evidence retrieved × answer correct* and the
share of wrong answers caused by retrieval vs generation.

---

## Quickstart (2 minutes, no API key)

```bash
pip install -r requirements.txt pytest
python examples/mock_pipeline.py --port 8000 &            # a toy BM25 pipeline exposed over HTTP

python benchmark.py run --dataset datasets/sample.jsonl --config configs/pipeline.yaml --run-id demo
python benchmark.py report  --run demo
python benchmark.py analyze --run demo --metric token_f1 --worst 5
python -m pytest                                          # 57 tests
```

```
RETRIEVAL                          WHY DO ANSWERS FAIL?
Recall@1        0.77                                 answer correct  answer wrong
Recall@5        1.00               evidence retrieved             6             4
MRR             0.95               evidence missing               0             0
QA                                 Accuracy when evidence retrieved : 60%
Exact Match     0.00               Wrong answers (4): 0% retrieval failure, 100% generation failure
Token F1        0.54
```

`datasets/sample.jsonl` is a 10-question **synthetic** toy set (fictional companies) used for smoke tests only.

---

## Run FinanceBench against your pipeline (e.g. the Prosperify API)

1. **Ingest** `finance_benchmark/corpus/documents/fin_doc_001.pdf … fin_doc_017.pdf` into the pipeline, keeping the
   file name (or `fin_doc_NNN`) as the document id and the page number of every chunk.
2. **Expose** an HTTP endpoint that follows the contract below.
3. **Run**:

```bash
export PIPELINE_URL=https://…/query PIPELINE_TOKEN=… ANTHROPIC_API_KEY=…
python benchmark.py run --dataset finance_benchmark/datasets/finance_benchmark_v1.jsonl \
                        --config configs/financebench.yaml --run-id prosperify_v1
python benchmark.py analyze --run prosperify_v1 --failure-type RETRIEVAL_FAILURE
python benchmark.py compare prosperify_v1 prosperify_v2
```

### HTTP contract

`POST <endpoint>` with `{"question": "..."}` → `200`:

```json
{
  "answer": "DHL Group's effective tax rate for 2025 was 29.4%.",
  "retrieved_chunks": [
    {"chunk_id": "c_8812", "text": "…Profit before income taxes 5,062 5,246…", "score": 12.3,
     "document_id": "fin_doc_011.pdf", "page": 162, "page_end": 162}
  ]
}
```

- Order of `retrieved_chunks` = ranking of the retriever. A chunk may also be a bare id string.
- Accepted aliases: `id`, `content`, `doc_id` / `source`, `page_number`. Field names of the payload are configurable.
- `text` is needed by the judge (groundedness); `document_id` + `page` let the runner match the annotated evidence.
  Without pages, a chunk matches an evidence item when it contains most of the evidence text.
- Errors are isolated per question: timeout, retries with backoff on network/408/425/429/5xx (never on other 4xx),
  invalid payload → `PIPELINE_ERROR`, metrics at 0, the run continues.

---

## Ground truth formats

One JSONL line per question. Two formats are accepted, so the same runner serves both datasets:

```jsonc
// chunk ids (tied to one chunking of the corpus) — datasets/sample.jsonl
{"id": "q_001", "question": "…", "reference_answer": "…", "relevant_chunks": ["alpha_2025_chunk_001"]}

// evidence in the original documents (independent of chunking) — FinanceBench
{"id": "fin_q_011", "question": "…", "reference_answer": "…",
 "evidence": [{"document_id": "fin_doc_011", "page": 162, "text": "Profit before income taxes 5,062 5,246 …"}],
 "metadata": {"type": "calculation", "style": "lookup", "answerable": true, "…": "…"},
 "calculation": {"inputs": {"…": 0}, "operation": "…", "result": 0.2936}}
```

Unanswerable questions carry `"answerable": false` (top level or in `metadata`) and no evidence.

## Metrics

| Family | Metrics | Notes |
|---|---|---|
| Retrieval | Recall@K, MRR (default) · Precision@K, nDCG@K | duplicates count once; averaged over answerable questions |
| Answer, deterministic | Exact Match, Token F1 | normalised (case, accents, punctuation, articles); a coarse proxy for long answers |
| Answer, LLM judge | correctness, completeness, groundedness ∈ [0, 1] + reason | JSON validated by Pydantic; provider `anthropic` or `openai_compatible`; the evaluated answer is treated as data, not instructions |
| Latency | mean, p50, p95 | successful calls only |

Answer correctness = judge `correctness ≥ 0.5` when the judge is on, else Token F1 ≥ 0.5 (thresholds configurable);
for unanswerable questions without judge, an explicit abstention ("cannot be established…") is required.
Adding a retrieval metric = one function on `(hits, n_relevant, k)` in `ragbench/evaluation/retrieval.py`.

## CLI

| Command | Purpose |
|---|---|
| `run --dataset D --config C [--run-id ID] [--limit N] [--no-judge]` | run, write `results/<run_id>/summary.json` + `traces.jsonl` |
| `report --run ID` | retrieval, QA, judge, latency, diagnosis, 2×2 failure table |
| `analyze --run ID [--metric M] [--worst N] [--failure-type T]` | worst traces with question, expected evidence, top-5 chunks, judge reason |
| `compare A B` | metric deltas between two runs (warns when the dataset hash differs) |

Each run records `run_id`, timestamp, pipeline name/version, dataset name/version/**SHA-256**, and the full configuration
(header values masked). `${VAR}` in YAML is read from the environment, so no secret lives in the config.

---

## FinanceBench V1.1 at a glance

- **Corpus (frozen, SHA-256 per file):** ECB annual accounts · Belfius Bank Pillar 3, EMTN base prospectus, FY2025 results release ·
  Belfius Insurance SFCR · ASN Bank Pillar 3 · M&G/PIA SFCR · Central Bank of Türkiye · Luzerner Kantonalbank · CBA Europe Pillar 3 ·
  Guggenheim UCITS annual report and prospectus · Fresenius consolidated statements and Q4/FY2025 release · DHL annual reports 2025 and 2024 ·
  AMF (French markets regulator) 2025 annual report.
- **113 questions** — types: table 38 · calculation 19 · temporal 12 · direct 11 · multi-document 9 · multi-evidence 7 · definition 7 ·
  unanswerable 6 · risk 4; forms: lookup 31 · comparison 23 · explanatory 13 · yes/no 12 · superlative 10 · count 6 · list 5 · ranking 5 ·
  conditional 5 · trend 3. 23 carry a deterministic `calculation` with the printed inputs, units and scale.
- **Validation:** annotation by model agents → automatic checks (every evidence quote verbatim on its page, every calculation
  recomputed, units checked) → **blind re-answer** by separate agents → adjudication of every disagreement against the source
  (41 questions rewritten, 1 withheld). **No human review yet:** `datasets/human_review_priority.json` lists the 20 questions to read first.
- **Missing:** a French Universal Registration Document (the issuer's domain is blocked by this environment's network policy).

Dataset card, document table, protocol and limits: **[finance_benchmark/README.md](finance_benchmark/README.md)**.

---

## Repository layout

```
benchmark.py                  CLI entry point (→ ragbench/cli.py)
ragbench/
  models.py                   Pydantic structures (Sample, EvidenceRef, PipelineResult, Trace, Summary…)
  config.py · dataset.py      YAML config and JSONL dataset loading/validation
  runner.py                   dataset → pipeline → metrics → diagnosis → traces
  storage.py                  results/<run_id>/ (incremental traces, read back)
  pipelines/                  base.py (PipelineAdapter), http.py (HTTPPipelineAdapter)
  evaluation/                 retrieval.py, qa.py, judge.py, diagnosis.py
  reporting/                  aggregator.py, report.py, analyze.py
configs/                      pipeline.yaml (mock demo), financebench.yaml (real pipeline + judge)
datasets/                     sample.jsonl + sample_corpus.jsonl (synthetic toy set for the mock pipeline)
examples/mock_pipeline.py     toy BM25 pipeline over HTTP (does not import ragbench)
finance_benchmark/            FinanceBench: corpus/, datasets/, annotation/ (audit trail), tools/, guide
tests/                        57 tests (metrics, judge, HTTP adapter, runner, evidence matching, CLI end-to-end, dataset tools)
```

## Known limits

- Sequential execution, no resume after interruption (traces already written are kept).
- The Anthropic / OpenAI-compatible judge clients are only tested with a fake client.
- No confidence intervals between runs: on ~100 questions, small differences are not significant.
- FinanceBench reference answers are long and often answer several sub-questions: use the judge, not EM/F1, to score them.
