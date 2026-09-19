# Realism review, draw 1234 (stage 5 gate)

**Verdict: FAIL.** Realism score 15/60 = **0.25** (gate >= 0.85). Counts: real-looking 15, suspicious 25, implausible 20. Several artifacts also exceed 10% of rows. This is my judgement of these 60 rows and of code counts over the file, not a claim that any data looks real.

## Sample

Seed 7 (`np.random.RandomState(7)`), 8 rows per account by `groupby('account')` and `choice`, giving the first 56 ids. 4 hard rows were added after the blind pass from the metadata. Row indices (0-based, data rows):

108 153 325 332 481 551 696 739 750 818 864 887 1023 1157 1173 1180 1307 1322 1334 1493 1496 1515 1605 1924 2202 2207 2209 2233 2321 2421 2423 2484 2533 2546 2708 2713 2771 2990 3038 3049 3218 3246 3292 3299 3319 3341 3389 3478 3493 3526 3572 3590 3655 3699 3771 3820, plus hard rows 561 1214 1723 3129.

Labels for the first 56 were assigned before the metadata was opened. The 4 hard rows were chosen after (random pick from non-easy rows, seed 7).

| idx | vendor | description | date | amount | paid | account | label | reason |
|---|---|---|---|---|---|---|---|---|
| 108 | 123inkt.n Holding | Pakkbon 44810 - betaald per pin | 2025-01-20 | 111.94 | True | Office | suspicious | "Holding" on 123inkt, "Pakkbon" typo, web shop paid "per pin" |
| 153 | KLM.COM | MAANDELIJKS - ROTTERDAM JAN 14 - 2 CHARGES | 2025-01-27 | 137.58 | True | Travel | suspicious | KLM "MAANDELIJKS" (monthly) with a city/date template, mixed NL/EN |
| 325 | Bedrijfsruimte Zwolle B.V. | Monthly payment due on the 1st | 2025-03-01 | 1190.0 | True | Rent | real-looking | Rent on the 1st, round 1190, EN text from a Dutch landlord is plausible |
| 332 | Vepa Bureau | Sale 14/08 till 2 - approved Betaalautomaat Already paid | 2025-03-02 | 8.22 | True | Office | implausible | Sale dated 14/08 on a row dated 2025-03-02 (Sunday); card-terminal text stacked with "Already paid" |
| 481 | ACTION 1234 AMSTERDAM | Receipt - store 1234 - 9 items | 2025-03-28 | 37.12 | True | General/Other | suspicious | Store number 1234 equals the seed; "Receipt - store - N items" frame |
| 551 | LOYENS LOEFF | Compliance advisory - GDPR review | 2025-04-08 | 400.0 | False | Professional | suspicious | Loyens & Loeff GDPR review at exactly 400.00 (real fees are hourly, thousands) |
| 696 | budget energie Inc | Creditnota 2025-4181 v | 2025-05-01 | 98.15 | False | Utilities | suspicious | Dutch utility named "budget energie Inc"; truncated "v" |
| 739 | AH | Pin AH to go Utrecht CS Reeds voldaan | 2025-05-09 | 53.27 | True | General/Other | real-looking | AH to go card payment, escalation to General/Other is what a bookkeeper would do |
| 750 | VODAFONEZIGGO | Contract no. 2201-8877-3345 | 2025-05-10 | 12.5 | True | Utilities | real-looking | Sparse description, 12.50 SIM plan; thin but plausible |
| 818 | simyo | SEPA Incasso algemeen doorlopend Debit - customer ref 5514 - Q3 | 2025-05-20 | 12.5 | True | Utilities | suspicious | "Q3" period tag on a May date; SEPA frame with "customer ref" |
| 864 | WERKGEBOUW BINNENSTAD | Payment | 2025-05-28 | 1120.0 | True | General/Other | real-looking | Generic "Payment" from a landlord-like vendor, 1120; ambiguous but real-feeling |
| 887 | REGUS | Paid by direct debit on 27-06-2025 | 2025-06-01 | 180.0 | True | Rent | real-looking | Regus 180, direct debit note; plausible |
| 1023 | Canon Business Services | Monitor 24 inch, standaard en kabel via iDEAL Reeds voldaan | 2025-06-20 | 18.86 | True | Office | implausible | Canon Business Services selling a monitor for 18.86 |
| 1157 | OV-chipkaart Holding | SEPA Overboeking Amount 10.03 - reload | 2025-07-09 | 10.03 | True | Travel | suspicious | OV-chipkaart "Holding"; reload of 10.03 is not a natural top-up amount |
| 1173 | schoolspullen groothandel BV | Toner huismerk zwart, hoge capaciteit via iDEAL | 2025-07-11 | 9.19 | True | Office | suspicious | Invented vendor; toner for 9.19 too cheap |
| 1180 | Studio Verhuur Tilburg | Statement 07/2025 - account 5514 - SEPA Incasso | 2025-07-13 | 960.0 | True | Rent | suspicious | Rent invoice dated the 13th (Sunday) with a SEPA collection |
| 1307 | Bedrijfsverzamelgebouw De Hoek B.V. | Amount due before 1 Aug 2025 Paid by card | 2025-08-01 | 310.0 | True | Rent | suspicious | "Amount due before 1 Aug" contradicts paid=True by card |
| 1322 | NS Flex | Train ticket Utrecht - Eindhoven, 2n class, e-ticket Kassa 75559 | 2025-08-01 | 9.21 | True | Travel | suspicious | Utrecht-Eindhoven 9.21 too cheap; e-ticket with "Kassa" code |
| 1334 | lebara | Maandbedrag 29,00 - factuur 2025-1521 | 2025-08-03 | 29.0 | True | Utilities | real-looking | Lebara 29,00 with invoice number; plausible |
| 1493 | Ernst & Young Accountants LLP | Betaalautomaat Dossier 76896247 - factuur 8801 | 2025-08-26 | 750.0 | True | Professional | implausible | Big-four audit firm paid at a card terminal (Betaalautomaat) 750.00 |
| 1496 | Van Doorne | Te betalen voor 28-08-2025 EUR 550,00 | 2025-08-27 | 550.0 | False | Professional | real-looking | Law firm payment request with due date, unpaid; plausible |
| 1515 | dropbox Inc | Slack Pro abonnernent, 4 actieve gebruikers | 2025-08-30 | 245.0 | True | Software | implausible | Vendor Dropbox, description "Slack Pro" (vendor/description cross-pairing) |
| 1605 | Ben | SEPA Incasso algemeen doorlopend Invoice 2025-5165 - thank you for p Terminal 2736 | 2025-09-10 | 39.0 | True | Utilities | implausible | Vendor "Ben": SEPA Incasso plus Terminal code plus truncated "thank you for p" |
| 1924 | Amazon.nl | Ordnerset, plastic hoesjes & markers (invoice) | 2025-10-22 | 151.91 | True | Office | real-looking | Amazon.nl office items 151.91; plausible |
| 2202 | Spar B.V. | Verzekering bedrijfsaansprakelijkheid, premie kwartaal | 2025-12-01 | 79.93 | True | General/Other | implausible | Spar B.V. billing business liability insurance |
| 2207 | BUSINESSCENTER LEIDEN Holding | Ref 6484344 | 2025-12-01 | 765.0 | True | Rent | real-looking | Business centre rent 765 with a reference number; plausible |
| 2209 | Flexwerkplek Centrum B.V. | Fixed monthly amount 650.00 | 2025-12-01 | 915.0 | True | Rent | implausible | "Fixed monthly amount 650.00" but amount is 915.00 |
| 2233 | Shopify | BEA NR:4821 ADOBE *CREATIVE CLOUD abonnement iDEAL betaling | 2025-12-02 | 29.0 | True | Software | implausible | Vendor Shopify, description Adobe Creative Cloud |
| 2321 | Sixt | Betaling monthly - PIN 1 x 12,60 EUR | 2025-12-15 | 118.64 | True | Travel | implausible | "PIN 1 x 12,60 EUR" but amount 118.64 |
| 2421 | HP Nederland Holding | MONITORARM ENKEL, KLEM | 2025-12-29 | 66.98 | True | Office | suspicious | HP "Holding" selling a monitor arm in ALL CAPS |
| 2423 | Juridisch Loket | Pinbetaling Invoice INV-2025-43803 #38346 Payable within 30 days | 2025-12-29 | 1900.0 | False | Professional | implausible | Juridisch Loket (free legal aid) invoicing 1900.00 with card-terminal text |
| 2484 | Interparking Nederland | Parking fe - garage P+R, 4 hours Already paid | 2026-01-05 | 2.04 | True | Travel | implausible | Parking 4 hours for 2.04; truncated "fe" |
| 2533 | Tonershop24 | Bestelnummer NL-2026-6832 | 2026-01-13 | 62.19 | True | Office | real-looking | Toner web shop order number 62.19; plausible |
| 2546 | BOL.COM Holding | IDEAL BETALING BOL.COM BESTELLING | 2026-01-15 | 4.97 | True | General/Other | suspicious | "Holding" suffix on bol.com; bank-style iDEAL line, otherwise fine |
| 2708 | Hertz Nederland B.V. | Car Rental - 2 Days, Compact, Insurance Included Paid | 2026-02-04 | 107.43 | True | Travel | real-looking | Hertz 2 days compact 107.43; plausible |
| 2713 | Kantoorhotel Arnhem | Verhuur werkplek, contract 2026-118 | 2026-02-05 | 245.0 | False | Rent | real-looking | Coworking desk, unpaid, contract number; plausible |
| 2771 | NUO | Meter rentla fee (electricity) | 2026-02-15 | 144.13 | True | Utilities | suspicious | Meter rental 144.13 is far too high; typo "rentla" |
| 2990 | xenos B.V. | Factuur F2026/4248 EUR 237,38 | 2026-03-18 | 237.38 | True | General/Other | suspicious | Xenos invoice number F2026/4248 with EUR line; Xenos is normally a receipt |
| 3038 | GITHUB.COM Inc | PEERIODE 18-03-2026 T/M 27-03-2026 Betaald via SEPA Incasso | 2026-03-24 | 69.0 | True | Software | suspicious | GitHub 69.00 for a 10-day period paid by SEPA; "PEERIODE" typo |
| 3049 | Hertz Inc | Airline seat selection + checked baggage 23 kg | 2026-03-26 | 209.62 | True | Travel | implausible | Hertz "Inc" billing airline seat selection |
| 3218 | STIBBE Inc | VOORSCHOT 500,00 - ZAAK 2026/118 (PERIOD) Te betalen voor 06-05-2026 | 2026-04-22 | 1800.0 | False | Professional | implausible | Stibbe "Inc": "VOORSCHOT 500,00" but amount 1800.00 |
| 3246 | Donkey Republic | iDEAL betaling ordernr 12697670 SEPA Overboeking | 2026-04-24 | 39.66 | True | Travel | suspicious | iDEAL and SEPA Overboeking in one line |
| 3292 | vastgoed noord exploitatie b.v. Inc | Transfer - 1St Of Month - Fixed | 2026-05-01 | 180.0 | True | Rent | implausible | "b.v. Inc" is not a legal form |
| 3299 | RSM Netherlands | Boekhoudkotsen en btw-aangifte Q2 2026 Betaald via SEPA Incasso | 2026-05-02 | 995.0 | True | Professional | suspicious | Accountant Q2 fee 995.00 "collected" on a Saturday; typo "Boekhoudkotsen" |
| 3319 | OPENAI *CHATGPT | Diversenn Reeds voldaan | 2026-05-05 | 6.9 | True | General/Other | suspicious | ChatGPT at 6.90 with "Diversenn"; real plan is ~20 USD |
| 3341 | LENOVO | Visitekaartjes 500 stuks | 2026-05-08 | 21.38 | True | Office | implausible | Lenovo selling business cards |
| 3389 | Vandebron Holding | SEPA Incasso algemeen doorlopend Direct debit 11-05-20 | 2026-05-15 | 100.04 | True | Utilities | suspicious | "Holding" on Vandebron; truncated date "11-05-20" |
| 3478 | twilio BV | Projectmanagementtool, 5 gebruik via iDEAL | 2026-05-31 | 198.0 | True | Software | implausible | Twilio selling a project-management tool for 198.00 |
| 3493 | e-Boekhouden.nl Holding | Invoice INV-00456 - VAT reverse charged - customer ID 5514 | 2026-06-02 | 12.0 | True | Software | suspicious | Dutch bookkeeping software with "VAT reverse charged"; "Holding" |
| 3526 | Dropbox International Unlimited Company | Canva Pro abonnement, 1 maand | 2026-06-08 | 12.0 | True | Software | implausible | Vendor Dropbox International, description Canva Pro |
| 3572 | NETLIFY | BTW 21% EUR 597,00 - Totaal EUR 597,00 SEPA Overboeking Betaald via SEPA Incasso | 2026-06-17 | 597.0 | True | Software | implausible | "BTW 21% EUR 597,00 - Totaal EUR 597,00" is arithmetically impossible; two payment methods |
| 3590 | VAN DOORNE | Professional fees per agreement | 2026-06-19 | 800.0 | False | Professional | real-looking | Law firm fee, unpaid, round 800; plausible |
| 3655 | OCTROOICENTRUM NEDERLAND | Betaling Freelance juridisch adviseur, dagdelen Betaald via SEPA Incasso | 2026-07-02 | 568.41 | True | Professional | suspicious | Patent office as "freelance legal adviser" at 568.41 paid by SEPA collection |
| 3699 | backblaze | Betaalautomaat Services | 2026-07-10 | 13.8 | True | General/Other | suspicious | "Services" only, Betaalautomaat for an online backup vendor |
| 3771 | caiway | Mobile roaming charges - EU, July 2026 | 2026-07-20 | 79.0 | True | Utilities | suspicious | Round 79.00 for a roaming charge |
| 3820 | 1Password BV | Betaald per creditcard, factuurdatum 14-07-2026 | 2026-07-28 | 12.0 | True | Software | suspicious | 1Password "BV" with a card-payment note; round 12.00 |
| 561 | Adobe Inc | BEA NR:1928 Parkeren Q-Park Zuidas, 3 uur | 2025-04-09 | 18.37 | True | Travel | implausible | Vendor Adobe Inc, description Q-Park parking (vendor_description_disagree) |
| 1214 | PLAUSIBLE | dienstverlening Betaald via SEPA Incasso | 2025-07-17 | 29.97 | True | General/Other | implausible | Vendor literally "PLAUSIBLE" |
| 1723 | Action | NOTEBOOKS, PENS & PAPER CLIPS Betaalautomaat | 2025-09-26 | 24.58 | True | Office | real-looking | Action stationery, card terminal, 24.58; plausible |
| 3129 | Bol.com | iDEAL betaling bol.com bestelling Term 61937 | 2026-04-08 | 196.87 | True | General/Other | real-looking | bol.com iDEAL order with terminal code; real-looking, genuinely ambiguous |

