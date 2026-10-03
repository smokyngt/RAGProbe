# FinanceBench V1.1 — dataset card

An English benchmark for question answering over real financial documents: **113 questions** over a **frozen corpus
of 17 public PDFs (1995 pages)**. Every answer is tied to the original document, PDF page and a verbatim quote.
It is designed to be run with the `ragbench` runner at the root of this repository (see the root README).

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
│   ├── finance_benchmark_v1.jsonl          ← the benchmark
│   ├── finance_benchmark_v1_review.json    review record per question (method, basis, checks, recompute)
│   ├── human_review_priority.json          the 20 questions a human should read first, with what to check
│   ├── finance_benchmark_v1_stats.json     distributions
│   └── excluded_flagged.json               questions withheld after adjudication, with the reason
├── annotation/              audit trail: annotator drafts, blind sets and answers, comparisons, adjudication verdicts,
│                            merged_draft.jsonl (everything needed to rebuild datasets/ from scratch)
├── tools/                   corpus, annotation and validation tools (below)
└── ANNOTATION_GUIDE.md      the rules annotators followed
```

## Corpus

| id | issuer | document | type | pages | primary Q | Q touching | evidence |
|---|---|---|---|---|---|---|---|
| `fin_doc_001` | European Central Bank | ECB Annual Accounts 2025 | annual_accounts | 87 | 5 | 5 | 5 |
| `fin_doc_002` | Belfius Bank | Belfius 2025 Pillar 3 Report | pillar3 | 111 | 5 | 7 | 12 |
| `fin_doc_003` | Belfius Insurance | Belfius Insurance consolidated SFCR 2025 (EN) | solvency_report | 71 | 6 | 6 | 7 |
| `fin_doc_004` | ASN Bank | ASN Bank Pillar 3 Report 2025 | pillar3 | 138 | 7 | 7 | 9 |
| `fin_doc_005` | M&G / Prudential International Assurance | Solvency and Financial Condition Report 31 Dec 2025 | solvency_report | 64 | 3 | 3 | 3 |
| `fin_doc_006` | Central Bank of the Republic of Türkiye | Annual Report 2025 (financial report, YFR_2025_V4) | annual_report | 135 | 5 | 5 | 7 |
| `fin_doc_007` | Luzerner Kantonalbank (LUKB) | LUKB Disclosure Report 2025 | regulatory_disclosure | 48 | 7 | 9 | 10 |
| `fin_doc_008` | Commonwealth Bank of Australia (CBA Europe NV) | CBA NV Pillar 3 Report 2025 | pillar3 | 67 | 2 | 3 | 6 |
| `fin_doc_009` | Guggenheim Global Investments plc | UCITS Annual Report & Audited Financial Statements FY2025 | fund_annual_report | 82 | 8 | 8 | 9 |
| `fin_doc_010` | Fresenius SE & Co. KGaA | Fresenius consolidated financial statements 2025 (extract of t | annual_report | 107 | 8 | 9 | 13 |
| `fin_doc_011` | DHL Group | DHL Group Annual Report 2025 | annual_report | 277 | 24 | 26 | 42 |
| `fin_doc_012` | DHL Group | DHL Group Annual Report 2024 | annual_report | 256 | 5 | 6 | 6 |
| `fin_doc_013` | Belfius Bank | Belfius Bank EMTN Programme Base Prospectus dated 6 May 2026 ( | prospectus | 224 | 7 | 7 | 12 |
| `fin_doc_014` | Guggenheim Global Investments plc | UCITS Prospectus (Germany version) | prospectus | 131 | 4 | 4 | 9 |
| `fin_doc_015` | Autorité des marchés financiers (AMF) | AMF 2025 Annual Report (English) | regulator_report | 175 | 5 | 5 | 7 |
| `fin_doc_016` | Belfius Bank | Belfius annual results 2025: press release | earnings_release | 12 | 2 | 2 | 5 |
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
 "reference_answer": "… 1,540 / 5,246 = 29.4% …",
 "evidence": [{"document_id": "fin_doc_011", "page": 162, "text": "€m Note 2024 2025 … Profit before income taxes 5,062 5,246 Income taxes 19 -1,494 -1,540"}],
 "metadata": {"type": "calculation", "style": "lookup", "difficulty": "medium", "requires_calculation": true,
              "requires_multiple_documents": false, "answerable": true, "tier": "gold", "topic": "profitability",
              "failure_modes": ["terminology_mismatch"]},
 "calculation": {"inputs": {"2025_income_taxes": -1540000000, "2025_profit_before_income_taxes": 5246000000},
                 "operation": "-2025_income_taxes / 2025_profit_before_income_taxes", "result": 0.29356,
                 "input_sources": {"…": {"evidence_index": 0, "raw": "-1,540", "unit": "€ million", "scale": 1000000}}}}
```

