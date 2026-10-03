# FinanceBench V1.1 — frozen financial corpus and independently checked QA ground truth (English)

**Status: complete EXCEPT the French URD category (blocked by the network policy — see "Finishing the URD step"). 113 verified questions over 17 documents / 1995 pages. The RAG has not been run, and nothing here was produced or validated with it.**

```
finance_benchmark/
├── corpus/
│   ├── documents/fin_doc_001.pdf … fin_doc_017.pdf   17 public PDFs, read-only
│   ├── manifest.json        provenance per document: source_url, domain, retrieved_at, SHA-256, pages, added_in
│   ├── FROZEN.json          current freeze + freeze_history (v1: 12 docs / 1,443 p.; v1.1: 17 docs / 1995 p.)
│   └── candidates.json      discovery log (dork-style searches; selected / reserve / excluded + why)
├── datasets/
│   ├── finance_benchmark_v1.jsonl          the benchmark: 113 verified examples (ids fin_q_001…114; fin_q_102 withheld)
│   ├── finance_benchmark_v1_review.json    per-question review record (method, basis, checks, recompute)
│   ├── human_review_priority.json          the 20 questions a human should read first, with the reason and what to check
│   ├── finance_benchmark_v1_stats.json     distributions (types, styles, documents, evidence)
│   ├── excluded_flagged.json               questions withheld by adjudication (fin_q_102) and why
│   └── finance_benchmark_v1_draft.jsonl, style_tags_wave1.json
├── validation_artifacts/    annotator drafts, blind re-answers, comparisons, adjudication verdicts (audit trail)
├── tools/                   fetch_corpus (--freeze / --add), extract_pages, make_blind_sets, compare_blind, build_draft,
│                            build_review, validate_dataset, human_review_priority, report_stats
└── ANNOTATION_GUIDE.md
```

## Corpus (frozen, 17 documents, 1995 pages)

Original 12 (v1): ECB annual accounts 2025 · Belfius Bank Pillar 3 · Belfius Insurance SFCR · ASN Bank Pillar 3 · M&G/PIA SFCR ·
Central Bank of Türkiye · Luzerner Kantonalbank · CBA Europe NV Pillar 3 · Guggenheim UCITS annual report · Fresenius consolidated
statements · DHL annual reports 2025 and 2024.
Added in v1.1 to cover the missing categories (all downloaded from the issuer's or regulator's own site, SHA-256 recorded):
**prospectus** — Belfius Bank EMTN Base Prospectus dated 6 May 2026 (224 p.) and Guggenheim UCITS prospectus (131 p., the "Germany"
version dated 9 Nov 2023 consolidating the 4 Sep 2023 prospectus); **regulator report** — AMF 2025 Annual Report, English (175 p.,
15 image-only pages); **earnings/results releases** — Belfius FY2025 (12 p.) and Fresenius Q4/FY2025 (10 p.).
Correction log: the first download for fin_doc_015 was a 3-page web print of the AMF page; it was replaced in place by the real report
*before any annotation used it* (recorded in `manifest.json` and `FROZEN.json`); the fetch tool now rejects PDFs under 4 pages.
Not obtainable: SEC Agency Financial Report (sec.gov "Request Rate Threshold Exceeded"), Bahamas central bank, MetLife IM UCITS.

## Finishing the URD step (the only missing category)

