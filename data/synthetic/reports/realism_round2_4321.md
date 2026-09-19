# Realism review round 2, draw 4321 (stage 5 gate)

**Verdict: FAIL.** Realism score 48/60 = **0.80** (gate >= 0.85). Labels: real-looking 48, suspicious 11, implausible 1. One artifact family (frozen per-vendor price menus) touches about 19.6% of rows, over the 10% limit. This is my judgement of these 60 rows plus code counts over the 4000-row file, not a claim that the data looks real.

Process note: while checking the file layout I ran `head -3` on the metadata file, which exposed the first two metadata rows (ids 0 and 1, neither in the sample) before the blind pass. Nothing else in metadata, spec, corpus, generator or reports was read before judging.

## Sample (seed 11, `random.seed(11)`)

8 rows per account from `groupby('account')` (row order in the transactions file), 56 rows, then 4 hard rows drawn from non-easy rows with the same seed after the blind pass. 0-based data row indices:
2141 3951 2583 3914 3609 2178 2394 3908 | 1182 1149 3577 3328 1159 534 3163 2083 | 893 565 3212 3995 3656 206 3445 2418 | 1912 2807 3046 2603 2806 1016 2605 6 | 569 539 330 1554 1948 281 3578 2551 | 2051 2858 3983 823 2416 975 3115 1280 | 2104 50 2830 492 1935 2779 1269 1761 | hard: 2009 3752 2531 3707.
Stratification was by account only for the blind pass (difficulty lives in metadata). Afterwards the sample turned out to be 48 easy, 6 ambiguous, 2 hard among the first 56; hard-case rows are under-represented, so the score is likely flattering.

Suspicious / implausible rows (all others in the sample were real-looking):

| idx | vendor | description | label | reason |
|---|---|---|---|---|
| 2394 | Netlify | Ride 96749225 - Total 2.76 incl. 21% VAT | implausible | hosting vendor with a taxi-ride description |
| 2141 | DB Fernverkehr AG | Invoice 2025-0912 - December 2025 - Payable within 14 days, 20.00 | suspicious | rail vendor with no journey, round 20.00, filed General |
| 2178 | Translink Systems B.V. | Factuur 202500340 Netbeheer Decembe | suspicious | network management under General/Other; truncated |
| 3908 | Bloemenwinkel Centrum | Pinbetaling Payment of invoice 202600857 | suspicious | florist with invoice number, NL+EN stacked |
| 3995 | RSM Netherlands | 4-clause description, Subtotal 235.00 + 21% = 284.35 | suspicious | over-long, every clause present at once |
| 1016 | KANTOORVERHUUR UTRECHT B.V. | svc charge July 2025 - Payment reference ... - SEPA Incasso | suspicious | EN abbreviation plus three stacked fragments |
| 2605 | Spaces BV | Order 51925856 - February 2026 - SEPA Incasso | suspicious | coworking rent described as an "Order" |
| 2858 | NS | OVERBOEKING INVOICE INV001468 - MARCH 2026 | suspicious | NS does not issue invoice numbers like this for a fare |
| 3983 | TANKSTATION DE KRUISEWEG | BEA NR:8219 Order 69594380 - August 2026 | suspicious | fuel stop with an "Order" number and month |
| 975 | Bolt | Betaling juni 2025 - Uw kenmerk 62025305, unpaid | suspicious | ride-hail is card-charged, never an unpaid invoice with reference |
| 2830 | Enexis BV | Payment of invoice 0000659 | suspicious | grid operator, not the supplier, and EN text on an NL utility |
| 2009 | AH | BETALING FACTUUR 0000941 BEA NR:8878 7.91 | suspicious | invoice wording on a POS receipt |

## Artifact hunt (n = 4000, metadata opened after the blind pass)

