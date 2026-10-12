# Product functions worth adding, 2026-10-12

Author: `research-product-scout`. Every source below was read on 2026-10-12.
Each claim is marked **S** (sourced: the page says it) or **I** (my inference).
Source numbers refer to the list at the end. Vendor pages and app-store
listings are marketing copy; review sites are self-selected opinion.

## What I could not verify

- **XAF 4.0 "mandatory as of 1 January 2026"** (action list, decided item 3).
  I found no primary source for it. The only page stating that date is a
  commercial blog [11]. SRA reported a consultation version in November 2024
  with no date [9]. A trade article of 26 June 2026 says 4.0 "is coming" and
  that the Belastingdienst phases out older versions on 1 January 2027 [10].
  auditfiles.nl did not resolve. Treat the date as unconfirmed.
- **Dutch B2B e-invoicing on 1 July 2030**: one secondary source, citing a
  policy letter of 11 September 2026; the bill is not yet submitted [12].
- Belastingdienst's own retention pages returned 404; I used the government
  site business.gov.nl instead [7].
- Dext's own pricing page (404), Capterra and Basecone's product page (403):
  figures come from the Xero marketplace listing [3] and search summaries.
- Moneybird booking rules and duplicate handling, e-Boekhouden, SnelStart,
  Klippa, Tellow, Yuki, Hubdoc: nothing usable found. Not in the table.

## The field

| Product | Type | Where data is processed | Relevant functions | Source |
|---|---|---|---|---|
| Moneybird (NL) | Bookkeeping suite | Hosted | Receipt capture by app, own email address or upload; reads UBL; pays purchase invoices; e-VAT return from the EUR 15 plan; accountant access on all plans; bank links only from EUR 29 plan; 7-year document retention | [1][2] S |
| Exact Online Scan & Herken (NL) | Capture add-on | Hosted | Upload, phone, email inbox; proposed booking from stored supplier data, final after approval; several invoices in one file; original kept with the entry; EUR 0.55 per scan (brochure dated 2018) | [5] S |
| Basecone (NL) | Pre-accounting | Hosted | UBL read without OCR, per line or per VAT rate; saved booking rules per supplier; authorisation flows by supplier, amount or file type | [6] S, flows from search summary [6b] |
| Dext | Capture | Hosted | Supplier, date, total, tax, line items; supplier rules; duplicate detection; approvals; app, email, WhatsApp intake; document vault; mileage; from GBP 30/month with only 5 line-item and 10 bank-statement extractions included | [3] S |
| AutoEntry | Capture | Hosted | Credit pricing: 1 per document, 2 with line items, 3 per bank-statement page | [4] S (search summary of Sage page) |
| Paperless-ngx | Document archive | Self-hosted | Local OCR archive; GPL-3.0, so not usable inside our product | [13] S |
| HappyTaxes | Offline bookkeeping app | On device (Android) | Tesseract receipt OCR, local zip backup; MIT; developer's own claims | [14] S |

I: none of the Dutch products a startup would compare us with is on-device.
The only on-device products found are a personal document archive and a
single-developer Android app. Privacy is our distinct position; the function
gap is everything around the core loop.

## What users complain about and pay extra for

- Moneybird, Trustpilot NL, Sept-Oct 2026: repeated price rises; bank links
  locked to the dearer plan; bank-link outages and a wrong balance after
  linking; AI pre-filled purchase invoices with wrong descriptions that need
  manual checking. Moneybird's reply offers manual CAMT.053 or MT940 upload as
  the alternative [8] S.
- Dext and AutoEntry, Capterra (search summary, page not readable): Dext seen
  as expensive; duplicate checks both miss copies and, in AutoEntry, wrongly
  drop monthly invoices from the same supplier [15] S, weak.
- Paid extras: line items, bank-statement extraction, supplier statements
  (Dext, AutoEntry) [3][4] S; bank links (Moneybird) [1] S.

## Ranked functions

Size: S small, M medium, L large. All twelve run fully on the machine.