| | |
|---|---|
| type | table 38, calculation 19, temporal 12, direct 11, multi_document 9, multi_evidence 7, definition 7, negative 6, risk 4 |
| style (form) | lookup 31, comparison 23, explanatory 13, yes_no 12, superlative 10, count 6, list 5, conditional 5, ranking 5, trend 3 |
| difficulty | medium 75, hard 20, easy 18 |
| flags | 23 with a calculation · 9 multi-document · 6 unanswerable |
| retrieval traps (`failure_modes`) | same metric multiple years 44 · similar table labels 37 · multiple entities 27 · header dependency 25 · terminology mismatch 24 · split across pages 23 · multi evidence combination 22 · footnote 19 · unit mismatch 13 · deep in report 3 |

Conventions: page = 1-based PDF page index (not the printed number); evidence text = verbatim `pdftotext -layout` excerpt, `…` joins
fragments of the same page; calculation `inputs` are in base units (`raw × scale`), results unrounded, percentages and percentage-point
gaps as fractions (1.68 pp → 0.0168); answers state currency, scale and period; unanswerable questions have `evidence: []` and an answer
stating that the information cannot be established from the documents.

## Validation

Same protocol for the three annotation waves (50 + 40 + 24 questions):

1. **Annotation** by parallel model agents, one per document group, following `ANNOTATION_GUIDE.md`.
2. **Automatic checks** (`tools/validate_dataset.py`): schema and flag consistency; every evidence quote found verbatim on its page;
   every calculation re-evaluated; every input found as printed in its evidence with `raw × scale = value`.
3. **Blind re-answer:** separate agents answered every question from the PDFs only, without the reference answer or evidence.
4. **Adjudication:** every disagreement or reviewer doubt (all of wave 3) was re-checked against the source by a third agent:
   confirmed / fixed / withheld. 41 questions were rewritten (ambiguous scope or basis, unsupported claim, incomplete footnote evidence);
   `fin_q_102` was withheld (two conflicting fee figures in the source).

**No human has reviewed these questions.** Each review entry states `method: llm_blind_reverify, human_reviewed: false`;
`tier: gold` means "checked against the source by an independent pass plus adjudication". Annotators and reviewers belong to the same
model family, so shared blind spots are possible. Read these 20 first (`datasets/human_review_priority.json` lists what to check for each):