1. **Frozen price menus for recurring vendors (about 19.6% of rows: vendors with >=10 rows and <=3 distinct amounts).** Microsoft 365: 10.93 x60, 21.86 x40 of 107. Adobe 12.00 x54 of 55. Dropbox 9.99 x38 of 38. KvK 85.15 x38 of 38. Zoom 10.00/45.00 x44 of 46. Slack 10.00/20.00 x50 of 52. Google Workspace 6.90/13.80/207.00 of 80. The same value for 20 months with no price change, no FX and no VAT drift. USD-billed vendors (Slack, Zoom, Adobe, Dropbox, GitHub, Figma) are 73% whole-euro amounts, which real EUR debits of USD prices would not be. Top single amounts: 10.00 x98, 29.04 x71, 15.13 x69, 35.09 x64. Examples: 3578, 1948, 2551, 281. Cross-vendor: VodafoneZiggo 35.09 (rows 50, 492) equals Hollandsnieuwe 35.09 (row 1269), so distinct vendors share one price.
2. **Reference-number filler (33% of rows contain an 8-digit reference, 47% carry Invoice/Order/Bestelling/Betaling words).** "Order NNNNNNNN" is bolted onto rent, fuel, transit and utility lines where a real bank line has none (2605, 3983, 2858). 195 rows have "BEA NR:####" (4.9%), all on non-invoice docs, correctly; 9 also have "Term". Frames such as "Payment of invoice #" (12), "Bestelling #" (14) recur.
3. **SEPA Incasso filler.** 559 rows (14.0%) say SEPA Incasso; the literal "SEPA Incasso algemeen doorlopend" (or its truncation "doorl") is 15 rows exact and far more as a suffix. Fine for direct debits, but it appears on rent, software and utilities alike as a generic tail, so it discriminates nothing.
4. **Vendor/description mismatch on rows not labelled as hard.** In the sample: 3908, 2858, 3983, 975, 2830, 2009. Vendor-description pairs are mostly coherent now, but the "invoice/order/reference" scaffolding is attached to vendors that would not produce it. Labelled `vendor_description_disagree`: 112 rows (2.8%), real cross-pairs (Netlify/Ride, Etos/Slack, Bruna 8712.00 "Order").
5. **Stacked payment/settled text.** 79 rows (2.0%) combine a payment method with Paid/Terminal/Kassa. 0 professional-services rows carry card-terminal text. Zero paid=True rows carry due-date text.
6. **Damaged strings.** noise ops: truncated 304 rows (7.6%), typo 216 (5.4%), ocr_confusion 192 (4.8%). "Decembe", "Netbeheer Decembe", "Orderr", "Payrnent", "0rder" are convincing; "Betselling", "administratue" (letter swaps) still read as injected. 41% of rows have no noise at all.
7. **Amounts and dates.** Integer share 16.9% (Software 41%, Travel 17%, Professional 14%, Rent 11%, Office 1%, Utilities 1%). Rent at only 11% whole euros is low for real rent (usually round), and Professional at 14% is low for fixed fees. Weekend dates 3.7% overall; bank and invoice rows 0%, receipts about 16% (real retail ~28%). 7.6% of rows fall on the 1st. Month-end 3.2%. No exact duplicates. VAT arithmetic is 100% consistent (gross = net x (1+rate) on every row, and quoted totals match the amount in 105/105 cases), which is suspiciously perfect for a 4000-row synthetic set with OCR noise.
8. **Suffixes.** Holding/Inc/LLC on 69 rows (1.7%), all US SaaS (Figma Inc, Notion Labs Inc, The Rocket Science Group LLC) which is correct; only 3 "Holding". "B.V." on Dutch entities is applied plausibly. No "b.v. Inc". Vendor-account dispute pairs: Google (26 General / 14 Software), Bol.com, HEMA, Amazon.nl, Coolblue split General vs Office by design; Translink "Netbeheer" and DB under General are the only pairs I would dispute.
9. **Separability.** "Ride", "Toner" keywords map to a single account 94-95%; "SEPA Incasso" is spread over Software, Utilities, Rent. Vendor alone predicts account for most rows (crosstab of vendor_canonical vs true_account is nearly diagonal), so the task is closer to vendor lookup than round 1 was.

## Hard and ambiguous rows

Escalate = 6.2% (247 ambiguous, 225 hard). All ambiguous rows are escalate=true, all easy and hard rows are false. `vendor_description_disagree` is now escalated (112/112). `account` equals `true_account` on every non-disagree row; on the 112 disagree rows the file is filed General while `true_account` is a different account for 83%, so a training signal "General/Other" is defensible.
- Genuinely ambiguous: Google Ads vs Workspace (2531 hard, "OVERBOEKING GOOGLE WORKSPACE 9.39", real), AH/HEMA Kassabon with no items (3707 4.30), bol.com marketplace iDEAL (3752), Amazon.nl "iDEAL Betaling" 98.87 (223), BP "0rder" (30).
- Mislabeled / weak: `generic_description` rows still escalate 24 of 83 while KvK "INV. 0000270" (93), NS Flex "iDEAL Betaling factuur" (313), TotalEnergies "Betaling factuur" (141) are booked at once by vendor, not escalated (good), but some generic rows with known vendors (BP 30, AH 2009) escalate although the vendor resolves them. `vendor_description_disagree` true accounts are arbitrary: Bruna "Order 28227033" 8712.00 with true=Professional Services (146) and Etos "Betaling 5" with true=Software (3629) have nothing in the row that supports the true account, so "true" is unknowable, not ambiguous.

## Unverified vendors (top 15 by frequency, 13.85% of rows)