| # | Function | Who has it | Evidence of value | Size and what it depends on |
|---|---|---|---|---|
| 1 | **Keep the original document with each entry** (stored per user, content hash, opened from the ledger row) | Exact, Moneybird, Dext vault [5][2][3] S | Records must be kept 7 years and digital files must stay readable at inspection [7] S. Today the upload is deleted after processing (`webapp/app.py:279`); only the filename is kept (I, from code) | S-M. `userdata.py`, `ledger.py` (new columns), `backup.py` size limits |
| 2 | **VAT (BTW) capture**: net, VAT amount, rate (0, 9, 21 %), reverse-charge flag, supplier VAT number | Dext tax field; Basecone split per VAT rate [3][6] S | Dutch rates and reverse charge [16] S. Without it the bookkeeper re-keys every document for the VAT return (I) | L. Locale profile and field parser; a new input-VAT account and a new rule in `entry_rules.py` (load-bearing spec, needs deliberate review); queue, ledger and export columns |
| 3 | **Supplier memory**: once a reviewer confirms a vendor to an account, the same vendor is proposed to that account by a rule, shown as "rule", not as a model guess | Dext supplier rules; Basecone booking rules; Exact supplier master data [3][6][5] S | The shipped classifier clears the 0.75 gate on nothing yet (README), so this is what makes bulk confirm real (I) | S-M. `corrections.py`, `ledger.py` lookup, `pipeline.py`, `confidence_gate.py`. Per user, so no cross-user leak |
| 4 | **Duplicate warning**: same file hash, or same vendor + date + amount (+ invoice number once extracted) | Dext [3] S | Reviews show both misses and false positives [15], so warn in the queue, never drop silently (I) | S. Needs the hash from #1; `queue.py`, `ledger.py`. Invoice number is not extracted today |
| 5 | **Structured e-invoice import (UBL 2.1 / NLCIUS XML)**: exact fields, no OCR | Moneybird, Basecone, Exact [2][6][5] S | Planned NL mandate 2030, unconfirmed [12]; removes OCR error and gives VAT lines for free (I) | M. New parser beside `extraction/pdf.py`, Python standard-library XML (PSF licence, already in use). Best after #2 |
| 6 | **Bank statement file import and matching** (CAMT.053, MT940): match to entries, set paid from fact, list payments with no document | Moneybird file upload [8] S; Dext and AutoEntry charge for statement extraction [3][4] S | Bank-link limits and outages are the top Moneybird complaint after price [8] S | L. New store and matcher; replaces the paid heuristic feeding rule R4 in `entry_rules.py`. `mt-940` is BSD-3-Clause, v5.1.1 [17] S; CAMT is XML, standard library |
| 7 | **Accounting-package hand-off**: period zip with import-shaped CSV, originals and audit file | Accountant access on every Moneybird plan [1] S | An accounting firm praises easy client hand-off [8] S. Export target is already decided (action list 3); the current `BOOKS_HEADER` is generic (I) | M. `reports.py`; needs #1, better with #2. Check a real Moneybird or Exact import file first (open item 1) |
| 8 | **Change history per entry**: who, when, old and new value, append-only | Basecone authorisation trail [6b] S, weak | Retention rules require checkable records [7] S; the audit export has no user and no field edits (I, from `reports.py`) | M. `ledger.py`, `queue.py`, `auth.py`. XAF export is a later step; version and date unconfirmed (see top) |
| 9 | **Intake without the upload button**: watched folder, and phone camera through the local web page | App and email intake at Moneybird, Exact, Dext [2][5][3] S | Every compared product has it (S); a watched folder is the on-device stand-in for an email inbox (I) | S for folder (`batch.py`); M for phone (HTTPS on the local network, and photos are untested per the OCR review) |
| 10 | **Search and filters** over documents and ledger | Exact: everything found quickly [5] S, marketing | I: needed once the archive holds a year of documents | S. Filter over CSV now; SQLite FTS5 later (public domain [18] S) |
| 11 | **Recurring-bill recognition**: expected monthly bill missing, or amount far from usual | Exact "continuous monitoring" signals [5] S, marketing | I: cheap by-product of #3 and #6 | S-M. Reads the ledger; plain arithmetic, no model |
| 12 | **Line items and several invoices in one file** | Dext, AutoEntry (metered) [3][4] S; Exact multi-invoice [5] S | Sold as a paid extra, so some users value it (I) | L. Needs all-pages reading and word positions (both "later" in the OCR review), and split entries in the rules |