A French Universal Registration Document is only published as a PDF on the issuer's own site (the AMF's BDIF database holds URDs as
XHTML/ZIP plus a 2-page visa PDF). The selected candidate is **Guillemot Corporation URD 2025** (`candidates.json` c24); its domain is
refused by the environment's egress policy. To finish:
1. Network access → add the allowed domain `*.guillemot.com` (one entry; any other French issuer's URD PDF works too — update `c24`).
2. Set `"selected": true` on c24 and run `python finance_benchmark/tools/fetch_corpus.py --add --label v1.2` (ids are never reused; the freeze history gets a new entry).
3. Annotate ~6 URD questions with the same protocol (`ANNOTATION_GUIDE.md` → blind re-answer → adjudication → `build_draft`, `build_review`, `validate_dataset --export`), then regenerate stats and the priority list.

## Dataset (113 questions)

| | |
|---|---|
| `type` | table 38, calculation 19, temporal 12, direct 11, multi_document 9, multi_evidence 7, definition 7, negative 6, risk 4 |
| `style` (form of the question) | lookup 31, comparison 23, explanatory 13, yes_no 12, superlative 10, count 6, list 5, conditional 5, ranking 5, trend 3 |
| flags | 23 with a `calculation` block · 9 need several documents · 6 unanswerable from the corpus |
| difficulty | medium 75, hard 20, easy 18 |
| top failure-mode tags | same_metric_multiple_years 44, similar_table_labels 37, multiple_entities 27, header_dependency 25, terminology_mismatch 24, split_across_pages 23, multi_evidence_combination 22, footnote 19 |

Wave 3 (23 questions kept of 24) targets the structures the first 90 under-represented: cross-referenced definitions, prospectus risk
factors and regulatory limits, footnoted tables, regulator statistics and accounts, guidance/outlook, release-vs-audited-report comparisons.

### Documents: primary questions, questions touching the document, evidence items

| document | title | type | pages | primary | touching | evidence |
|---|---|---|---|---|---|---|
| fin_doc_001 | European Central Bank — ECB Annual Accounts 2025 | annual_accounts | 87 | 5 | 5 | 5 |
| fin_doc_002 | Belfius Bank — Belfius 2025 Pillar 3 Report | pillar3 | 111 | 5 | 7 | 12 |
| fin_doc_003 | Belfius Insurance — Belfius Insurance consolidated SFCR 2025 (EN) | solvency_report | 71 | 6 | 6 | 7 |
| fin_doc_004 | ASN Bank — ASN Bank Pillar 3 Report 2025 | pillar3 | 138 | 7 | 7 | 9 |
| fin_doc_005 | M&G / Prudential International Assurance — Solvency and Financial Condition Report 31 Dec 2025 | solvency_report | 64 | 3 | 3 | 3 |
| fin_doc_006 | Central Bank of the Republic of Türkiye — Annual Report 2025 (financial report, YFR_2025_V4) | annual_report | 135 | 5 | 5 | 7 |
| fin_doc_007 | Luzerner Kantonalbank (LUKB) — LUKB Disclosure Report 2025 | regulatory_disclosure | 48 | 7 | 9 | 10 |
| fin_doc_008 | Commonwealth Bank of Australia (CBA Europe NV) — CBA NV Pillar 3 Report 2025 | pillar3 | 67 | 2 | 3 | 6 |
| fin_doc_009 | Guggenheim Global Investments plc — UCITS Annual Report & Audited Financial Statements FY2025 | fund_annual_report | 82 | 8 | 8 | 9 |
| fin_doc_010 | Fresenius SE & Co. KGaA — Fresenius consolidated financial statements 2025 (extract  | annual_report | 107 | 8 | 9 | 13 |
| fin_doc_011 | DHL Group — DHL Group Annual Report 2025 | annual_report | 277 | 24 | 26 | 42 |
| fin_doc_012 | DHL Group — DHL Group Annual Report 2024 | annual_report | 256 | 5 | 6 | 6 |
| fin_doc_013 | Belfius Bank — Belfius Bank EMTN Programme Base Prospectus dated 6 May 20 | prospectus | 224 | 7 | 7 | 12 |
| fin_doc_014 | Guggenheim Global Investments plc — UCITS Prospectus (Germany version) | prospectus | 131 | 4 | 4 | 9 |
| fin_doc_015 | Autorité des marchés financiers (AMF) — AMF 2025 Annual Report (English) | regulator_report | 175 | 5 | 5 | 7 |
| fin_doc_016 | Belfius Bank — Belfius annual results 2025: press release | earnings_release | 12 | 2 | 2 | 5 |
| fin_doc_017 | Fresenius SE & Co. KGaA — Fresenius press release Q4 and FY 2025 | earnings_release | 10 | 4 | 4 | 9 |

DHL 2025 (fin_doc_011) is the primary source of ~21% of the questions; fin_doc_005, 008, 016 are lightly covered.

Every example has `evidence` = `{document_id, page, text}` from the **original PDF** (1-based PDF page; verbatim `pdftotext -layout`
excerpt) — never RAG chunk ids. Units, currencies and scales are kept in answers; calculations carry `inputs` (base units),
`operation`, `result` (unrounded) and `input_sources` (number as printed, unit, scale). Percentage-point gaps use scale 0.01
(1.68 pp → 0.0168). Negative questions have `evidence: []`, `answerable: false` (each searched across the whole corpus).

## How it was validated — and what that does NOT mean

Same protocol for all three waves: (1) annotation by parallel Claude agents per document group (guide: `ANNOTATION_GUIDE.md`);
(2) automatic checks — schema, every evidence excerpt **verbatim** on its cited page, every calculation re-evaluated, every input found
as printed with `raw × scale = value`; (3) separate agents re-answered every question **blind** from the PDFs;
(4) automatic comparison, then **adjudication** by third agents who re-read the sources (confirmed / fix / flag) — wave 1: 33 questions,
wave 2: 35, wave 3: all 24. Across the three waves 41 questions were rewritten (ambiguous scope or basis, unsupported claims, loose
wording, incomplete footnote evidence) and 1 was withheld (fin_q_102: the Directors' fees differ between the income statement and
Note 10, and whether pension contributions count as "remuneration" changes the answer).
**No human has reviewed these examples.** Every review entry says `method: llm_blind_reverify, human_reviewed: false`; `tier: gold`
means "checked against the source by an independent pass plus adjudication", not "human verified". Annotators and reviewers are the
same model family, so shared blind spots are possible.

### The 20 questions to review first (`datasets/human_review_priority.json`)

Explainable additive score (calculation, superlative/ranking/count/list, multi-document, rewritten by adjudicator, scope/basis words,
unit mismatch, look-alike values, blind-reviewer doubt, multi-page evidence), max 5 per primary document:
fin_q_014, fin_q_113, fin_q_112, fin_q_105, fin_q_057, fin_q_096, fin_q_030, fin_q_053, fin_q_084, fin_q_093, fin_q_111, fin_q_010, fin_q_039, fin_q_041, fin_q_051, fin_q_052, fin_q_074, fin_q_077, fin_q_079, fin_q_092.
Each entry lists why it was selected and what to check (recompute from the page, scan every row for the extreme, confirm the basis…).

## Known limits

- URD category still missing (above). Only 6 negative questions; DHL 2025 over-represented.
- Evidence text comes from `pdftotext -layout`; another PDF parser splits table rows differently, so mapping evidence to RAG chunks
  must use fuzzy overlap on numbers and labels, not exact string equality.
- Several answers hinge on a stated basis (CRR2 vs pro forma CRR3, before/after special items, rounded vs component sums); the question
  wording pins it, but a pipeline that ignores footnotes will fail exactly as intended.
- 113 questions is not the 1,000-question silver tier, which has deliberately not been started.

## Reproduce

```bash
python finance_benchmark/tools/fetch_corpus.py --freeze        # verify SHA-256 of all documents and re-freeze
python finance_benchmark/tools/build_draft.py                  # merge waves + adjudication fixes (drops flagged)
python finance_benchmark/tools/build_review.py                 # review record from blind answers + adjudication
python finance_benchmark/tools/validate_dataset.py --export    # errors=0 required; rewrites finance_benchmark_v1.jsonl
python finance_benchmark/tools/report_stats.py ; python finance_benchmark/tools/human_review_priority.py
```

## Next phase (not done here)

Ingest `corpus/documents/` into the Prosperify RAG, convert each `evidence` (document, page, text) into `relevant_chunks` for the
`ragbench` runner by text overlap, then run `finance_benchmark_v1.jsonl`. Do not use the RAG to edit the ground truth.
