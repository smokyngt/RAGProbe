# FinanceBench V1.1 — dataset card

An English benchmark for question answering over real financial documents: **120 questions** over a **frozen corpus
of 17 public PDFs (1995 pages)**. Every answer is tied to the original document, PDF page and a verbatim quote. Every question
also has a short natural phrasing and, when answerable, the key facts a correct answer must contain.
It can be run with any runner (see [Using it](#using-it)) or with the `ragbench` runner at the root of this repository.

> **Status.** Complete except one category: a French Universal Registration Document (URD), blocked by the network policy of the
> environment it was built in (see [Adding the URD](#adding-the-urd)). No human has reviewed the questions yet (see [Validation](#validation)).

## Contents

```
finance_benchmark/
├── corpus/
│   ├── documents/fin_doc_001.pdf … fin_doc_017.pdf   read-only
│   ├── manifest.json        provenance per document: source URL, domain, retrieval time, SHA-256, pages, batch
│   ├── FROZEN.json          current freeze (manifest hash) + freeze history
│   ├── candidates.json      discovery log: selected / reserve / excluded documents and why
│   └── fetch_report*.json   download logs
├── datasets/
│   ├── finance_benchmark_v1.jsonl          ← the benchmark (full annotation)
│   ├── financebench_v1_simple.jsonl / .csv ← question / answer / document(s) / pages only, for an external runner
│   ├── finance_benchmark_v1_review.json    review record per question (method, basis, checks, recompute)
│   ├── human_review_priority.json          the 20 questions a human should read first, with what to check
│   ├── relevance_report.json               relevance scores of every question (before retirements and rewrites)
│   ├── finance_benchmark_v1_stats.json     distributions
│   └── excluded.json                       questions withheld or retired, with the reason
├── annotation/              audit trail: drafts, blind sets and answers, comparisons, adjudication, enrichment (natural
│                            phrasing + key facts), relevance reviews, repairs, retired.json, merged_draft.jsonl
├── tools/                   corpus, annotation and validation tools (below)
└── ANNOTATION_GUIDE.md      the rules annotators followed
```

## Corpus

| id | issuer | document | type | pages | primary Q | Q touching | evidence |
|---|---|---|---|---|---|---|---|
| `fin_doc_001` | European Central Bank | ECB Annual Accounts 2025 | annual_accounts | 87 | 7 | 7 | 10 |
| `fin_doc_002` | Belfius Bank | Belfius 2025 Pillar 3 Report | pillar3 | 111 | 5 | 6 | 10 |
| `fin_doc_003` | Belfius Insurance | Belfius Insurance consolidated SFCR 2025 (EN) | solvency_report | 71 | 6 | 6 | 6 |
| `fin_doc_004` | ASN Bank | ASN Bank Pillar 3 Report 2025 | pillar3 | 138 | 6 | 6 | 6 |
| `fin_doc_005` | M&G / Prudential International Assurance | Solvency and Financial Condition Report 31 Dec 2025 | solvency_report | 64 | 7 | 7 | 14 |
| `fin_doc_006` | Central Bank of the Republic of Türkiye | Annual Report 2025 (financial report, YFR_2025_V4) | annual_report | 135 | 5 | 5 | 7 |
| `fin_doc_007` | Luzerner Kantonalbank (LUKB) | LUKB Disclosure Report 2025 | regulatory_disclosure | 48 | 7 | 9 | 11 |
| `fin_doc_008` | Commonwealth Bank of Australia (CBA Europe NV) | CBA NV Pillar 3 Report 2025 | pillar3 | 67 | 5 | 6 | 16 |
| `fin_doc_009` | Guggenheim Global Investments plc | UCITS Annual Report & Audited Financial Statements FY2025 | fund_annual_report | 82 | 6 | 7 | 9 |
| `fin_doc_010` | Fresenius SE & Co. KGaA | Fresenius consolidated financial statements 2025 (extract) | annual_report | 107 | 7 | 8 | 12 |
| `fin_doc_011` | DHL Group | DHL Group Annual Report 2025 | annual_report | 277 | 22 | 24 | 39 |
| `fin_doc_012` | DHL Group | DHL Group Annual Report 2024 | annual_report | 256 | 5 | 6 | 6 |
| `fin_doc_013` | Belfius Bank | Belfius Bank EMTN Programme Base Prospectus dated 6 May 2026 | prospectus | 224 | 7 | 7 | 11 |
| `fin_doc_014` | Guggenheim Global Investments plc | UCITS Prospectus (Germany version) | prospectus | 131 | 5 | 5 | 11 |
| `fin_doc_015` | Autorité des marchés financiers (AMF) | AMF 2025 Annual Report (English) | regulator_report | 175 | 4 | 4 | 4 |
| `fin_doc_016` | Belfius Bank | Belfius annual results 2025: press release | earnings_release | 12 | 2 | 2 | 3 |
| `fin_doc_017` | Fresenius SE & Co. KGaA | Fresenius press release Q4 and FY 2025 | earnings_release | 10 | 4 | 4 | 9 |

All documents were downloaded from the issuer's or regulator's own website (provenance and SHA-256 in `manifest.json`).
Institution types: banks, insurers, central banks, a UCITS fund, industrial groups, a market regulator. Document types: annual reports
and accounts, Pillar 3 and solvency reports, financial statements, a fund report, two prospectuses, two results releases, a regulator report.
Batches: v1 (`fin_doc_001`–`012`, 1,443 pages) and v1.1 (`013`–`017`, adding prospectus, regulator report and results releases).
`fin_doc_015` was first downloaded as a 3-page web print; it was replaced by the real report before any annotation used it (logged in
the manifest). Not obtainable: SEC agency financial report (rate limit), Bahamas central bank (403), MetLife UCITS (HTML disclaimer).

## Questions

```json
{"id": "fin_q_011",
 "question": "What was DHL Group's effective income tax rate for fiscal year 2025 (income taxes divided by profit before income taxes, consolidated)? Give the answer as a percentage to one decimal place.",
 "question_natural": "What was DHL Group's effective tax rate in 2025?",
 "reference_answer": "… 1,540 / 5,246 = 29.4% …",
 "key_facts": [{"fact": "effective tax rate FY2025", "value": "29.4%", "accept": ["29.36%", "29.4 per cent"]}],
 "evidence": [{"document_id": "fin_doc_011", "page": 162, "text": "€m Note 2024 2025 … Profit before income taxes 5,062 5,246 Income taxes 19 -1,494 -1,540"}],
 "metadata": {"type": "calculation", "style": "lookup", "difficulty": "medium", "requires_calculation": true,
              "requires_multiple_documents": false, "answerable": true, "tier": "gold", "topic": "profitability",
              "failure_modes": ["terminology_mismatch"]},
 "calculation": {"inputs": {"2025_income_taxes": -1540000000, "2025_profit_before_income_taxes": 5246000000},
                 "operation": "-2025_income_taxes / 2025_profit_before_income_taxes", "result": 0.29356,
                 "input_sources": {"…": {"evidence_index": 0, "raw": "-1,540", "unit": "€ million", "scale": 1000000}}}}
```

- `question` is explicit (entity, period, basis): it has exactly one defensible answer. `question_natural` is the same question as a
  user would type it (median 18 words vs 38); it relies on the same evidence and is the harder test for a retriever.
- `key_facts` are the values a correct answer must contain (with sign/direction when it matters, e.g. "down 5.9%", "-€431m"), with
  accepted variants. They allow deterministic scoring without a judge; unanswerable questions have none (they are scored on abstention).

| | |
|---|---|
| type | table 36, calculation 17, multi_evidence 14, temporal 13, negative 10, direct 9, multi_document 9, definition 6, risk 6 |
| style (form) | lookup 32, comparison 21, explanatory 17, yes_no 13, superlative 12, list 7, ranking 6, trend 4, conditional 4, count 4 |
| difficulty | medium 85, hard 22, easy 13 |
| flags | 25 require a calculation · 9 multi-document · 10 unanswerable · 3 false premise |
| key facts | 1–8 per answerable question |
| retrieval traps (`failure_modes`) | same metric multiple years 51 · similar table labels 37 · header dependency 32 · terminology mismatch 31 · multiple entities 27 · split across pages 27 · footnote 21 · multi evidence combination 20 · unit mismatch 14 · deep in report 8 |

**Negatives.** 10 unanswerable questions, 6 patterns: period after the report date (`fin_q_018`, `031`, `042`, `082`, `108`), entity
not in the corpus (`116`), metric the document does not publish (`118`: no income statement in a Pillar 3 report), figure merged into
another line for confidentiality (`119`), unpublished granularity (`120`: quarter alone), absent quantitative limit (`072`).
3 more questions carry a false premise (`fin_q_115` a profit distribution by an ECB that made a loss, `117` a solvency ratio said to
have fallen when it rose, `121` a sub-fund that does not exist): the correct answer corrects the premise from the documents.

Conventions: page = 1-based PDF page index (not the printed number); evidence text = verbatim `pdftotext -layout` excerpt, `…` joins
fragments of the same page; calculation `inputs` are in base units (`raw × scale`), results unrounded, percentages and percentage-point
gaps as fractions (1.68 pp → 0.0168); answers state currency, scale and period; unanswerable questions have `evidence: []` and an answer
stating that the information cannot be established from the documents.

## Validation

Same protocol for the four annotation waves and for every later rewrite:

1. **Annotation** by parallel model agents, one per document group, following `ANNOTATION_GUIDE.md`.
2. **Automatic checks** (`tools/validate_dataset.py`): schema and flag consistency; every evidence quote found verbatim on its page;
   every calculation re-evaluated; every input found as printed in its evidence with `raw × scale = value`; every key fact found in
   the reference answer.
3. **Blind re-answer:** separate agents answered every question from the PDFs only, without the reference answer or evidence.
4. **Adjudication:** every disagreement or reviewer doubt was re-checked against the source by a third agent: confirmed / fixed /
   withheld. `fin_q_102` was withheld (two conflicting fee figures in the source).
5. **Relevance review** (`datasets/relevance_report.json`, 131 questions scored 1–5 on user realism, decision value, financial depth,
   benchmark value, clarity): mean 3.63; clarity is high (4.48), depth and benchmark value lower (3.33 / 3.34); the AMF report scored
   lowest (2.84). Outcome: 13 questions retired (`annotation/retired.json`: Guggenheim TER near-duplicates, redundant or mechanical
   questions), 18 rewritten to ask something more useful, then re-verified with steps 2–4 (`annotation/repairs/`).
6. **Enrichment:** natural phrasing and key facts written for every question, then checked (`tools/check_enrichment.py`).

**No human has reviewed these questions.** Each review entry states `method: llm_blind_reverify, human_reviewed: false`;
`tier: gold` means "checked against the source by an independent pass plus adjudication". Annotators and reviewers belong to the same
model family, so shared blind spots are possible. Read these 20 first (`datasets/human_review_priority.json` lists what to check for each):

| # | id | type / style | main reasons |
|---|---|---|---|
| 1 | `fin_q_131` | calculation / ranking | calculation; style=ranking; rewritten by adjudicator (ambiguity existed) |
| 2 | `fin_q_014` | multi_document / comparison | multi-document; rewritten by adjudicator; scope/basis issue discussed in adjudication |
| 3 | `fin_q_026` | calculation / lookup | calculation; rewritten after the relevance review; rewritten by adjudicator |
| 4 | `fin_q_113` | multi_document / explanatory | calculation; multi-document; rewritten by adjudicator |
| 5 | `fin_q_129` | calculation / superlative | calculation; style=superlative; rewritten by adjudicator |
| 6 | `fin_q_030` | multi_document / comparison | calculation; multi-document; rewritten after the relevance review |
| 7 | `fin_q_074` | calculation / superlative | calculation; style=superlative; rewritten after the relevance review |
| 8 | `fin_q_123` | multi_evidence / superlative | calculation; style=superlative; rewritten by adjudicator |
| 9 | `fin_q_126` | calculation / lookup | calculation; rewritten after the relevance review; unit_mismatch |
| 10 | `fin_q_027` | calculation / lookup | calculation; rewritten after the relevance review; unit_mismatch |
| 11 | `fin_q_057` | calculation / comparison | calculation; rewritten by adjudicator; scope/basis issue discussed in adjudication |
| 12 | `fin_q_096` | table / lookup | rewritten after the relevance review; scope/basis issue; unit_mismatch |
| 13 | `fin_q_127` | risk / superlative | style=superlative; rewritten by adjudicator; unit_mismatch |
| 14 | `fin_q_041` | table / conditional | style=conditional; rewritten after the relevance review; rewritten by adjudicator |
| 15 | `fin_q_053` | calculation / superlative | calculation; style=superlative; rewritten by adjudicator |
| 16 | `fin_q_093` | calculation / yes_no | calculation; style=yes_no; scope/basis issue discussed in adjudication |
| 17 | `fin_q_111` | multi_evidence / list | style=list; rewritten by adjudicator; scope/basis issue discussed in adjudication |
| 18 | `fin_q_010` | calculation / lookup | calculation; scope/basis issue discussed in adjudication; similar_table_labels |
| 19 | `fin_q_051` | calculation / superlative | calculation; style=superlative; rewritten by adjudicator |
| 20 | `fin_q_077` | table / yes_no | style=yes_no; rewritten by adjudicator; scope/basis issue discussed in adjudication |

Also worth a look: `fin_q_128` — the adjudicator found that the report's printed 2025 corporate RWEA density (101.15%) does not follow
from the template's own formula (100.18%); the question no longer asks for it.

## Using it

**Any runner:** `datasets/financebench_v1_simple.jsonl` / `.csv` (`python tools/export_simple.py`) has one row per question:
`id`, `question`, `question_natural`, `answer`, `documents` (PDF file names in `corpus/documents/`), `pages` (`fin_doc_011.pdf:162`),
`answerable`. Ingest the 17 PDFs, send `question` (or `question_natural`), compare with `answer`; for unanswerable rows the expected
behaviour is an abstention. For deterministic scoring, take `key_facts` from the full JSONL.

**ragbench** (repository root; matches evidence by document + page, or by text overlap):

```bash
python benchmark.py run --dataset finance_benchmark/datasets/finance_benchmark_v1.jsonl --config configs/financebench.yaml
```

Set `question_field: question_natural` in the config to send the natural phrasing. Reference answers are explanatory (median ~65
words) and often answer several sub-questions: score with the LLM judge or the key facts; Exact Match and Token F1 are only indicative.

## Tools and reproducibility

```bash
python finance_benchmark/tools/fetch_corpus.py --freeze      # verify every SHA-256 (no change → nothing rewritten)
python finance_benchmark/tools/extract_pages.py --doc fin_doc_011 --page 162      # read a page (text cached in analysis/, git-ignored)
python finance_benchmark/tools/build_draft.py                # drafts + adjudication + enrichment + repairs - retired → annotation/merged_draft.jsonl
python finance_benchmark/tools/build_review.py               # blind answers + adjudication → datasets/…_review.json
python finance_benchmark/tools/validate_dataset.py --require-enrichment --export   # must report errors=0; writes the benchmark
python finance_benchmark/tools/report_stats.py ; python finance_benchmark/tools/human_review_priority.py
python finance_benchmark/tools/export_simple.py              # question / answer / document export
```

Running these from a fresh clone reproduces `datasets/` byte for byte. Annotation tools: `make_blind_sets.py` (questions only, for blind
reviewers), `compare_blind.py` (automatic comparison, crude on purpose: every flag goes to adjudication), `check_enrichment.py`,
`relevance_report.py`.

## Adding the URD

A French URD is only published as a PDF on the issuer's site (the AMF's BDIF database serves URDs as XHTML/ZIP). The selected candidate
is Guillemot Corporation's 2025 URD (`candidates.json`, `c24`), whose domain was blocked. To add it: allow `*.guillemot.com` in the
environment's network settings (or pick another issuer and update `c24`), set `"selected": true`, run
`python finance_benchmark/tools/fetch_corpus.py --label v1.2` (new id `fin_doc_018`, ids never reused, freeze history kept), then annotate
~6 questions with the same protocol and rebuild `datasets/`.

## Known limits

- DHL 2025 is still the primary source of 18% of the questions (22/120); the AMF report and the Belfius release are lightly covered.
- Half of the unanswerable questions use the same pattern (a period after the reports' date).
- `question` is explicit about entity, period and basis, hence longer and lexically helpful to a retriever; `question_natural` is the
  realistic variant.
- Several answers hinge on a stated basis (CRR2 vs pro forma CRR3, before/after special items, rounded vs component sums): a pipeline
  that ignores footnotes is expected to fail them.
- Relevance scores were given by a model, before the rewrites; they guide curation, they are not a measure of quality.
