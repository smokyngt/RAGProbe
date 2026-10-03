# FinanceBench V1 — frozen financial corpus and independently checked QA ground truth (English)

**Status: corpus frozen, 90 questions annotated and checked. The RAG has not been run, and nothing here was produced or validated with it.**

```
finance_benchmark/
├── corpus/
│   ├── documents/fin_doc_001.pdf … fin_doc_012.pdf   12 public PDFs, 1,443 pages, read-only
│   ├── manifest.json        provenance per document: source_url, domain, retrieved_at, SHA-256, pages
│   ├── FROZEN.json          frozen_at + manifest SHA-256 (tools/fetch_corpus.py --freeze)
│   └── candidates.json      discovery log (dork-style web searches; selected / reserve / excluded + why)
├── datasets/
│   ├── finance_benchmark_v1.jsonl          the benchmark: 90 verified examples
│   ├── finance_benchmark_v1_review.json    per-question review record (method, basis, checks, recompute)
│   ├── finance_benchmark_v1_draft.jsonl    merged annotations before export (same 90)
│   └── style_tags_wave1.json, excluded_flagged.json
├── validation_artifacts/    raw annotator drafts, blind re-answers, comparisons, adjudication verdicts (audit trail)
├── tools/                   fetch_corpus, extract_pages, make_blind_sets, compare_blind, build_draft, build_review, validate_dataset
└── ANNOTATION_GUIDE.md      the annotation rules used (units, evidence, calculations, styles, negatives)
```

## Corpus (frozen)

12 documents published by their issuers, all FY2025 except one prior-year report, all English, all with extractable text:
ECB annual accounts 2025 · Belfius Bank Pillar 3 2025 · Belfius Insurance SFCR 2025 · ASN Bank Pillar 3 2025 ·
M&G / Prudential International Assurance SFCR 2025 · Central Bank of the Republic of Türkiye annual report 2025 ·
Luzerner Kantonalbank disclosure report 2025 · CBA Europe NV Pillar 3 (30 June 2025) · Guggenheim Global Investments plc
UCITS annual report 2025 · Fresenius consolidated financial statements 2025 · DHL Group annual reports 2025 and 2024.
Institution types: banks, insurers, central banks, a UCITS fund, two industrial groups. 87–277 pages each.
Not covered (gaps from the brief): prospectus, regulator-authored report, French URD, earnings-release PDF. Excluded after
inspection: Bahamas central bank (origin 403), MetLife IM UCITS (URL returns an HTML disclaimer), FTI press release (HTML only).
Reserves for extending the corpus: NBG annual financial report (567 p.), Merck KGaA (565 p.), Fresenius full report (440 p.).

## Dataset (90 questions)

| | |
|---|---|
| `type` | table 34 · calculation 14 · direct 11 · temporal 11 · multi_document 6 · multi_evidence 5 · negative 5 · definition 3 · risk 1 |
| `style` (form of the question) | lookup 28 · comparison 17 · superlative 10 · explanatory 8 · yes_no 8 · count 5 · conditional 4 · ranking 4 · list 3 · trend 3 |
| flags | 17 with a `calculation` block · 6 need several documents · 5 unanswerable from the corpus |
| difficulty | easy 16 · medium 61 · hard 13 |

Distribution vs the requested 50-question mix: the first wave (50) matched it exactly; the second wave (40) added varied question
forms (superlatives, rankings, yes/no, lists/counts, trends, explanations, scenarios), so the final mix is table-heavy.
Failure-mode tags (retrieval traps): same metric in several years (36), similar table labels (31), several entities (26),
header dependency (22), footnote (14), split across pages (14), multi-evidence combination (10), unit mismatch (9), terminology mismatch (14).

Every example has `evidence` = `{document_id, page, text}` from the **original PDF** (page = PDF page index, 1-based; text is a
verbatim `pdftotext -layout` excerpt) — never RAG chunk ids. Units, currencies and scales are kept in answers (`€1,284 million`,
`TRY` in whole lira for the Turkish central bank, `bp`, `%`). Calculations carry `inputs` (base units), `operation`, `result`
(unrounded) and `input_sources` (the number as printed, its unit and scale), so a retrieval failure can be told apart from a
calculation failure. Negative questions have `evidence: []`, `answerable: false` and an answer saying the information cannot be
established from the available documents (each was grepped across all 12 documents).

## How it was validated — and what that does NOT mean

1. **Annotation** (two waves, parallel Claude agents, one per document group) following `ANNOTATION_GUIDE.md`; each agent self-checked with the validator.
2. **Automatic checks** (`tools/validate_dataset.py`): schema and flag consistency; every evidence excerpt found **verbatim** on the cited page; every calculation re-evaluated; every input found as printed in its evidence and `raw × scale = value`.
3. **Blind re-answer**: separate agents answered every question from the PDFs only, without seeing the reference answer or evidence (`validation_artifacts/blind/`).
4. **Comparison + adjudication**: disagreements and reviewer doubts (60 of 90 questions) went to third agents who re-read the sources and returned *confirmed* / *fix* / *flag*. 28 questions were rewritten (ambiguous scope or basis: CRR2 vs CRR3, before/after special items, total vs continuing operations, rounded vs component sums, an unsupported "what drove it" claim…); none had to be dropped. Blind reviewers were wrong on some points too (e.g. fin_q_056), which is why adjudicators checked the source, not the reviewer.
5. **My own spot checks** on several examples (tax rate, fund net-asset change, exposure sums, EVE scenarios) and on the negative question fin_q_042 against all documents.

**No human has reviewed these examples.** Every review entry says `method: llm_blind_reverify, human_reviewed: false`. The
`tier: gold` label means "checked against the source by an independent pass plus adjudication", not "human verified".
Annotators and reviewers are the same model family, so shared blind spots are possible. Recommended before relying on it for decisions:
a human spot check of ≥ 20 questions, prioritising calculation, superlative and unit-sensitive items.

## Known limits

- DHL (two reports) is cited by ~40% of the evidence; some documents (M&G/PIA, ECB) are lightly covered.
- Belfius's Pillar 3 PDF is a narrative risk report (its quantitative templates are in an annex not in the PDF); CBA's key-metrics and liquidity tables disagree on LCR, so CBA LCR is not asked.
- Some answers hinge on a stated basis (e.g. "before special items"); the question wording pins it, but a pipeline that ignores footnotes will fail exactly as intended.
- Evidence text comes from `pdftotext -layout`; a different PDF parser may split table rows differently, so mapping to RAG chunks should use fuzzy overlap on numbers and labels, not exact string equality.
- 90 questions is not the 1,000 requested. The tooling scales (`validate_dataset.py`, blind sets, comparison, review builder); a larger silver tier should be generated from tables and labelled `tier: silver`, with a ≥ 10% human sample.

## Reproduce

```bash
python finance_benchmark/tools/fetch_corpus.py --freeze     # (already done) verify SHA-256 and freeze
python finance_benchmark/tools/extract_pages.py --doc fin_doc_011 --page 162
python finance_benchmark/tools/build_draft.py               # merge waves + adjudication fixes
python finance_benchmark/tools/validate_dataset.py          # must report errors=0 (needs the review file)
python finance_benchmark/tools/validate_dataset.py --export # rewrites finance_benchmark_v1.jsonl (verified only)
```

## Next phase (not done here)

Ingest `corpus/documents/` into the RAG, convert each `evidence` (document, page, text) into `relevant_chunks` for the `ragbench`
runner by text overlap with the ingested chunks, then run `finance_benchmark_v1.jsonl`. Do not use the RAG to edit the ground truth.
