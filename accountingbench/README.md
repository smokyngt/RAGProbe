# AccountingBench V1 — dataset card

An accounts-payable benchmark for document assistants (Prosperify): **20 deterministic questions** over a **corpus of
200 fictional but professional-grade documents** (180 PDFs totalling 329 pages: 90 single-page and 90 multi-page documents of 2 to 10 pages, 239 pages between them; 20 image-only scans; 20 e-mails as `.eml` files) from one company's September
2026 close. It uses the **same JSON format as FinanceBench** (`finance_benchmark/`), so it can be run with the `ragbench` runner at
the root of this repository or with any external runner.

It replaces the first accounting pilot (questions B1–B5 and T1–T15). Each question keeps the original **control intent**,
but is rewritten the way an engagement manager would brief a junior accountant: the entity, period and documents are named,
the control rule is stated, the output format is fixed, and the answer "cannot be determined" is allowed. Prosperify is
treated as a capable intern: the more precisely a question is briefed, the more an answer can be checked.

## Why a new corpus

The pilot's documents could not support a reliable test:

| pilot problem | what AccountingBench does instead |
|---|---|
| ~20 one-page documents: retrieval was barely exercised | 200 documents, 329 PDF pages. Only 46 are cited as evidence; the rest are routine flows, other months, a sister company, contracts, policies, sales invoices and unrelated documents |
| Invoices without VAT number, address, IBAN, PO, quantities or unit prices; one without VAT or due date | Invoices with the mandatory EU invoice mentions (art. 226 directive 2006/112/EC), 4 supplier layouts, line items, VAT summary, bank details, legal footer. The only non-compliant invoice (Quick Marine Repairs) is non-compliant on purpose and listed in the anomaly register |
| A "scanned copy" that was a clean digital PDF | 20 real image-only scans (rotated, noisy, no text layer): OCR is actually tested |
| Corrupted characters in a bank reference (`■■■FUEL 1182■■■`) | No accidental defects; every anomaly is planted on purpose and recorded |
| File titles giving the answer away (`Email MarinaFuel Discrepancy`, `Sept_Final`) | Neutral file names (`acc_doc_001` … `acc_doc_200`) in a shuffled order |
| Every document one page long; e-mails printed as PDFs | Half of the PDFs are multi-page, as long as their real counterparts: procurement policy with annexes (10 pages), 2025 internal audit report (9), 2025 annual accounts (8), vessel survey (7), insurance policy (6), AP ledger July–September (6), bank statements with end-of-day balances, fees and information annexes (4–5), double-entry purchase journal with centralisation (5), lease, IT and berth contracts, supplier statements since January, invoices with call detail, IT service report or terms of sale overleaf, POs above EUR 5,000 with purchasing conditions overleaf. The other half stays single-page: delivery notes, payment notices, aged payables, master file, small invoices. E-mails are real `.eml` messages (headers, plain text + HTML), one message per file |
| Open questions ("do a full review", "is the rest expected later or split?") with no single answer | One verifiable answer per question; any judgement is settled by a rule stated in the question |
| Totals that could not be traced (`Total paid EUR 40,880`) | Every total is reconcilable line by line and checked against the statement total |
| Store isolation "tested" through an accounting answer | A technical probe: a document ingested only in another store (see T15) |

## Contents

