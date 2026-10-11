# Prompt — Création d'un benchmark comptable déterministe pour Prosperify

> À coller dans une nouvelle conversation Claude, avec en pièce jointe :
> (1) les 20 questions du pilote de Giorgia (B1–B5, T1–T15) et leurs réponses attendues,
> (2) les documents du pilote (factures, emails, relevés).

---

## Rôle

Tu es un expert-comptable senior (cabinet, 15 ans d'expérience en révision et en clôture mensuelle)
doublé d'un concepteur de benchmarks pour systèmes RAG. Tu construis un jeu de test qui évalue
Prosperify, un assistant documentaire, sur des tâches qu'un comptable réalise réellement.

## Contexte

Un premier pilote (Giorgia) a donné : B1–B5 PASS ; T1–T15 : 7 PASS, 6 PARTIAL, 1 FAIL, 1 INCONCLUSIVE.
Ses limites ne viennent pas seulement du modèle, mais aussi du test lui-même :

1. **Corpus trop petit** (une vingtaine de documents d'une page) : la recherche documentaire,
   qui est la valeur ajoutée de Prosperify, n'est presque pas sollicitée.
2. **Documents irréalistes** : factures sans numéro de TVA, sans adresse, sans IBAN, sans bon de
   commande, sans quantités ni prix unitaires ; une facture (INV-2026-552) sans TVA ni échéance ;
   une mention « scanned copy » sur un PDF natif ; des caractères corrompus dans une référence
   bancaire (« ■■■FUEL 1182■■■ ») ; des titres de fichiers qui révèlent l'anomalie
   (« 12 Email MarinaFuel **Discrepancy** », « Sept_**Final** »).
3. **Questions trop ouvertes** (« fais une revue complète », « est-ce que le solde est attendu plus
   tard ou réparti entre deux navires ? ») : aucune réponse unique n'est vérifiable, et un comptable
   ne formulerait pas sa demande ainsi.
4. **Aucun format de sortie imposé** : les totaux (ex. 40 880 €) ne sont pas recalculables et
   les anomalies se perdent entre les tâches individuelles et la synthèse.

Principe directeur : **Prosperify doit être briefé comme un stagiaire compétent.** Plus la question
précise le périmètre, les documents, la règle de contrôle et le format attendu, plus la réponse est
évaluable et utile.

## Ta mission

### Partie A — Spécifier le corpus (à générer ou à collecter)

Décris un corpus fictif mais réaliste pour **une société** (reprendre Azur Marine Services S.A.M.,
Monaco, exercice 2026, clôture de septembre) contenant **au moins 200 documents**, dont :

| Type | Volume indicatif | Exigences de réalisme |
|---|---|---|
| Factures fournisseurs | 80–100 | mentions obligatoires (art. 226 dir. 2006/112/CE) : n° TVA intracom, adresse, n° séquentiel, date, quantités, PU HT, taux et montant TVA, échéance, IBAN, réf. bon de commande |
| Avoirs | 5–10 | référence à la facture d'origine |
| Bons de commande | 60–80 | n° BC, approbateur, montant engagé |
| Bons de livraison / réception | 60–80 | date, quantités reçues, signature |
| Relevés bancaires | 3 mois (juillet–septembre) | format réel de relevé (date opération, date de valeur, libellé tronqué bancaire, solde) ou export CAMT.053/CSV |
| Grand livre fournisseurs / balance âgée | 1–2 | export du logiciel comptable, comptes 401xxx |
| Emails internes / fournisseurs | 20–30 | relances, litiges, validations |
| Fiche fournisseurs (master data) | 1 | IBAN de référence de chaque fournisseur |
| **Bruit** | ≥ 30 % du corpus | documents d'autres mois, autres sociétés du groupe, contrats, devis, factures clients |

Contraintes :
- **Noms de fichiers neutres** (`SUP_INV_0418.pdf`, `BANK_2026-09.pdf`) : aucun mot qui trahit une anomalie.
- 20 à 30 % de documents **scannés réellement** (image, légère rotation, tampon) pour tester l'OCR.
- Pas de caractères corrompus involontaires ; les anomalies doivent être **intentionnelles et documentées**.
- Chaque anomalie plantée est inscrite dans un **registre des anomalies** (fichier séparé, jamais ingéré).

Anomalies à planter (chacune avec 1 à 2 occurrences, plus des « faux positifs » plausibles mais justifiés) :
doublon de facture (même n°, ou même montant/date avec n° différent), paiement partiel, écart de
règlement après avoir (cas SeaGlass, 10 €), paiement antérieur à la facture et au BL (cas Harbor Parts),
facture sans BC, BC non approuvé, écart de quantité BL/facture (three-way match), IBAN de paiement
différent de la fiche fournisseur, erreur de taux ou de calcul de TVA, facture datée de septembre reçue
en octobre (cut-off / charge à payer), virement sans facture, facture non conforme (mentions manquantes).

### Partie B — Réécrire les 20 questions, une pour une

**Ne crée aucune question supplémentaire et n'en supprime aucune.** Conserve l'identifiant (B1…B5,
T1…T15) et l'intention de contrôle de chaque question d'origine, mais réécris-la pour qu'elle :

1. soit formulée **comme un chef de mission la donnerait à un collaborateur** (vocabulaire métier :
   lettrage, rapprochement bancaire, three-way match, cut-off, balance âgée, FNP / charge à payer) ;
2. précise **la société, la période, le ou les fournisseurs, les comptes ou documents concernés** ;
3. énonce **la règle de contrôle** (ex. « un paiement est rapproché si le montant est identique à
   l'euro près et si le libellé contient le n° de facture ; sinon, statut "non rapproché" ») ;
4. impose **un format de sortie fermé** : tableau avec colonnes nommées, statuts dans une liste fermée
   (`RAPPROCHÉ | PARTIEL | ÉCART | NON RAPPROCHÉ | NON DÉTERMINABLE`), montants à 2 décimales ;
5. exige **les sources** : nom du document + page pour chaque ligne ;
6. prévoit **la sortie « non déterminable »** et la liste des documents consultés lorsque le dossier
   ne permet pas de conclure (pas d'hypothèse inventée) ;
7. pour les questions de synthèse (T8, T11, T12) : impose **une liste exhaustive des documents
   couverts / non couverts**, un total recalculable (détail des lignes qui le composent) et la reprise
   explicite de toutes les anomalies (SeaGlass et Harbor Parts doivent y figurer) ;
8. pour T15 (isolation des stores) : remplace la question générative par **un test technique** —
   ingérer un document piège dans un autre store et vérifier qu'il n'apparaît jamais dans les sources.

### Exemples de réécriture attendue

**Avant (Giorgia)** : « Can you confirm whether the remaining EUR 13,200.00 is expected later or
whether the invoice should be split between two vessels? »

**Après** : « Pour Azur Marine Services, lettre la facture Marina Fuel INV-2026-1182 avec le relevé
bancaire de septembre 2026. Donne dans un tableau : montant facturé TTC, montant(s) payé(s) avec date
de valeur et libellé bancaire, solde restant dû. Indique ensuite si un document du dossier (bon de
commande, bon de livraison, email) justifie une répartition entre deux navires : réponds `OUI` avec la
source, ou `NON DÉTERMINABLE` avec la liste des documents consultés. »
→ Réponse attendue : 26 400,00 / 13 200,00 / 13 200,00 / `NON DÉTERMINABLE` (sauf document prévu au corpus).

**Avant** : « Reconcile the September payments. »

**Après** : « Pour chaque paiement fournisseur du relevé de septembre 2026, compare la date de valeur
du paiement à la date de la facture et à la date du bon de livraison correspondants. Liste uniquement
les paiements antérieurs à la facture OU au bon de livraison, avec les trois dates, l'écart en jours et
les sources. Ne qualifie pas l'opération (erreur, acompte, fraude) : signale-la seulement. »
→ Réponse attendue : Harbor Parts — paiement 05/09, BL 11/09, facture 12/09 (+ éventuels acomptes justifiés par contrat, à exclure).

## Livrables attendus (dans cet ordre)

1. **Spécification du corpus** (Partie A) : liste des documents à générer avec leur contenu clé.
2. **Registre des anomalies** : id, type, documents concernés, montants, dates, question(s) qui la testent.
3. **Les 20 questions réécrites**, au format JSON Lines :

```json
{"id": "T3", "original_question": "...", "rewritten_question": "...",
 "control_intent": "rapprochement bancaire fournisseurs",
 "scope": {"entity": "Azur Marine Services S.A.M.", "period": "2026-09", "suppliers": ["..."]},
 "control_rule": "...", "output_format": "tableau: fournisseur | n° facture | montant facture | montant payé | écart | statut | source",
 "expected_answer": {"rows": [...], "totals": {...}},
 "required_sources": [{"doc": "...", "page": 1}],
 "anomalies_tested": ["A07", "A12"],
 "scoring": {"type": "exact_rows", "amount_tolerance": 0.00, "partial_credit": "par ligne"}}
```

4. **Grille de notation automatique** : pour chaque question, ce qui est vérifié par script
   (montants, statuts, dates, présence des anomalies) et ce qui nécessite un relecteur humain.
5. **Tableau de correspondance** ancienne question → nouvelle question → raison du changement.

## Règles strictes

- Exactement 20 questions, mêmes identifiants, même intention de contrôle que l'original.
- Chaque réponse attendue est **unique et vérifiable** à partir du corpus ; si elle dépend d'un
  jugement, la question doit fixer la règle qui tranche.
- Aucune question ne contient la réponse ni ne nomme l'anomalie recherchée (« trouve le doublon »
  est interdit ; « liste les factures dont le n° ou le couple montant/date apparaît plus d'une fois »
  est autorisé).
- Les calculs attendus sont détaillés et justes au centime ; vérifie-les deux fois.
- Langue des questions : anglais (destinataire du pilote : Giorgia) ; commentaires de conception en français.
