# FinanceBench V1 — annotation guide (English benchmark)

All questions, reference answers, notes and metadata are written in **English**. The corpus is frozen
(`corpus/FROZEN.json`); never modify it. Document ids and page counts: `corpus/manifest.json`.

## Reading the documents

```bash
python finance_benchmark/tools/extract_pages.py --doc fin_doc_011 --page 120        # print one page (1-based)
python finance_benchmark/tools/extract_pages.py --doc fin_doc_011 --page 120-122
python finance_benchmark/tools/extract_pages.py --doc fin_doc_011 --grep "free cash flow"   # find pages
```

Page numbers are PDF page indexes (1 = first page of the file), NOT the numbers printed on the page.
Text is `pdftotext -layout`: tables are column-aligned. Always read the table header/unit line (e.g. "€ million").

## Example format (one JSON object per line)

```json
{"id": "fin_q_001", "question": "...", "reference_answer": "...",
 "evidence": [{"document_id": "fin_doc_011", "page": 120, "text": "verbatim excerpt"}],
 "metadata": {"type": "table", "difficulty": "medium", "requires_calculation": false,
              "requires_multiple_documents": false, "answerable": true, "tier": "gold",
              "topic": "profitability", "failure_modes": ["header_dependency"]},
 "calculation": null}
```

- `type`: direct | table | temporal | calculation | multi_evidence | multi_document | definition | risk | negative.
- `difficulty`: easy | medium | hard. `tier`: always `gold`.
- `failure_modes` (≥1 when genuinely applicable): same_metric_multiple_years, similar_table_labels, multiple_entities,
  footnote, terminology_mismatch, unit_mismatch, split_across_pages, header_dependency, deep_in_report, multi_evidence_combination.
- `topic`: short free label such as `risk:credit`, `risk:liquidity`, `risk:market`, `risk:operational`, `risk:concentration`,
  `capital:CET1`, `solvency`, `profitability`, `cash_flow`, `segment`, `fund_expenses`, `accounting_policy`.

## Rules

1. **Question quality.** Realistic questions from an analyst / auditor / investor / compliance / finance-team member. Self-contained:
   name the entity, period and scope (consolidated vs standalone, group vs bank) explicitly. Do not mention page or table numbers.
   Avoid trivial lookups of the first number on a page; prefer questions where the pipeline can be wrong for a reason listed in `failure_modes`.
   Use terminology a user would use even when the report words it differently (e.g. "operating profit" for "EBIT").
2. **Evidence = original document.** `document_id` + 1-based `page` + a **verbatim** excerpt copied from the extracted page text
   (1–6 lines; use `…` to skip text on the same page). It must contain every raw number the answer relies on AND the unit/header line
   needed to read them (e.g. `€ million`) — if the header is far from the row, include both fragments joined with `…`.
   Never use RAG chunk ids. If information is split across pages, list one evidence item per page.
3. **Units and currencies are never dropped.** Answers state currency and scale ("€1,284 million, i.e. €1.284 billion"), percentages as %,
   ratios as x or %, and basis points as bp. Keep the report's sign convention (negative numbers in parentheses = losses/outflows).
4. **Calculations** (`requires_calculation: true`): deterministic arithmetic only (difference, % change, ratio, margin, sum).
   ```json
   "calculation": {"inputs": {"2024_revenue": 120000000, "2025_revenue": 150000000},
                   "operation": "(2025_revenue - 2024_revenue) / 2024_revenue", "result": 0.25,
                   "input_sources": {"2024_revenue": {"evidence_index": 0, "raw": "120.0", "unit": "€ million", "scale": 1000000},
                                     "2025_revenue": {"evidence_index": 0, "raw": "150.0", "unit": "€ million", "scale": 1000000}}}
   ```
   `inputs` are in base units (`raw × scale`); `raw` is the number exactly as printed in the cited evidence text (e.g. `1,284`, `(213)`, `12.5`);
   percentages use `scale: 0.01`, basis points `0.0001`. `result` is unrounded; the reference answer states the rounding (e.g. one decimal).
   Percent change/margins: result as a fraction (0.25 = 25%). Inputs must come from the evidence, never from memory.
5. **Multi-document** questions cite evidence from ≥ 2 documents (`requires_multiple_documents: true`), e.g. the same metric in two
   reporting periods or two institutions. **Multi-evidence** needs ≥ 2 evidence items from one document.
6. **Negative / unanswerable** questions: plausible, specific, but the corpus must NOT contain the answer. Prove it: search all 12
   documents (`--grep` for the key terms and synonyms) before keeping the question. `evidence: []`, `answerable: false`,
   `type: negative`, and the answer must state "cannot be established from the available documents" and say what is missing.
   Good patterns: a different reporting year (FY2026 / forward-looking numbers not reported), a different entity not in the corpus,
   a metric the report explicitly does not disclose.
7. **Ambiguity.** If a question has two defensible answers (two scopes, two definitions), fix the question, don't guess.
8. **Never invent.** Every number and definition must be read from the page. If you are not sure, drop the question.
9. Self-check before returning: `python finance_benchmark/tools/validate_dataset.py --draft <your file> --no-review`
   (errors about missing review entries do not apply in this mode). Fix every ERR it reports.

## Review file (written later, after blind re-answering)

`datasets/finance_benchmark_v1_review.json` — per question: `status` (verified|flagged), `method`
(`manual` | `manual_sample` | `llm_blind_reverify` | `automated`), `human_reviewed` (must be `false` for `llm_blind_reverify`),
the 10 checks (answer_correctness, numerical_correctness, currency, units, reporting_period, entity, evidence_location,
calculation, ambiguity, completeness), `independent_recompute`, `notes`.
