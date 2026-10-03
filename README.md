# ragbench — benchmark runner for RAG pipelines (V1: retrieval + QA)

An **independent** runner: it sends the questions of a dataset to an existing pipeline (HTTP), collects `answer` +
`retrieved_chunks`, computes metrics, and keeps a **complete trace per question**. It contains no RAG pipeline.
The central question of V1:

> When an answer is wrong, did the system **not find** the information (retrieval) or **fail to use it** (generation)?

```
datasets/*.jsonl ─► Runner ──HTTP──► RAG pipeline (any)
                      │                  │
                      │      {answer, retrieved_chunks[]}
                      ▼                  ▼
              evaluation/retrieval   evaluation/qa (+ optional LLM judge)
                      └────────┬─────────┘
                               ▼
                diagnosis (retrieval / generation / grounding)
                               ▼
               results/<run_id>/{summary.json, traces.jsonl}
```

All benchmark content (datasets, reports, messages) is in **English**. Internal code comments are partly French.

## Install and try it in 2 minutes

```bash
pip install -r requirements.txt pytest          # + `pip install anthropic` for the Anthropic judge
python examples/mock_pipeline.py --port 8000 &  # mock pipeline (BM25 + extractive answer)

python benchmark.py run --dataset datasets/sample.jsonl --config configs/pipeline.yaml --run-id demo
python benchmark.py report  --run demo
python benchmark.py analyze --run demo --metric token_f1 --worst 5
python -m pytest
```

Sample output (10 financial example questions):

```
RETRIEVAL                          WHY DO ANSWERS FAIL?
Recall@1        0.77                                 answer correct  answer wrong
Recall@5        1.00               evidence retrieved             6             4
MRR             0.95               evidence missing               0             0
QA                                 Accuracy when evidence retrieved : 60%
Exact Match     0.00               Wrong answers (4): 0% retrieval failure, 100% generation failure
Token F1        0.54
```

With `--top-k 2` on the mock pipeline, the same questions yield 2 `RETRIEVAL_FAILURE` and 2 `GENERATION_FAILURE`.

## Commands

| Command | Purpose |
|---|---|
| `run --dataset D --config C [--run-id ID] [--limit N] [--no-judge]` | run the benchmark, write `results/<run_id>/` |
| `report --run ID` | print the report (retrieval, QA, judge, latency, diagnosis) |
| `analyze --run ID [--metric M] [--worst N] [--failure-type T]` | worst traces by `recall_at_5`, `mrr`, `token_f1`, `correctness`, `groundedness`… |
| `compare A B` | metric differences between two runs (warns if the datasets differ) |

Default `run_id`: `<date>_<pipeline>_<version>` (suffix `_2`, `_3` on collision; an explicit `--run-id` never overwrites).
Global option: `--results-dir` (default `results`).

## Contract with the tested pipeline

`POST <endpoint>` with `{"question": "..."}` → `200` with:

```json
{"answer": "The contract runs for five years.",
 "retrieved_chunks": [{"chunk_id": "contract_12_chunk_084", "text": "…", "score": 12.3}, "contract_12_chunk_021"]}
```

A chunk is an id (`str`) or an object (`chunk_id`|`id`, `text`|`content`, `score`). Order = retriever ranking.
**Returning `text`** is required for the judge to assess groundedness. Field names are configurable
(`request_field`, `answer_field`, `chunks_field`). For a non-HTTP pipeline: subclass `PipelineAdapter.query()`.

Error handling: timeout, limited retries with backoff (network, 408/425/429/5xx; **no** retry on 4xx), invalid payloads →
the error is isolated **to the question** (`PIPELINE_ERROR`, metrics at 0) and the run continues.

## Dataset

JSONL, one question per line (validated with Pydantic, unique ids, errors carry the line number):

```json
{"id": "q_001", "question": "…", "reference_answer": "…", "document_id": "alpha_2025",
 "relevant_chunks": ["alpha_2025_chunk_001"], "metadata": {"category": "factual", "difficulty": "easy"}}
```