Real Dutch businesses: Staples (47, real brand, NL presence via Staples Solutions/staples.nl), 9292 (16, real journey planner), Cartridge World (13, real franchise), Delta Energie (10, real), YOND (9, real Dutch flex-workspace brand as far as I know), Tonershop24 (10, plausible-real webshop name, unsure).
Invented (generic location-plus-function pattern): Paperman (22, I do not recognise it), Notariaat Oost (18), Printerinkt Direct B.V. (12), Notariskantoor Centrum (12), Taxi Utrecht Centrale (11), Accountantskantoor Noord B.V. (9), Cloudnine Apps B.V. (9), Tankstation De Kruiseweg (9), Boekhouder aan Huis (9).
Count: 5 real, 1 unsure, 9 invented. The invented ones are exactly the tidy "Noord/Oost/Centrum + trade" names, each with nearly one price (YOND, Cloudnine Apps, Boekhouder aan Huis have a single amount for all rows).

## Round 1 (seed 1234, 0.25 FAIL) versus round 2

| Round-1 artifact | Round 1 | Round 2 status |
|---|---|---|
| 1 Vendor/description contradiction on easy rows | ~15-30% est. | Mostly gone (1/60 implausible, 2.8% labelled disagree and now escalated); residual scaffolding mismatch (about 8% of sample rows) |
| 2 Amount contradicts quoted amount | 0.8% | Gone (0 of 105 quoted totals wrong) |
| 3 Fake Holding/Inc/LLC suffixes | 13.6% | Gone as artifact (1.7%, US SaaS only; 3 "Holding") |
| 4 Stacked payment text | 10.1% | Reduced to 2.0%; no terminal text on Professional; no due-date text on paid rows |
| 5 Round amounts, single-amount rent series | 30.8% | Reduced to 16.9%, now arguably too low for Rent/Professional; rent vendors recur monthly (Spaces 363.00) but with zero price change |
| 6 Weekend dates 16.4% | 16.4% | Reduced to 3.7% (0% bank/invoice); 1st-of-month share 7.6% (was 9.3%) |
| 7 Injected letter-swap typos | ~9/60 sample | Reduced; OCR confusions (0/O, rn/m) now present and convincing; some letter swaps remain |
| 8 Leaked tokens (PLAUSIBLE, (PERIOD), 1234, 5514) | 2.6%+ | Gone: 0 "(PERIOD)", 0 "1234", 0 "5514". "Plausible Analytics" (2 rows) is a real product |
| 9 Repeated description frames | top 50 = 8% | Still present, similar order (top frames 14/12/9 rows) |
| 10 Vendor casing duplicates | 1956 strings/1414 lower | Still present by design (1149 vendor strings for 374 canonical), plausible as bank-vs-invoice variation |

## New artifacts introduced by the revision

- **Over-regular archetype-linked descriptions.** Each archetype now has a small set of desc families (median 1 family per archetype), so every Spaces/Kantoorverhuur/coworking row reads "SEPA Incasso ... Order NNN - Month YYYY". Categories are separable by vendor plus family; the description adds little beyond the vendor.
- **Unnaturally consistent price menus.** Item 1 above: 19.6% of rows, identical amounts for 20 months, even across different vendors (35.09). Introduced by the fix for "amounts should vary by vendor".
- **Perfect internal arithmetic.** net x VAT = gross on 100% of rows, quoted totals never wrong, no rounding or line-item mismatches.
- **Over-tidy calendar.** Bank/invoice rows have zero weekend dates; recurring lines land on business days with no bank-holiday shifts or late collections.
- **Reference scaffolding.** "Order/Invoice/Kenmerk NNNNNNNN" appended to low-information lines that would have none.

## Concrete fixes

Blocking (gate):
1. Add price-change events and jitter to recurring SaaS/rent amounts (annual increases, USD-to-EUR FX drift, seat count changes); stop cross-vendor sharing of 35.09; drop whole-euro prices for USD-billed vendors. Target under 10% of rows in frozen menus.
2. Reduce reference scaffolding by archetype: rent, fuel, transit and tap lines should be mostly blank or bare month text, not "Order NNN".
3. Fix the ~8-10% residual invoice/order wording attached to receipt-style vendors (AH, Bloemenwinkel, tank stations, Bolt, NS).

Non-blocking:
4. Widen desc families per archetype and mix in bare bank strings ("SEPA Incasso ..." alone, "Overboeking diversen").
5. Recompute `escalate` for generic rows where the vendor determines the account; give disagree rows a `true_account` that the row supports or drop it.
6. Add rounding/VAT slips on a few rows, a few weekend/holiday bank lines, and rents that are mostly round (currently 11%).
7. Add non-templated invented vendors (personal names, "X & Y", numbers), fewer Noord/Oost/Centrum patterns.

## Gate

FAIL (0.80 < 0.85; frozen price menus about 19.6% of rows). Blocking fixes: 1, 2, 3. The revision cleared the round-1 killers (cross-pairing, fake suffixes, leaked tokens, weekends, contradicted amounts); the remaining failure is regularity, not contradiction.