Only the blind-pass reasons are mine; a few "suspicious" weekend dates matter less than the cross-field contradictions.

## Artifacts across the whole file (n = 4000)

Ranked by damage to realism, then prevalence.

1. **Vendor and description contradict each other (software vendor selling other products, wrong-domain pairs), non-hard rows.** In the sample: 1515 (Dropbox/Slack Pro), 2233 (Shopify/Adobe), 3526 (Dropbox Intl/Canva), 3478 (Twilio/project tool), 3341 (Lenovo/business cards), 1023 (Canon/monitor), 3049 (Hertz/airline seat), 2202 (Spar/insurance). Brand names in the description that differ from the vendor: 51 rows (1.3%) by a narrow keyword list, but 20/60 sample rows were implausible, most for this or the next artifact, so the true prevalence is far higher (sample-based estimate: ~15-30%). Only 84 rows (2.1%) are flagged `vendor_description_disagree`; the rest are not labelled as hard, so the labels claim "easy" for rows a bookkeeper would dispute. Examples: 561, 1515, 2233, 3526, 3478.
2. **Amount contradicts the amount quoted in the description.** Regex found 32 rows (0.8%) with an explicit number that differs (e.g. 353 "PIN 1 x 12,60 EUR" vs 334.73; 598 "1 x 19.99" vs 199.00; 892 "Fixed Monthly Amount 650.00" vs 305.00; 3218 "VOORSCHOT 500,00" vs 1800). The description fragments are reused across unrelated vendors and amounts, so they are template text. 3572 has "BTW 21% EUR 597,00 - Totaal EUR 597,00" which is impossible. Small share by regex, but each one is an instant tell.
3. **Fake corporate suffixes.** "Holding", "Inc", "LLC" on vendors: 542 rows (13.6%), including Dutch consumer names ("OV-chipkaart Holding", "budget energie Inc", "HP Nederland Holding", "Stibbe Inc"), and "b.v. Inc" (4 rows: 32, 1708, 3292, 3353). Real Dutch entities use B.V./N.V. This is a noise op (`vendor_legal_suffix_variation`) that is not Dutch-aware. **>10%: gate breach on its own.**
4. **Payment-method text stacked and inconsistent with paid and document type.** 404 rows (10.1%) combine a payment-method phrase (SEPA Incasso, iDEAL, Betaalautomaat, Pin, creditcard) with a second settled/terminal phrase (Reeds voldaan, Already paid, Paid, Terminal, Kassa). Card-terminal text appears on 11.9% of Professional Services rows (e.g. 1493 Big-four audit paid at a terminal, 2423 Juridisch Loket). "Amount due before 1 Aug" with paid=True (1307). Bank-prefix and suffix noise is applied independently of vendor type. **>10% borderline (10.1%) and worse within professional services.**
5. **Round amounts, and salary-like tidy series.** 30.8% of amounts are integers (Rent 86%, Professional 68%, Software 55%, Utilities 33%). Rent is plausible; software at 55% is mostly fixed plan prices, but 1Password, Twilio, GitHub, Canva prices are not all round and multiple-vendor same amounts repeat (e.g. 12.00, 29.00, 79.00, 198.00). Nearly every rent vendor has exactly one amount (mean 1.02 distinct amounts per rent vendor, 167 vendors), so recurrence never varies, and a whole rent vendor appears as roughly a single row: the "series" is not really a series. **Software+Rent+Professional integer share exceeds 10% of rows.**
6. **Dates ignore business days.** Weekend share 16.4% (real business documents would be nearer 2-6%, except card receipts). Rent invoices dated on Sunday/Saturday (1180). 9.3% of all rows fall on the 1st, and rows are globally sorted by date. Weekend pattern is flat across categories: professional-services invoices (551, 3299) land on weekends as often as receipts.
7. **Damaged strings that look like injected noise, not OCR.** Words with a single deleted/doubled letter or truncated mid-word: "PEERIODE", "rentla", "Boekhoudkotsen", "abonnernent", "Diversenn", "Parking fe", "thank you for p", "11-05-20". 0.9% truncated endings and 0.2% obvious typos by regex; sample rate is higher (about 9 of 60 rows have visible damage). Real OCR damage would hit digits/lookalikes (l/1, O/0) far more than these tidy letter swaps; 61 shows "Beta1ing", which is more convincing.
8. **Leaked placeholders/tokens.** A vendor literally named "PLAUSIBLE" (5 rows: 1214, 1511, 2747, 3661, 3939); the literal string "(PERIOD)" in 25 rows (e.g. 72, 231, 388, 393, 574, 3218), plus "(period)"/"(Periode)" tags: 104 rows (2.6%) carry some period tag. The tag is appended at the end of text, in three casings, sometimes mid-string ("PERIOD - BEA NR"). It reads as an artifact. Also: seed-like literals `1234` in vendors/descriptions (18 rows, 0.4%; e.g. "ACTION 1234 AMSTERDAM", 481) and "5514" in 30 descriptions (0.8%).
9. **Description frames repeated.** Top 50 masked templates cover 8.0% of rows; single frames such as "Nota #  aug#" (17), "Factuur #-#" (16), "Periode #-#-# t/m #-#-#" (13), "Payment" (10), "Rekening #/# kostenplaats #" (10). Prefix "SEPA Incasso" opens 195 rows (4.9%) and "SEPA Overboeking" 118 (3.0%). Below 10% but visible.
10. **Vendor duplication by casing/suffix.** 1956 distinct vendor strings map to 1414 lowercase strings; "Microsoft 365" vs "MICROSOFT 365" vs "microsoft 365" are 53 rows. Real exports are consistent per source. Also "Microsoft 365", "Microsoft Azure", "Google", "Adobe" are 3-5 fixed prices.

