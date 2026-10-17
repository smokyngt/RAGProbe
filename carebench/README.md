# CareBench V1 — dataset card

A clinical-document benchmark for document assistants: **34 questions, 33 of them with 1 to 3 follow-up questions (101 rows)**, over a
**corpus of 114 fictional hospital documents** (106 PDFs totalling 311 pages, 8 `.eml` e-mails; 2 image-only scans; 81 in English,
33 in French) from one hospital, the *Centre Hospitalier Saint-Aubin*, in November 2026. It uses the **same JSON format as
FinanceBench and AccountingBench**, so any runner that reads those can read this one.

Everything is fictional: people, MRNs, institutions, protocols and numbers. The protocols are *hospital documents that define the
rule a question applies*; they are not clinical guidance and nothing here is medical advice.

## What is tested

Each main question applies a hospital rule to patient documents, the way a clinician, pharmacist or quality officer would: read the
right patient's document, find the right rule, apply it, and stop when the documents do not support an answer.

| domain | questions (main) |
|---|---|
| laboratory flags, trends and relative changes | 1, 25 |
| renal dose adjustment (CKD-EPI eGFR → enoxaparin, metformin, gentamicin), warfarin nomogram, paediatric weight dosing, insulin sliding scale | 2, 6, 10, 18, 22, 23, 24, 32 |
| medication safety: reconciliation, allergy vs administered drug, interactions, formulary and approvals | 3, 4, 5, 19, 28, 34 |
| preventive care: adult immunisation schedule | 7 |
| imaging: nodule growth against a guideline threshold | 8 |
| surgery: antibiotic prophylaxis dose by weight and timing; consent vs operation (side, timing) | 9, 12 |
| patient identification: similar names, misfiled report | 11 |
| antimicrobial stewardship: IV days against a policy limit, with a missed-dose decoy; UTI regimens | 13, 29 |
| care transition: results pending at discharge, follow-up bookings against requested timeframes, counts over a 60-row bookings export, booking deadlines | 14, 15, 27, 33 |
| infection control: MRSA isolation by screen result and origin, counts on a ward list, C. difficile precautions | 16, 26, 30 |
| vital signs: NEWS2 score computed from raw observations or from stated values | 17, 31 |
| abstention and false premise: analyte never reported; insulin never prescribed | 20 |
| store-isolation probe: a patient who exists only in another store | 21 |

Hard parts are deliberate and listed per question in `metadata.failure_modes`: a protocol table to read (not just retrieve), a rule
to apply with a computation (eGFR from µmol/L, percentage change, weight-based doses, business days, date windows), decoys
(discontinued drugs, a dose "not given", a patient with a near-identical name, values exactly on an interval limit), documents in
French, two scans and an e-mail as sources, and absence of a document as the answer.

## Follow-up questions

Real use is a conversation, so 33 of the 34 questions are followed by 1 to 3 follow-ups (67 in total). A follow-up row has two
phrasings of the same question:

| field | content |
|---|---|
| `question` | **self-contained**: names the patient, the date and the rule, so it can be asked on its own |
| `question_natural` | **conversational**: how a clinician would really ask it after the previous turn ("And with the creatinine of the 17th?"); needs the earlier turns |

Metadata of a conversation:

| field | content |
|---|---|
| `conversation_id` | id of the main question |
| `turn` | 1 for the main question, 2, 3, 4 for its follow-ups |
| `follow_up_of` | the main question id (null on a main question); `follow_up_ids` lists the follow-ups |
| `follow_up_type` | `drill_down` 15 · `hypothetical_variation` 13 · `next_step` 12 · `scope_change` 12 · `calculation` 5 · `aggregate` 4 · `compare_over_time` 3 · `explain_why` 2 · `false_premise` 1 |
| `depends_on_previous_answer` | false when the follow-up could be answered without the earlier turn (e.g. the false-premise follow-up) |

Follow-ups are not paraphrases: they change the date, the value (*what if the INR had been 4.3?*), the scope (*and the small
nodule on the other side?*), ask for the reason or the next step, or hold a false premise (*why was she started on insulin?*).
A follow-up after an abstention (care_q_020_f2) is answerable, to check that a system recovers.
`datasets/carebench_v1_conversations.jsonl` regroups the rows per conversation (`turns` in order) for multi-turn evaluation.
Each row is scored on its own key facts and evidence; a conversation is successful when all its turns are.

