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
- `style` (form of the question, orthogonal to `type`): lookup | superlative | ranking | yes_no | comparison | list | count | trend |
  explanatory | conditional. See "Question styles" below. Default `lookup`.
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

## Question styles (vary the form, not only "What was X?")

| style | example shape | what the answer and evidence must contain |
|---|---|---|
| superlative | "Which division had the highest/lowest/largest decline in …?" | the extreme item AND its value; evidence must cover **every candidate** compared (all rows/segments/years/entities in scope), so the extreme is verifiable; no ties; scope and period explicit |
| ranking | "Rank the divisions by EBIT in 2025" / "the three largest …" | the full ordered list with values; evidence covers all ranked items |
| yes_no | "Did X exceed/meet Y?", "Was Z higher in 2025 than in 2024?" | Yes/No first, then the figures and threshold that justify it (a bare yes/no is never acceptable) |
| comparison | "Which was higher, A or B, and by how much?" | both values with units, the winner, the gap |
| list | "Which … reported a decline?", "List the …" | the complete list, nothing omitted; evidence covers the full set |
| count | "How many … ?" | the number plus the items counted |
| trend | "How did X evolve over 2023–2025?" (≥3 data points) | direction and the values for each period |
| explanatory | "What drove the change in …?" "Why did … ?" | the reasons exactly as the report states them (cite the passage; do not infer drivers the report does not give) |
| conditional | "What would the ratio be under the +50bp shock?", "If X were excluded, …" | the figure given by the report's sensitivity/scenario table or a deterministic recomputation with `calculation` |

Styles combine with any `type` (e.g. a `table` question with `superlative` style). Traps to avoid: superlatives with ties,
open scope ("largest company" when only some entities are in the document), and "why" questions whose causes are not in the text.

## Natural question and key facts (every question)

```json
"question_natural": "What was DHL's effective tax rate in 2025?",
"key_facts": [{"fact": "effective tax rate 2025", "value": "29.4%", "accept": ["29.36%", "29.4 per cent"]}]
```

- `question_natural` = how a real analyst would type it: short (aim ≤ 20 words, max 30), no document titles, section names,
  page or table references, no list of the candidate rows. Keep only what is needed so that the SAME reference answer stays the
  only defensible answer: entity, period, and the basis when the basis is the point of the question ("before special items",
  "in the results press release", "on a CRR3 basis"). If that is impossible, keep the extra words: ambiguity is worse than length.
- `key_facts` = 1–6 atomic facts a correct answer MUST contain, used for deterministic scoring (all present ⇒ correct):
  numbers with their unit, the extreme item of a superlative, every item of a list/ranking, the count of a count question,
  the defined term's essential content. `value` is copied as written in the reference answer (it must be found there by the
  matcher: thousands separators, spaces before %, and unicode minus signs are ignored); `accept` lists equivalent
  formulations (other scale "€1.54 billion", unrounded "29.36%", "EUR" vs "€"). Do not use bare "Yes"/"No" as a value: use the
  figures or the phrase that justify the verdict. Leave out context-only details ("for comparison…"). No key facts for
  unanswerable questions (abstention is scored separately).
- Check a file with `python tools/check_enrichment.py <file>`.

## Unanswerable questions: vary the pattern

Do not rely only on "a period after the report date". Patterns: an entity not in the corpus; a metric the document explicitly
does not disclose; a segment / sub-fund / share class that does not exist; a figure that would only be in a document type absent
from the corpus (e.g. a quarterly report); a false premise the documents contradict (the answer must say what the documents
actually show and that the premise cannot be confirmed). Grep all 17 documents (synonyms included) before keeping one.

## Review file (written later, after blind re-answering)

`datasets/finance_benchmark_v1_review.json` — per question: `status` (verified|flagged), `method`
(`manual` | `manual_sample` | `llm_blind_reverify` | `automated`), `human_reviewed` (must be `false` for `llm_blind_reverify`),
the 10 checks (answer_correctness, numerical_correctness, currency, units, reporting_period, entity, evidence_location,
calculation, ambiguity, completeness), `independent_recompute`, `notes`.