Not found: exact duplicates on vendor+description (0), software vendors under travel (only 7 of 305 software-name rows sit outside the Software account and most of those are the disagree cases).

## Hard and ambiguous rows (metadata opened after the blind pass)

- **Escalation** applies to 260 rows (6.5%), all filed as General/Other; `true_account` is retained and never differs from `account` for non-escalated rows.
- **Genuinely ambiguous, a bookkeeper would escalate:** Google Ads top-up vs Workspace at ~45 EUR (1140, 386), generic descriptions like "dienstverlening" with an invented vendor (1214), Action "Kassabon" with no item detail (1294, 903), Albert Heijn or Tango coffee/snack (739, 1215, 1280), bol.com marketplace order (3129, 2546). These are real ambiguity.
- **Mislabeled rather than ambiguous:** `generic_description` rows have vendors like "Freedom Internet B.V." (3298), "BOLDDESK SOFTWARE B.V." (1656), "Bureau Strategie & Groei" (845) where the vendor alone resolves the account; a bookkeeper would book them rather than escalate (100% escalate flag on 67 rows). Also hard rows where escalation is 0% for `vendor_description_disagree` (0/84): these are the rows a bookkeeper would dispute or escalate the most (Vattenfall "Parkeerkosten en tanken", GitHub "Elektriciteit en gas", Loyens & Loeff "Huurtermijn", Adobe Inc / Q-Park), yet they are labelled with the description's account and not escalated. Conversely `fuel_station_shop` at 138.60 for a coffee (1280) is not credible in amount.
- `amazon_nl` 36% escalate, `bol_marketplace` 27%: partial, plausible given amounts.