`relevant_chunks` (≥ 1) must contain the ids **exposed by the pipeline**. Each run records the dataset SHA-256: two runs are
comparable iff the hashes are equal. `datasets/sample.jsonl`: 10 fictional financial questions (factual, numeric, multi-hop);
`sample_corpus.jsonl` is only used by the mock pipeline. The real finance benchmark lives in `finance_benchmark/`
(see its README); its ground truth references original documents (document + page), not RAG chunks.

## Metrics

- **Retrieval** (`evaluation/retrieval.py`): Recall@K, MRR; Precision@K and nDCG@K available (`benchmark.retrieval_metrics`).
  Duplicate chunks count once. Adding a metric = one function + one line in `K_METRICS`/`RANK_METRICS` (e.g. MAP).
- **Deterministic QA** (`evaluation/qa.py`): Exact Match, Token F1 after normalisation (lowercase, accents, punctuation, articles).
- **LLM judge** (`evaluation/judge.py`): `correctness`, `completeness`, `groundedness` ∈ [0,1] + `reason`, JSON validated by Pydantic
  (one retry if invalid; otherwise `judge_error` in the trace and fallback to Token F1). The provider is in the config
  (`anthropic` or `openai_compatible`); the benchmark only depends on the `AnswerJudge` interface. The evaluated answer is
  treated as data (tags + instruction), not as instructions. Several judges: write a composite `AnswerJudge`.

## Diagnosis (the central point)

Each trace holds `analysis` = {`retrieval_ok`, `answer_correct`, `grounded`} and a derived `diagnosis`:

| `retrieval_ok` | answer | `diagnosis` |
|---|---|---|
| no | wrong | `RETRIEVAL_FAILURE` — the evidence is missing from the top-K |
| yes | wrong | `GENERATION_FAILURE` — the evidence was there, badly used |
| — | right but `groundedness` < threshold | `GROUNDING_FAILURE` (needs the judge) |
| — | right | `SUCCESS` |
| — | HTTP error / timeout | `PIPELINE_ERROR` |

- `retrieval_ok` = **all** annotated evidence is within the top-K max (`max(top_k)`): strict for multi-hop.
- "Right answer" = judge `correctness` ≥ 0.5 if enabled, else Token F1 ≥ 0.5 (thresholds in `benchmark`).
  Without a judge, F1 is a coarse proxy: EM is ~0 whenever the wording differs.
- The report gives the 2×2 table (evidence × answer) and the share of wrong answers due to retrieval vs generation.

## Configuration (`configs/pipeline.yaml`)

Validated YAML (unknown keys rejected). `${VAR}` is resolved from the environment (URL, tokens); header values are masked in
`summary.json`. Anthropic judge: `ANTHROPIC_API_KEY` or `ant auth login`; `temperature` is not sent (refused by some recent models).

## Run outputs

- `traces.jsonl`: one line per question (written as it goes) — input, ground truth, full pipeline output, metrics, judge, analysis,
  diagnosis, latency, error.
- `summary.json`: `run` (run_id, timestamp, pipeline + version, dataset + version + sha256, configuration), aggregates,
  latency (mean/p50/p95), diagnosis counters, failure analysis.
- Pipeline errors count as 0 in the averages (and are flagged); latencies cover successes only.

## Layout

```
benchmark.py            CLI entry point (→ ragbench/cli.py)
ragbench/
  models.py             Pydantic structures (Sample, PipelineResult, Trace, Summary…)
  config.py  dataset.py YAML and JSONL loading/validation
  runner.py             loop dataset → pipeline → metrics → traces
  storage.py            results/<run_id>/ (incremental writing, reading back)
  pipelines/            base.py (PipelineAdapter), http.py (HTTPPipelineAdapter)
  evaluation/           retrieval.py, qa.py, judge.py, diagnosis.py
  reporting/            aggregator.py, report.py, analyze.py
examples/mock_pipeline.py   mock pipeline (does not import ragbench)
finance_benchmark/      FinanceBench V1: frozen corpus, annotation tools, dataset (see its README)
```

## Known V1 limits

Sequential execution (no parallelism, no resume after interruption — traces already written are kept); the Anthropic /
OpenAI-compatible judge is only tested with a fake client; no statistical comparison (confidence intervals) between runs;
on small datasets, differences between runs are not significant.