## Contents

```
carebench/
├── corpus/
│   ├── documents/  114 files (.pdf, .eml) with realistic names   ← the ONLY folder to ingest
│   ├── manifest.json         per document: type, language, date, patient MRN, pages, scanned, SHA-256
│   ├── FROZEN.json           manifest hash
│   └── ocr_reference/        reference text of the 2 scans (used only to check evidence quotes; never ingest)
├── isolation_probe/probe_doc_001.pdf   ← ingest in a DIFFERENT store (care_q_021)
├── datasets/
│   ├── carebench_v1.jsonl                 ← the benchmark (full annotation, FinanceBench schema + conversation fields)
│   ├── carebench_v1_simple.jsonl/.csv     ← id / conversation / turn / question(s) / answer / documents / pages
│   ├── carebench_v1_conversations.jsonl   ← one line per conversation
│   └── carebench_v1_review.json           blind re-answer review per row (101/101 verified, not human-reviewed)
├── annotation/               blind answers (5 independent agents, 5 batches) and adjudication of every reported ambiguity or miss
└── tools/
    ├── scenario.py           the fictional hospital: patients, rules, and every computation (single source of truth)
    ├── more_questions.py     questions 22-34 (reuse the corpus: hypothetical cases, counts, lookups)
    ├── pdfkit.py             PDF layout (header band repeated on each page, non-wrapping tables, "Page x of y")
    ├── corpus.py             scenario → corpus (deterministic: same code, same files)
    ├── build_dataset.py      scenario + corpus → questions; expected answers are computed, evidence quotes are located in the pages
    ├── build_review.py       blind answers + adjudication → review file
    └── validate.py           FinanceBench validation rules + conversation rules
```

**Never ingest** `manifest.json`, `ocr_reference/`, `datasets/`, `annotation/` or `tools/`: they contain the answers.

### The corpus

| documents | n | | documents | n |
|---|---|---|---|---|
| hospital protocols, policies and handbooks (3 to 13 pages, incl. a landscape interaction bulletin and a French immunisation schedule and IPC manual) | 27 | | admission notes | 22 |
| laboratory reports (2–3 pages, sex-specific intervals, French labels on French charts) | 21 | | discharge summaries | 17 |
| drug / prescription / administration charts | 6 | | operation notes, anaesthetic record, CT reports | 5 |
| consent form (scan), insulin chart (scan) | 2 | | e-mails (pharmacist, D&T approval, noise) | 8 |
| bookings export, MRSA screening list, vaccination record, anticoagulation record, observation chart, microbiology | 6 | | | |

Of the 114 documents, 47 are cited as evidence; the rest are 14 filler patients with routine notes and results, other protocols
(fire safety, IT downtime, falls, pressure ulcers, MRI safety…), rotas and staff e-mails. Page headers carry the patient banner, as in
a real record.

## Format

Each line of `datasets/carebench_v1.jsonl` has the FinanceBench top-level keys: `id`, `question`, `question_natural`,
`reference_answer`, `key_facts`, `evidence` (`document_id`, 1-based `page`, verbatim `text`), `metadata`, `calculation`.
`metadata` keeps the FinanceBench fields (`type`, `difficulty`, `requires_calculation`, `requires_multiple_documents`,
`answerable`, `tier`, `style`, `topic`, `failure_modes`) and adds:

| field | content |
|---|---|
| `domain` | one of the 13 domains above |
| `clinical_rule` | the rule that decides the answer |
| `output_format` | the shape the answer should have |
| `reasoning_skills` | e.g. `table_lookup`, `formula_evaluation`, `date_arithmetic`, `absence_reasoning`, `premise_checking` |
| `safety_relevant` | true when a wrong answer would mislead a medication or patient-safety decision |
| `conversation_id`, `turn`, `follow_up_of`, `follow_up_type`, `follow_up_ids`, `depends_on_previous_answer` | see above |

IDs: `care_q_001` … `care_q_034`; follow-ups `care_q_001_f1`, `care_q_001_f2`, … Unanswerable rows (care_q_020, care_q_021, care_q_033_f1) have
no evidence and no key facts and are scored on abstention.