## Unverified vendors

544 rows (13.6%) across 118 distinct canonical vendors. Top 15 by frequency:

| vendor_canonical | rows | my view |
|---|---|---|
| Staples | 40 | real (US chain; in the NL it is a brand of Office Centre / exists as staples.nl historically); flagged unverified but real-ish |
| 9292 | 18 | real (Dutch public transport journey planner), though a transaction from it is odd |
| Taxi Utrecht Centrale | 15 | generic, plausible, invented as a specific company |
| Delta Energie | 13 | real (Delta Energie / Delta Fiber exists) |
| Rotterdamse Taxi Coop | 12 | invented (plausible pattern) |
| Paperman | 12 | invented |
| Boekhoudservice Zuid | 12 | invented |
| Cartridge World | 11 | real (international franchise, present in NL) |
| Printerinkt Direct B.V. | 11 | invented (plausible) |
| Tonershop24 | 11 | plausibly real webshop; unsure |
| Notariskantoor Centrum | 11 | invented generic |
| Administratiekantoor De Balans | 11 | invented generic |
| Accountantskantoor Noord B.V. | 10 | invented generic |
| Vepa Bureau | 9 | real (Vepa is a Dutch office furniture brand) |
| Notariaat Oost | 9 | invented generic |

Counting: real 5 (Delta Energie, Cartridge World, Vepa Bureau, 9292, Staples), plausible-real 1 (Tonershop24), invented 9. The invented ones are all "location/function + type" names, which makes them tidy; real firms include personal names, abbreviations and odd spellings. Note "Staples" is also under "verified" spellings elsewhere (12 rows), which is inconsistent.