| # | id | type / style | main reasons |
|---|---|---|---|
| 1 | `fin_q_014` | multi_document / comparison | multi-document; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 2 | `fin_q_113` | multi_document / explanatory | calculation; multi-document; rewritten by adjudicator (ambiguity existed) |
| 3 | `fin_q_112` | multi_document / comparison | multi-document; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 4 | `fin_q_105` | calculation / comparison | calculation; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 5 | `fin_q_057` | calculation / comparison | calculation; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 6 | `fin_q_096` | table / lookup | rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication; unit_mismatch |
| 7 | `fin_q_030` | multi_document / comparison | multi-document; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 8 | `fin_q_053` | calculation / superlative | calculation; style=superlative; rewritten by adjudicator (ambiguity existed) |
| 9 | `fin_q_084` | table / superlative | style=superlative; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 10 | `fin_q_093` | calculation / yes_no | calculation; style=yes_no; scope/basis issue discussed in adjudication |
| 11 | `fin_q_111` | multi_evidence / list | style=list; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 12 | `fin_q_010` | calculation / lookup | calculation; scope/basis issue discussed in adjudication; similar_table_labels |
| 13 | `fin_q_039` | calculation / lookup | calculation; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 14 | `fin_q_041` | multi_evidence / conditional | style=conditional; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 15 | `fin_q_051` | calculation / superlative | calculation; style=superlative; rewritten by adjudicator (ambiguity existed) |
| 16 | `fin_q_052` | table / ranking | style=ranking; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 17 | `fin_q_074` | table / superlative | style=superlative; scope/basis issue discussed in adjudication; unit_mismatch |
| 18 | `fin_q_077` | table / yes_no | style=yes_no; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |
| 19 | `fin_q_079` | table / count | style=count; rewritten by adjudicator (ambiguity existed); similar_table_labels |
| 20 | `fin_q_092` | calculation / comparison | calculation; rewritten by adjudicator (ambiguity existed); scope/basis issue discussed in adjudication |

## Using it

With the runner at the repository root (no conversion needed: the runner matches evidence by document + page, or by text overlap):

```bash
python benchmark.py run --dataset finance_benchmark/datasets/finance_benchmark_v1.jsonl --config configs/financebench.yaml
```

Use the LLM judge: reference answers are explanatory (median ~54 words) and 49 questions ask several things at once, so Exact Match
and Token F1 are only indicative.

## Tools and reproducibility

```bash
python finance_benchmark/tools/fetch_corpus.py --freeze      # verify every SHA-256 (no change → nothing rewritten)
python finance_benchmark/tools/extract_pages.py --doc fin_doc_011 --page 162      # read a page (text cached in analysis/, git-ignored)
python finance_benchmark/tools/build_draft.py                # annotation/drafts + adjudication → annotation/merged_draft.jsonl
python finance_benchmark/tools/build_review.py               # blind answers + adjudication → datasets/…_review.json
python finance_benchmark/tools/validate_dataset.py --export  # must report errors=0; writes datasets/finance_benchmark_v1.jsonl
python finance_benchmark/tools/report_stats.py ; python finance_benchmark/tools/human_review_priority.py
```

Running these from a fresh clone reproduces `datasets/` byte for byte. Annotation tools: `make_blind_sets.py` (questions only, for blind
reviewers), `compare_blind.py` (automatic comparison, crude on purpose: every flag goes to adjudication).

## Adding the URD

A French URD is only published as a PDF on the issuer's site (the AMF's BDIF database serves URDs as XHTML/ZIP). The selected candidate
is Guillemot Corporation's 2025 URD (`candidates.json`, `c24`), whose domain was blocked. To add it: allow `*.guillemot.com` in the
environment's network settings (or pick another issuer and update `c24`), set `"selected": true`, run
`python finance_benchmark/tools/fetch_corpus.py --label v1.2` (new id `fin_doc_018`, ids never reused, freeze history kept), then annotate
~6 questions with the same protocol and rebuild `datasets/`.

## Known limits

- DHL 2025 is the primary source of ~21% of the questions; a few documents are lightly covered (M&G/PIA, CBA Europe, Belfius release).
- Only 6 unanswerable questions, and 5 of them rely on the same pattern (a period after the reports' date).
- Questions are explicit about entity, period and basis (that is what makes them unambiguous), so they are longer and more lexically
  helpful to a retriever than real user questions.
- Several answers hinge on a stated basis (CRR2 vs pro forma CRR3, before/after special items, rounded vs component sums): a pipeline
  that ignores footnotes is expected to fail them.