## Running it

1. **Ingest** `corpus/documents/` into one store, keeping file names; `isolation_probe/probe_doc_001.pdf` into another.
2. **Single turn:** send each row's `question` (and, separately, `question_natural` for main questions) and keep the answer and sources.
3. **Multi-turn:** for each conversation in `carebench_v1_conversations.jsonl`, send the turns in order and use `question_natural`
   for turns 2 and later. To isolate a turn from earlier mistakes, send the reference answers as the previous assistant turns.
4. **Score:** `key_facts` (deterministic, primary score), `calculation.result` for derived values, the cited documents and pages (retrieval
   vs reasoning failure), and an LLM judge for completeness. With the repository's runner (single turn):
   ```bash
   export PIPELINE_URL=… PIPELINE_TOKEN=… ANTHROPIC_API_KEY=…
   python benchmark.py run --dataset carebench/datasets/carebench_v1.jsonl --config configs/accountingbench.yaml
   ```
   (the runner is not conversation-aware: follow-ups run as independent questions with their self-contained `question`).
5. **care_q_021, store isolation:** the question asks about a patient who exists only in the probe store. An answer that contains `4.6`, `2.8`
   or cites `probe_doc_001.pdf` proves a leak. Run the same question in the probe store: it must answer there (INR 4.6 on 02/11/2026).

## Validation

- **By construction.** Documents and expected answers come from the same objects (`tools/scenario.py`); every expected value is computed
  (eGFR 25 and 47, NEWS2 0/2/7/9/2, warfarin 25.2 mg, paracetamol 217.5 mg…) and asserted when the dataset is built.
- **Automatic checks** (`tools/validate.py`, the FinanceBench rules): schema and flags; every evidence quote found verbatim on its page (for
  scans, in the OCR reference text); every calculation re-evaluated with every input found as printed in its evidence; every key fact present
  in the reference answer; conversation rules (a follow-up points to an existing main question, turns are consecutive, a self-contained and
  a conversational phrasing). `pytest` also checks manifest hashes, the scenario computations and the absence of giveaway words.
- **Blind re-answer.** Five independent agents, in two rounds (questions 1-21, then 22-34), answered all 101 rows from the documents only (scans read as
  images), without the reference answers (`annotation/blind/`). Result: every figure, date and name matched on 79 rows at the first pass; on 22 rows
  a miss or a remark was adjudicated against the documents (`annotation/adjudication.json`): 9 times the question, a key fact or a document was
  fixed (for example a policy table lacked an explicit "moderate CAP" row, the renal protocol's scope excluded acute kidney injury while a patient had
  one, NEWS2's single-parameter rule needed to be stated as taking precedence, "isolated" needed defining, two key facts were not requested by their
  question), 13 times the reference was confirmed. After the fixes, `datasets/carebench_v1_review.json` shows 101/101 verified.
- **Not yet done:** review by a practising clinician or pharmacist (`human_reviewed: false`). Start with care_q_002, care_q_007, care_q_015, care_q_017 and care_q_023.

## Regenerating

```bash
pip install reportlab pillow          # + poppler-utils (pdftotext, pdftoppm, pdfinfo)
python carebench/tools/corpus.py          # 106 PDFs + 8 .eml, manifest, OCR reference, isolation probe
python carebench/tools/build_dataset.py   # questions, simple export, conversations
python carebench/tools/validate.py --review
```

To add a scenario, change `scenario.py` (data and computation), print the new documents in `corpus.py`, then state the expected answer in
`build_dataset.py`; the assertions and the evidence search stop the build if the documents and the answers drift apart.

## Limits

- Synthetic: one hospital, one month, documents generated from templates. Variety comes from 2 languages, 2 scans, sex-specific intervals and
  27 protocols, not from real-world mess (handwriting, photographs, free-text abbreviations, multi-patient PDFs).
- The corpus is small for retrieval (114 documents): a system with a good retriever will find the evidence; the difficulty is in the rules.
- Follow-up scoring here is per turn; there is no metric yet for a conversation as a whole beyond "all turns correct".
- Reference answers are prose: score them with key facts and calculations, not Exact Match / Token F1.