## Concrete fixes

**Generator (blocking)**
1. Restrict the `vendor_legal_suffix_variation` op to Dutch legal forms (B.V., N.V., VOF) and never append to a string that already ends with a legal form or to brands that are not companies (OV-chipkaart, NS, Bol.com). Drop Inc/Holding/LLC except for US-based vendors. Target < 3% of rows.
2. Make payment-method text a single field chosen by document type: card terminal/Pin/Kassa only for receipts, SEPA Incasso/Overboeking only for invoices/utilities. Ban stacking (Betaald via + Reeds voldaan). Never emit "Amount due before" when paid=True.
3. Compute any amount that appears in the description from the sampled amount (single source of truth) or omit it. Remove reused fragments such as "PIN 1 x 12,60 EUR", "1 x 19.99", "Fixed monthly amount 650.00".
4. Replace weekend-agnostic dates with business-day sampling for invoices (roughly 3-5% weekends) and allow weekends only for receipts/card lines. Rent on the 1st of the month is fine, but should roll to the next working day for SEPA lines.
5. Replace period-tag repair by appending real, varied context (month name in the vendor language, invoice number, week number), lowercase, in the position other frames use. Remove the literal "(PERIOD)".
6. Fix the "PLAUSIBLE" placeholder and the seed/store literal `1234`/`5514` (use varied store numbers, customer refs).