Suggested order (I): 1, 3 and 4 are small and make the demo believable;
2 is the gate for a Dutch customer and should be specified before 5, 6 and 7.

Licence note: `rapidfuzz` (MIT, v3.14.6 [19] S) is suitable for fuzzy vendor
matching in #3 and #4. `python-stdnum` validates Dutch VAT numbers but is
LGPL-2.1-or-later [20] S, which is copyleft: do not adopt it; write the check
ourselves.

## Do not build

| Function | Who has it | Why not |
|---|---|---|
| Live bank feeds | Moneybird (via Ponto) [8] S | Transactions pass through a third party, breaking the core claim; it is also the most complained-about part [8]. File import (#6) gives the same result |
| Hosted email inbox, WhatsApp intake | Moneybird, Exact, Dext [2][5][3] S | Needs a hosted mail service that receives customer documents. Watched folder instead |
| Paying invoices from the app | Moneybird, Dext [2][3] S | Bank connections and payment regulation; outside pre-accounting (I) |
| Filing the VAT return | Moneybird [1] S | The accounting package already files it; we supply clean VAT figures (#2) (I) |
| Multi-step approval flows | Basecone, Dext [6b][3] S | Built for firms; a startup has one reviewer, and `is_admin` grants nothing yet. Revisit for bookkeeping firms (I) |
| Auto-posting without review, "100 %" or "99.9 %" accuracy claims | Exact, Dext [5][3] S | Users report having to recheck AI pre-fill [8] S; our honest accuracy panel is a selling point (I) |
| Mileage, expense claims, cards, web-shop links | Dext [3] S | Different product (I) |
| Embedding Paperless-ngx | - | GPL-3.0 [13] S |

## Sources (all read 2026-10-12)

1. https://www.moneybird.com/pricing/ (vendor)
2. https://www.moneybird.com/features/purchase-invoices/ (vendor)
3. https://apps.xero.com/uk/app/dext (marketplace listing, vendor copy)
4. https://www.sage.com/en-us/products/sage-50/add-ons/autoentry/ (vendor; search summary only)
5. https://files.exact.com/static/web/downloads/NL-ACY-Brochure-Efficie%CC%88nter-werken-met-scan-herken.pdf (vendor brochure, 2018)
6. https://support.basecone.com/en/articles/633128-submitting-and-processing-invoices-in-ubl
   6b. https://support.basecone.com/en/articles/2428795-authorisation-flow (search summary only)
7. https://business.gov.nl/regulation/keeping-business-records/ (government)
8. https://nl.trustpilot.com/review/moneybird.nl (user reviews and vendor replies)
9. https://www.sra.nl/nieuwsoverzicht/2024/consultatieversie-auditfile-financieel-4-xaf-beschikbaar
10. https://www.accountancyvanmorgen.nl/2026/06/26/xaf-4-0-komt-eraan-maar-de-accountant-zit-nog-te-stoeien-met-excel/
11. https://invoicedataextraction.com/blog/netherlands-auditfile-financieel-xaf-requirements (commercial blog; search summary only)
12. https://www.banqup.com/nl-be/resources/compliance-pulse/nederland (vendor; page updated 14 September 2026)
13. https://github.com/paperless-ngx/paperless-ngx
14. https://f-droid.org/en/packages/io.github.dorumrr.happytaxes/ (search summary only)
15. https://www.capterra.com/p/160189/Dext/reviews/ and https://www.capterra.com/p/227227/AutoEntry/reviews/ (search summary only)
16. https://business.gov.nl/regulation/vat-rates-exemptions/ (government)
17. https://pypi.org/project/mt-940/
18. https://www.sqlite.org/copyright.html
19. https://pypi.org/project/rapidfuzz/
20. https://pypi.org/project/python-stdnum/