```
accountingbench/
├── corpus/
│   ├── documents/acc_doc_001 … acc_doc_200 (.pdf, .eml)   ← the ONLY folder to ingest
│   ├── manifest.json         per document: type, issuer, addressee, date, language, pages, scanned, SHA-256, internal key
│   ├── FROZEN.json           manifest hash
│   └── ocr_reference/        reference text of the 20 scans (used only to check evidence quotes; never ingest)
├── isolation_probe/probe_doc_001.pdf   ← ingest in a DIFFERENT store (T15)
├── datasets/
│   ├── accountingbench_v1.jsonl             ← the benchmark (full annotation, FinanceBench schema)
│   ├── accountingbench_v1_simple.jsonl/.csv ← id / question / answer / documents / pages, for an external runner
│   ├── accountingbench_v1_review.json       blind re-answer review per question (20/20 verified)
│   └── anomaly_register.json                18 planted anomalies + 3 decoys, their documents and the questions testing them
├── annotation/               blind answers (2 independent agents) and adjudication of every reported ambiguity
├── tools/
│   ├── world.py              the fictional company, suppliers, orders, deliveries, invoices, payments (single source of truth)
│   ├── render.py             PDF layouts (invoices x4 styles, PO, delivery note, bank statement, ledger, journal, e-mail…)
│   ├── generate_corpus.py    world -> corpus (deterministic: same code, same files)
│   ├── build_dataset.py      world + corpus -> questions; expected answers are computed, never typed
│   ├── build_review.py       blind answers + adjudication -> review file
│   └── validate.py           FinanceBench validation rules applied to AccountingBench
└── PROMPT_creation_benchmark_comptable.md   the design brief this benchmark implements
```

**Never ingest** `manifest.json`, `ocr_reference/`, `datasets/` or `tools/`: they contain the answers.

## Scenario

**Azur Marine Services S.A.M.** (yacht management, Monaco, VAT FR 64 000 512 748) closes **September 2026**; July, August
and early October give history and subsequent events. The company manages three yachts (M/Y Aurelia, M/Y Selene, S/Y Blue Horizon) and has
23 suppliers in its master file: Monaco, French, Italian, Dutch, German and Maltese, with domestic VAT 20%, mixed 5.5%/20%,
reverse charge and exempt regimes. The supplier names of the pilot are kept (Mediterra, SeaGlass, Harbor Parts, Marina Fuel,
Oceanic Safety, Northstar), so results can be compared. All names, addresses, VAT numbers and IBANs are fictional. IBANs have valid
check digits and e-mail domains use the reserved `.example` TLD.

| documents | n | | documents | n |
|---|---|---|---|---|
| supplier invoices (incl. sister company, 2025) | 69 | | payment execution notices (beneficiary IBANs) | 12 |
| purchase orders (with approver and signature) | 27 | | sales invoices (sales cycle, out of scope) | 7 |
| delivery notes / service reports | 20 / 6 | | contracts (berth, IT, waste, office lease) | 4 |
| e-mails, `.eml` (supplier, internal, phishing, noise) | 20 | | bank statements Jul / Aug / Sep / 1–9 Oct | 4 |
| quotes / pro-forma / credit note | 4 / 1 / 1 | | purchase journals Jul–Sep, AP ledger, aged payables, master file | 3 / 1 / 1 / 1 |
| supplier statements of account | 3 | | annual accounts 2025, internal audit report, management reports, policies, insurance, survey, minutes, loan, VAT, payroll, other | 16 |

Languages: 122 English, 78 French (accounting exports and bank documents are in French, as at a Monaco company: the question
says "purchase journal", the document says "Journal des achats").

## Questions

| id | pilot | control | difficulty |
|---|---|---|---|
| acc_q_001 | B1 | duplicate invoices in the September purchase journal (explicit duplicate rule) | easy |
| acc_q_002 | B2 | invoices settled by several debits in September | easy |
| acc_q_003 | B3 | September POs vs the approval matrix of policy PRC-FIN-04 | medium |
| acc_q_004 | B4 | bank debits with no supporting invoice, credit note or PO | medium |
| acc_q_005 | B5 | document types (quote, pro-forma, PO, delivery note, invoice, statement): which one is a liability | easy |
| acc_q_006 | T1 | status of a supplier's documents: BOOK / DUPLICATE / OTHER ENTITY, and journal consistency | medium |
| acc_q_007 | T2 | supplier statement vs ledger reconciliation | medium |
| acc_q_008 | T3 | bank-to-invoice matching for six named suppliers, with totals | hard |
| acc_q_009 | T4 | payment discrepancy after a credit note, carried to the ledger | medium |
| acc_q_010 | T5 | aged payables over 60 days, disputed or not | medium |
| acc_q_011 | T6 | partial payment follow-up: balance, and is any split or schedule documented? | medium |
| acc_q_012 | T7 | payments dated before the invoice or the delivery: JUSTIFIED / NOT JUSTIFIED | hard |
| acc_q_013 | T8 | complete review of the 27 journal lines with 5 checks and an explicit coverage statement | hard |
| acc_q_014 | T9 | invoices booked and paid without a purchase order | medium |
| acc_q_015 | T10 | beneficiary IBAN vs master file, change request and call-back | hard |
| acc_q_016 | T11 | breakdown of all September debits, reconciled to the statement total | hard |
| acc_q_017 | T12 | exception register: 12 closed exception types, every exception carried to the summary | hard |
| acc_q_018 | T13 | cut-off: what to accrue at 30/09 | medium |
| acc_q_019 | T14 | VAT arithmetic and mandatory invoice mentions | medium |
| acc_q_020 | T15 | store isolation probe (unanswerable in this store) | medium |