**Corpus/spec (blocking)**
7. Vendor and description must come from the same archetype for `easy` rows. Audit that Dropbox/Shopify/Twilio/Lenovo/Canon/Spar/Juridisch Loket descriptions match what those vendors sell. Keep cross-pairings only under `vendor_description_disagree` and label them escalate (or dispute), not with the description's account.
8. Tie amount ranges to vendor reality: Loyens & Loeff, Stibbe, EY fees in the thousands and hourly; Juridisch Loket is not an invoicing firm; NS/OV tickets and parking not below plausible minima; ChatGPT ~20 USD; utility meter rental 3-10 EUR. Add price points per vendor (`typical_amount` set) rather than one pooled log-normal.
9. Recurring series: give rent/subscription vendors several rows with the same amount at monthly cadence and occasional price changes, not one row per vendor.
10. Corpus: add non-generic invented vendors (personal names, abbreviations, "X & Y", numbers) and reduce "Noord/Zuid/Oost/Centrum" patterns. Normalise brand casing per vendor.

**Labels (non-blocking but needed)**
11. `generic_description` rows whose vendor is unambiguous should not be escalate=true; re-tag `vendor_description_disagree` rows as escalate or dispute.
12. Noise: prefer OCR-style digit/letter lookalikes over random letter deletion; do not truncate mid-word except at fixed OCR line width.

## Gate

FAIL. Blocking: fixes 1, 2, 3, 7, 8 (they drive the 0.25 score and the >10% artifacts: suffixes 13.6%, stacked payment text 10.1%, round amounts 30.8%, weekends 16.4%). Re-run the generator with the same seed after these; then re-review with a fresh sample.