### Old question → new question

The pilot's own wording was not available when this set was built. For B1–B4, T1, T3, T4, T7, T8, T11, T12 and T15 the intent
comes from the pilot review (observations and scorecard). For B5, T2, T5, T6, T9, T10, T13 and T14 it was **inferred** from the
capabilities the review lists ("document-type distinctions", "Marina Fuel remains unresolved", "Northstar is not labelled fraudulent")
and from standard close controls. Paste the original wording to re-align those eight if needed.

| pilot | what went wrong or was unclear | how the new question fixes it |
|---|---|---|
| B1–B5 | passed, but on a tiny corpus | same controls, now against 200 documents with decoys (identical monthly amounts, sister-company invoice, contractual deposit) |
| T1 | a duplicate was classified "irrelevant" | closed statuses BOOK / DUPLICATE / OTHER ENTITY; the duplicate is a status, not an exclusion |
| T3 | SeaGlass and Harbor Parts not surfaced | scope, amount due, amount paid and statuses defined; totals required |
| T4 | €10 computed but not carried through | the answer must also say whether the €10 is open in the ledger and whether any document waives it |
| T7 | chronology anomaly missed | explicit date comparison (payment vs invoice vs delivery) and an explicit JUSTIFIED rule (a contractual deposit is the decoy) |
| T8 | "review not completed" | a bounded checklist over a known number of lines (27), a forced coverage statement, and a journal line whose PDF is missing |
| T11 | `40,880` not reconcilable | six categories that must add up to the statement total |
| T12 | exceptions lost in the summary | 12 closed exception types with definitions and amounts; 17 expected rows (`metadata.expected_rows`) |
| T15 | inconclusive | becomes a technical probe (below) |

## Format

Each line of `datasets/accountingbench_v1.jsonl` has the FinanceBench top-level keys: `id`, `question`, `question_natural`,
`reference_answer`, `key_facts`, `evidence` (`document_id`, 1-based `page`, verbatim `text`), `metadata`, `calculation`.
`metadata` keeps the FinanceBench fields (`type`, `difficulty`, `requires_calculation`, `requires_multiple_documents`,
`answerable`, `tier`, `style`, `topic`, `failure_modes`) and adds:

| field | content |
|---|---|
| `pilot_id` | B1…B5, T1…T15 |
| `control` / `control_rule` | the accounting control and the rule that decides the answer |
| `output_format` | the table the answer must contain |
| `anomalies_tested` | ids in `anomaly_register.json` |
| `expected_rows` | for T3, T11, T12: the expected table, for row-level scoring |

`question` is the full briefing (median 90 words). `question_natural` is how a busy manager would ask the same thing (median 13
words): run both to measure how much the briefing helps.

## Running it

1. **Ingest** `corpus/documents/` (180 PDFs + 20 `.eml`) into one store, for example `azur-marine-2026-09`. Ingest
   `isolation_probe/probe_doc_001.pdf` into **another** store.
2. **Query** the Azur store with each `question` (and, separately, with `question_natural`). Keep the first answer and the
   sources displayed (document, page).
3. **Score**:
   - `key_facts`: every figure, document number and status the answer must contain (deterministic, accepted variants included).
     This is the primary score.
   - `expected_rows` (T3, T11, T12): precision and recall per row.
   - evidence: the cited documents and pages, which tell a retrieval failure (the evidence was never found) from a reasoning
     failure (it was found but used wrongly).
   - the LLM judge, for completeness and grounding.
   ```bash
   export PIPELINE_URL=… PIPELINE_TOKEN=… ANTHROPIC_API_KEY=…
   python benchmark.py run --dataset accountingbench/datasets/accountingbench_v1.jsonl --config configs/accountingbench.yaml
   ```
4. **T15, store isolation.** In the Azur store, acc_q_020 asks for the total of invoice KAF-2026-7731, which exists only in the
   probe store. The correct answer is an abstention. An answer that contains `48,620.55` or `F-HELI`, or that cites
   `probe_doc_001.pdf`, proves a leak between stores. To complete the check, run the same question in the probe store: it must
   answer there. Both runs together show that retrieval is scoped to the store.

## Validation

- **By construction.** Documents and expected answers come from the same objects (`tools/world.py`). Every expected value is
  computed and asserted against the value the scenario was designed with (for example duplicates = exactly FA-2026-0917, 27
  journal lines, 21 passing lines, statement total debits EUR 242,173.01).
- **Automatic checks** (`tools/validate.py`, the FinanceBench rules): schema and flags; every evidence quote found verbatim on its
  page (for scans, in the OCR reference text); every calculation re-evaluated, with every input found as printed in its evidence;
  every key fact present in the reference answer. `pytest` also checks IBAN validity, weekday bank dates, invoice arithmetic,
  manifest hashes and the absence of giveaway words in the questions.
- **Blind re-answer.** Two independent agents answered the 20 questions from the documents only (rendering the 20 scans to images),
  without the reference answers (`annotation/blind/`). Result: **every key fact of every question found (recall 1.00 on 20/20)**.
  They reported 3 real ambiguities, all fixed in the questions: "same amount" in acc_q_004 (now: the label cites a document of
  the same payee), invoice lines absent from the delivery note in acc_q_013 (now excluded), and the due date of credit notes in
  acc_q_019 (now exempt). They also found 2 missing mentions on the QMR invoice (quantity, net amount) that the reference had
  omitted, which are now corrected. After the move to multi-page PDFs and `.eml` e-mails, a third blind agent re-answered the 6 questions most
  exposed to the new layout (journal, bank statement, supplier statement, e-mails): all key facts found. Every note is adjudicated in `annotation/adjudication.json`; review per question in
  `datasets/accountingbench_v1_review.json` (20/20 verified, `human_reviewed: false`).
- **Not yet done:** review by a practising accountant. Start with acc_q_013, acc_q_017 and acc_q_008 (the longest answers).

## Regenerating

```bash
pip install reportlab pillow          # + poppler-utils (pdftotext, pdftoppm)
python accountingbench/tools/generate_corpus.py   # 180 PDFs + 20 .eml, manifest, OCR reference, isolation probe
python accountingbench/tools/build_dataset.py     # questions, simple export, anomaly register
python accountingbench/tools/validate.py --review
```

To add a scenario, change `world.py` (and `generate_corpus.py` for new documents), then the expected answers in
`build_dataset.py` by stating the new expected values. The assertions stop the build if the world and the questions drift
apart.

## Limits

- Synthetic: one company, one month-end close, documents generated from templates. The variety comes from 4 invoice layouts,
  2 languages, 5 number and date formats and 20 scans, not from real-world mess (handwriting, multi-invoice PDFs, photos).
- Reference answers are long prose tables: score them with key facts and expected rows, not EM/F1.
- Determinism has limits: two reviewers are a small sample. A practising accountant should still read acc_q_013, acc_q_017
  and acc_q_008 first.
