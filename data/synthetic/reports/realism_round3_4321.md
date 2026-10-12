# Realism review round 3, draw 4321 (stage 5 gate)

**Verdict: FAIL.** Realism score 46/60 = **0.767** (gate >= 0.85). Two artifact families are over the 10% limit on a count I can defend (description language unrelated to the vendor, 15.8% of rows; Monday pile-up of invoice dates, 12.3% of rows in excess), and a third sits on the line (forced whole-string Title Case / lowercase, 10.1%). This is my judgement of 60 + 20 sampled rows plus code counts over the 4000-row file. It is not a claim that the rest of the data looks real or unreal.

## Score

| Sample | Real-looking | Suspicious | Implausible | Score |
|---|---|---|---|---|
| Blind, 60 rows stratified by account (the gate) | 46 | 14 | 0 | **0.767** |
| Second sample, 20 non-easy rows (judged after metadata was open) | 11 | 3 | 6 | 0.550 |
| Both, 80 rows | 57 | 17 | 6 | 0.713 |

Sensitivity of the gate score. Three of the 14 calls are soft (1508, 1589, 3214). Dropping all three gives 49/60 = 0.817, still under the gate. Restricting to the 49 rows that metadata later showed to be `easy` gives 39/49 = 0.796. There is no reading of my labels under which the sample reaches 0.85.

## Sample

Blind pass: `random.seed(29)`, accounts sorted alphabetically, `random.sample` of the row indices of each account in turn, 9 rows for the first four accounts and 8 for the last three (60 is not divisible by 7). 0-based row indices of `transactions_4321.csv`:

General/Other 224 276 1165 1508 2236 2407 2647 2712 3859 | Office 88 180 656 1589 2445 2479 2874 3023 3217 | Professional 447 1021 1227 2049 2584 2791 3017 3214 3521 | Rent 1247 1712 1811 2137 2346 2620 2823 3058 3264 | Software 1168 1572 1772 2184 2310 3143 3229 3620 | Travel 1356 1400 2299 2856 3145 3476 3645 3649 | Utilities 582 1546 1660 2632 3157 3361 3652 3844

Metadata, opened afterwards, shows the blind sample was 49 easy, 6 hard, 5 ambiguous.

Second sample: `random.seed(29)` re-seeded, 20 rows from the non-easy rows not already in the first sample: 91 134 322 388 441 930 1234 1597 1600 1831 1917 1999 2286 2434 2600 2646 2890 3593 3759 3760.

### Blind sample: rows not judged real-looking (the other 46 were real-looking)

| idx | vendor | description | amount | label | reason |
|---|---|---|---|---|---|
| 1165 | ALBERT HEIJN | LUNCH VOOR TEAM 18-07-2025 - SEPA OVERBOEKING | 32.16 | suspicious | nobody pays a supermarket lunch by manual bank transfer |
| 1508 | Tuincentrum Groenland | Pltgrond en potten - Uw kenmerk 73049380 - SEPA Overboeking | 28.97 | suspicious (soft) | garden-centre purchase of EUR 29 by transfer with a customer reference |
| 2407 | NETLIFY | SEPA Overboeking Betaling januari 2026 | 6.52 | suspicious | US card-billed host paid by transfer and booked General/Other; nothing in the row argues against Software |
| 2647 | OV-chipkaart B.V. | Invoice INV001396 - February 2026 | 27.90 | suspicious | unpaid English invoice from a transit card under a legal name I do not recognise, booked General/Other |
| 1589 | Inktweb.nl | Betaling factuur INV-2025-00306 - Betaaltermijn 30 dagen | 22.41 | suspicious (soft) | a payment line that also states 30-day terms, for a EUR 22 webshop order already paid |
| 3214 | Baker Tilly | bet. factuur INV-2026-00807 - Bedrag excl. BTW 230,00 + 21% BTW 48,30 = 278,30 - Te betalen voor 24-05-2026 | 278.30 | suspicious (soft) | "bet." (paid) prefix, full VAT sum and a due date on an unpaid row; every clause at once |
| 2137 | Pandbeheer Van Alle Markten | Servicekosten december 2025 - Ref. 76567437 | 272.25 | suspicious | vendor name reads as a joke ("of all trades"), not a property manager |
| 2346 | WeWork B.V. | Payment ref 59591787 - Factuur 2025-0623 - Kenmerk 15878223 | 405.41 | suspicious | two unrelated 8-digit references plus an invoice number, no content |
| 2184 | NordVPN | Betalign factuur INV000763 - Payment ref 16785507 - Referentie 75744489 | 7.35 | suspicious | same double reference; NordVPN is a card subscription, not a Dutch "factuur" payer flow |
| 1400 | NS Reizigers B.V. (Flex) | Invoice INV000675 travel - Your reference 93122711 - Payment terms 30 days | 158.87 | suspicious | NS Flex is a monthly direct debit with Dutch statements, not an English 30-day invoice |
| 2856 | TOTALENERGIES | Payment March 2026 - SEPA Overboeking | 44.59 | suspicious | fuel paid by manual transfer, described as a monthly payment |
| 3476 | AVIA TANKSTATION | Overboeking bet. juni 2026 | 36.47 | suspicious | same: a petrol station is pin, card or fuel-card debit |
| 3645 | CHECK | Bike rental Arnhem - SEPA Overboeking | 10.43 | suspicious | Check rents shared mopeds in-app; "bike rental" by bank transfer does not happen |
| 2632 | REGIONALE NETBEHEERDER OOST | Factuurnummer INV-2026-00282, periode februari 2026 - Incasso | 45.99 | suspicious | generic invented grid operator; small customers are not billed monthly by the grid operator |

Rows I passed with a reservation: 276 (English "Payment POS 87" inside a BEA line), 656 and 1356 (OCR confusion inside a pin line, acceptable only if the source is a scanned slip), 88 and 3859 (keyboard typos inside iDEAL text), 3145 (RET day pass at 12.08, not a tariff I know), 3652 and 3844 (KPN and Vodafone described in English), 3143 (Mailchimp by "Incasso"; I could not tell whether Mailchimp offers SEPA debit). Had I failed these the score would be lower still.

### Second sample (non-easy rows)

| idx | vendor | description | label | reason |
|---|---|---|---|---|
| 134 | Flexa Kantoor | Pinbetaling Tanken diesel - Bedrag excl. BTW 73,73 + 21% BTW 15,48 = 89,21 | implausible | office landlord, pin payment for diesel |
| 930 | 123inkt | Microsoft 365 abon. juni 2025 - BTW verlegd naar afnemer | implausible | Dutch ink webshop with reverse-charged VAT |
| 2286 | Loom | Pinbetaling Whiteboard en stiften | implausible | video SaaS with a card-terminal purchase of stationery |
| 2646 | GVB | Exact Online boekhoudpakket februari 2026 - incl. 21% BTW | implausible | Amsterdam transit company invoicing accounting software |
| 3759 | Microsoft 365 | Toner cartridge b1ack - Re: invoice 202600774 | implausible | |
| 3760 | OV-chipkaart | SEPA Overboeking Netbeheer vastrecht aansluiting ju1i 2026 | implausible | transit card charging a grid connection fee |
| 388 | AWS EMEA | Sepa Overboeking Diversen | suspicious | AWS paid by manual transfer, "sundries" |
| 441 | HEMA B.V. | iDEAL betaling Kassabon 27-03-2025 | suspicious | "till receipt" on an online iDEAL payment |
| 3593 | Amazon.nl | Diversen - excl. BTW 199,93, BTW 21% 41,99, totaal 241,92 iDEAL | suspicious | "sundries" with a full VAT breakdown |

Real-looking: 91, 322, 1234, 1597, 1600, 1831, 1917, 1999, 2434, 2600, 2890.

## Artifact hunt (all 4000 rows, metadata opened after the blind pass)

Shares are of all 4000 rows unless stated. Ranked by share.

**1. Description language is unrelated to the vendor: 631 rows = 15.8% (over the limit).**
Counted only on bank and invoice text, which the vendor or the bank writes: 331 rows with an English description from vendor types that only write Dutch (energy, grid, water, telecom, KvK, city and regional transit, OV-chipkaart, NS, supermarkets, fuel, notaries, local shops), plus 300 rows with a Dutch description from a foreign reverse-charge vendor. Including receipts, English text on those Dutch vendor types is 524 rows (13.1%). Per vendor the English share clusters around 0.43 (quartiles 0.29 to 0.56 over the 79 vendors with 15 or more rows): KvK 29% English, NS 35%, Slack 37%, Microsoft 365 60%. Foreign SaaS is 51% English and 33% Dutch, Utilities 28% English. Examples: 3652 KPN "Incasso Mobile and internet subscription June 2026", 733 Eneco "Electricity and gas - monthly advance May 2025 - SEPA Incasso", 288 Qbuzz "SEPA Overboeking Bus and tram rides February 2025", 1410 KvK "Invoice number 0000372, period August 2025", 167 Slack Technologies Ltd "Betaling factuur 2025-0338 - BTW verlegd naar afnemer - Betaaltermijn 30 dagen", 2449 Adobe Systems Software Ireland Ltd "Factuur INV001349 januari 2026 - Kenmerk 94362931".
What I could not tell: if the description field is a memo typed by the user, language would follow the user, not the vendor. Even then one ledger would be consistently Dutch or consistently English, not a per-row coin flip inside one vendor's series (Slack, KPN, Spaces all alternate). I did not see this in the blind pass as a reason to fail rows; it is a count finding.

**2. Monday pile-up on invoice dates: 760 Monday invoices = 19.0% of rows; excess over the Tuesday-Friday mean 493 rows = 12.3% (over the limit).**
41.6% of invoices and 41.8% of bank lines fall on a Monday against 13-16% for every other weekday; none of the 3065 invoice and bank rows falls on a weekend. Weekend dates are rolled forward, so Monday collects three days. For fixed-day direct debits that is correct (a debit due on Saturday the 28th does land on Monday the 30th; KPN and Eneco behave this way and I count them as fine). For invoices it is not: automated billers date invoices on the billing day including weekends, and people who write invoices spread over the week. Manual transfers ("Overboeking") are 39% Monday as well. 22 of my 60 blind rows were Mondays and I did not notice while judging. Related, small: 37 bank lines (0.9%) are booked on days the SEPA settlement system is closed (1 January, Good Friday, Easter Monday, 1 May, 25 and 26 December), for example 5, 565, 568, 3264. Receipts: 12.9% on weekends.
Date is not a model feature in the train/val/test files, so the effect on the classifier is probably nil; the gate is on realism, so it counts.

**3. Whole-string Title Case or lowercase: 405 rows = 10.1% (marginally over the limit, low confidence).**
`casing_variation` rows split into 397 upper case, 260 Title Case and 145 all-lowercase. Upper case is normal on bank lines. Title Case over the entire string mangles acronyms and function words in a way I have not seen on documents: 51 "Geen Btw Van Toepassing - Betreft Factuur 2025-0720 - Betaaltermijn 30 Dagen", 103 "Re: Invoice Inv000720 - Sepa Incasso", 112 "Bea Nr:3431 Parkeersessie", 173 "Payment Of Invoice F2025/0591 ... 9% Vat". Lowercase invoices: 21 "payrnent january 2025 - vat 0%". Some export tools do recase text, so I cannot say every one of these is wrong; by the number it is over.

**4. Payment channel does not fit the vendor: 359 rows = 9.0% strict, 384 = 9.6% with card-billed SaaS (under the limit, 6 of 60 blind rows).**
Every bank line of a point-of-sale or app-charged vendor type is rendered as a manual transfer. "Overboeking" share of bank lines: city transit 53/53, regional transit 51/51, OV-chipkaart 30/30, supermarket 22/22, fuel 21/21, ride-hail 20/20, bike and scooter share 24/24, parking 52/53, rail 40/41. Examples: 1179 UBER *TRIP "Overboeking Rit 21-07-2025", 2537 PARKMOBILE "Parking session 80652763 - SEPA Overboeking", 2672 GVB AMSTERDAM "Overboeking Day pass Amsterdam", 1726 Albert Heijn "OVERBOEKING KASSABON 02-10-2025", 3416 "SEPA Overboeking OV-chipkaart saldo opwaarderen EUR 15,00", 62 GITHUB "... - Overboeking". Real lines for these are pin (BEA), card, iDEAL or direct debit (Parkmobile, Yellowbrick, NS Flex, automatic OV top-up). CREW.md revision 2 lists this as known and left to the corpus. A further 83 rows (2.1%) are invoices from instant-pay vendor types (28 Felyx "Bike rental Nijmegen" 6.47, 260 EasyPark "Parking session" 2.38, 177 Esso "Tankbeurt"); some of those are legitimate (fuel-card and trip invoices exist) and I did not count them. 418 rows (10.5%) are SEPA debit or transfer lines for foreign reverse-charge SaaS; Microsoft, Google and Adobe do offer SEPA debit, for Notion, Zoom, Figma, Twilio, 1Password and the rest I could not tell, so those are not counted either. If even a quarter of the uncounted rows are wrong, this family is over 10%.

**5. Prices carry no price points: retail exposure 624 rows = 15.6%, my estimate of the excess about 5% (not measurable without real data).**
Receipt amounts end in .99, .95 or .00 on 5.4% of rows, and the last digit is uniform (9, 5 or 0 on 32%, where chance is 30%). Single named items come out as Bureaulamp 20.32 (3217), Monitor stand 30.81 (3023), Koffiemachine 215.54 (1211), Ergonomic mouse 26.50 and 66.22 for the same item (855, 1596). Basket totals and fuel are legitimately diffuse, so only part of the 624 rows is affected. Transit: 30 "day pass / dagkaart" rows carry 29 different prices from 8.09 to 27.41 (3145, 2672, 1782); a day pass is a fixed tariff.

Smaller findings, all under 5%:

- **Cross-wired `vendor_description_disagree` rows: 112 = 2.8%.** See hard cases below.
- **Keyboard typos inside machine-written text: 113 = 2.8%** (iDEAL, SEPA and pin strings: 88 "iDEAL Otder", 197 "Payment of invlice", 315 "Fae"), and OCR confusion on bank-feed lines, 51 = 1.3% (170 "Parking session 9336555S", 178 "Invoice 202S00432"). OCR errors belong on scanned paper, typos on hand-typed memos.
- **Clause stacking.** Two or more unrelated 8-digit references in one line: 65 = 1.6% (2346, 2184, 121, 173). A payment prefix together with payment terms: 84 = 2.1% (3, 70, 167). Terms or due-date text on rows marked paid: 151 = 3.8% (14, 51, 60). 26.5% of rows carry an 8-digit number.
- **Frozen prices: 162 rows = 4.05%** by the round-2 definition (vendors with 10 or more rows and at most 3 distinct amounts): KvK 38, Swapfiets 18, Typeform 14, Wix 14, JetBrains 13, Squarespace 13, Oxxio 12, Nuon 10, Ziggo 10, HubSpot 10, Pipedrive 10. Under the limit.
- **Amount oddities.** Mijndomein hosting at 1431.05 three times (12, 117, 2531) against a median of 6.45 for that vendor type. KPN "mobile and internet" at 19-21 per month (291, 450). KvK appears 38 times at 85.15 in 20 months as "Jaarlijkse bijdrage handelsregister", an annual fee I do not know to exist today.
- **Brands that no longer trade under that name, with 2025-2026 dates:** Nuon (10 rows), Powerpeers (1660), Thalys (51), T-Mobile Thuis (21 rows), RealtimeBoard Inc (1772), "Translink"-style "OV-chipkaart B.V." (2647). I am going from memory here and may be wrong on dates.
- **Unpaid invoices never age.** 253 invoices dated before June 2026 are still unpaid at the end of the data (August 2026), with paid/unpaid apparently independent of age.

Checked and found acceptable: sentence frames (3312 distinct frames after masking digits and months; the top 20 frames cover 4.4% of rows); no single keyword separates a class (best coverage by a 90%-precision token: Utilities 30%, Software 24%, Rent and Professional 0%); invoice-number formats are consistent per vendor (1 of 83 vendors mixes three formats); no duplicate rows; VAT arithmetic in quoted totals; rent on the first business day; ex-VAT amounts whole euros for 81% of Rent and 67% of Professional rows; no invoice wording on receipts (0 rows); "Order" on rent, fuel, transit or utility lines (4 rows).

## Hard and ambiguous rows

472 non-easy rows (11.8%): 247 ambiguous (all escalated, booked General/Other) and 225 hard.

Genuinely ambiguous to a human, labels defensible: Albert Heijn and HEMA receipts (1234, 2600, 854), Action and Coolblue (1917, 1211, 1597), bol.com and Amazon order numbers with no item (2890, 619, 638), Shell and BP shop purchases against fuel (1999, 3382 against 2434, 1600), Google Ads against Workspace (1831, 2974, 3179). These read like real judgement calls and were mostly real-looking in the second sample.

Not ambiguous, cross-wired: the 112 `vendor_description_disagree` rows (45% of all ambiguous rows). A human does not see a hard classification in "GVB - Exact Online boekhoudpakket" (2646), "Loom - Pinbetaling Whiteboard en stiften" (2286), "Deutsche Bahn - Bijstand geschil, 6 uur" (979) or "GITHUB - BETAALAUTOMAAT SECOND-HAND ITEMS" (3819); a human sees the wrong vendor attached to a document. The vendor/true-account pairs are spread over the whole grid with no pattern. Real disagreement is narrower: a retailer selling something outside its usual line, as in the brand cases above. All 6 implausible rows in the second sample come from this case.

Mislabeled: 35 of those 112 rows (0.9% of all rows, 14% of ambiguous rows) have a description with no content word at all, so the row is indistinguishable from an ordinary payment to that vendor, yet it is booked General/Other with a `true_account` nothing in the row supports. Examples: 2407 NETLIFY "SEPA Overboeking Betaling januari 2026" (true account Travel), 2647 OV-chipkaart B.V. "Invoice INV001396 - February 2026" (Software), 1614 Cloudflare "Betaling factuur INV-2025-00927" (Utilities), 3003 EY "Payment of invoice INV-2026-00461 - VAT 21% 37.80" (Rent), 1791 NautaDutilh "Overboeking Invoice number 202500702, period October 2025" (Rent), 3141 Vistaprint "Invoice 0000275" (Software). Full list: 37 193 207 241 608 744 786 989 1061 1062 1614 1623 1791 1833 1978 1979 2029 2214 2220 2315 2406 2407 2441 2603 2647 2814 2993 3003 3141 3212 3220 3305 3740 3956 3990. A bookkeeper books each of these to the vendor's usual account. They teach the model that Netlify or EY with a bland description is General/Other.

## Vendors I do not recognise

From the two samples: Tuincentrum Groenland, Bloemisterij De Tulp, Notariaat Oost, Boekhoudservice Zuid, Loonadministratie Direct, Holding Pandbeheer Midden B.V., Pandbeheer Van Alle Markten, Werkspot Flexplekken (Werkspot is a tradesmen marketplace, not a workspace firm), Werkplek Eindhoven B.V., Regionale Netbeheerder Oost, OV-chipkaart B.V. (as a legal name), Flexa Kantoor.

Metadata flags 110 vendors (554 rows, 13.9%) as unverified; Rent is 57% unverified vendors, Professional 30%, Office 29%. Of those I recognise as real businesses: Staples, 9292, Cartridge World, Delta Energie, YOND, Tribes, Provast, NSI, Bouwinvest, Merin, Colliers, CBRE, JLL, Hines, Significant, Legalstart, Deskr, ANWB Wegenwacht, Vepa. The remainder I do not recognise, and most follow one pattern, trade plus compass point or city: Notariskantoor Centrum, Printerinkt Direct B.V., Taxi Utrecht Centrale, Accountantskantoor Noord B.V., Tankstation De Kruiseweg, Cloudnine Apps B.V., Boekhouder aan Huis, Administratiekantoor De Balans, Kantoorverhuur Utrecht / Rotterdam / Den Haag / Amsterdam-Zuid B.V., Vastgoed Beheer Zuid B.V., Vastgoed Noord Exploitatie B.V., Onroerend Goed Delta B.V., Flexwerken Utrecht, Flexwerkplek Centrum B.V., Bureau voor Vertalingen Centraal, Drukkerij Snelprint, Bedrijfsverzamelgebouw De Hoek, Stichting Bedrijfspanden Regio, Officeland, HR Partners Nederland, Hanos Kantoor, Toonbank Kantoorservice, Kabelshop, Schoolspullen Groothandel, Wheels4All Taxi, Tweakers Pricewatch Shop, Glasvezel Buitenaf B.V., Fiscaal Adviesbureau Centrum, Verpakkingsgroothandel Noord, Hobbyhandel Gouda, Belastingadviseurs Randstad, Bureau Strategie & Groei, Werkgebouw Binnenstad, Kantoorartikelen.nl, Businesscenter Leiden, Bureau Huren Rotterdam, Boek & Kantoor Centrum, Brasserie Het Plein, Broodjeszaak Centraal, Studio Verhuur Tilburg, Marketingadvies Delta, Compliance Advies Holland, Commerciele Ruimte Maastricht B.V., Eetcafe De Hoek, Kartonnage Verpakkingen NL, Octrooibureau Delta, Advocaten Utrecht Zuid, Kantoorruimte Groningen, Atelierruimte Kunstenaars Collectief, Bedrijfsruimte Zwolle B.V., Bloemenbank, Bloemenwinkel Centrum, Zakelijk Mobiel Nederland B.V., Loods en Opslag Verhuur Oost, Hub Nijmegen Werkplekken, IT Consultancy Rhijn B.V., Zoolplan Elektro, Werkloft Breda, Sleutelservice en Schoenmaker, Kantoorhotel Arnhem, Papierwaren De Schrijfhoek, Kapper en Barbershop Centrum, Sportschool FitPoint, Kabelwinkel.nl, Cateringservice Vers B.V., Waterschapsbelasting Zuid, Adviesgroep Noord B.V., Kantine Bedrijfsrestaurant Noord, Advocatenkantoor Rijnmond, Praktijkruimte Verhuur B.V., Restaurant De Gouden Lepel, Rotterdamse Taxi Coop, Autowasstraat en Tank Zuid, Bolddesk Software B.V., Paperman, Tonershop24, Bureaustoelen.nl. Some of these may exist; I have not checked any register.

## Fixes

I did not open the spec, the corpus or the generator, so the owning stage is inferred from CREW.md.

Blocking:

1. **Tie description language to the vendor** (stage 1 spec for the rule, stage 2 corpus for a per-vendor language flag, stage 3 generator to apply it). Dutch-only vendor types get Dutch bank and invoice text; foreign reverse-charge vendors get English invoice text with at most the Dutch bank prefix; if English memos are wanted, make language a property of the ledger or of a vendor, not a per-row draw. Target under 10% by the count in artifact 1.
2. **Stop rolling invoice dates to Monday** (stage 3 generator, stage 1 for the weights). Automated billers keep the calendar day including weekends; hand-written invoices draw a weekday directly. Keep the roll-forward for direct debits only, and roll past the SEPA closing days as well. Target: Monday share of invoices under 25%.
3. **Give card and app vendors a real bank channel** (stage 2 corpus doc mix, which CREW.md already names as the owner; stage 3 for the wording). Bank lines for transit, parking, fuel, supermarkets, ride-hail, sharing and OV top-ups become pin, card or direct-debit text, never "Overboeking"; drop transfers for card-billed SaaS. This is at 9.0-9.6% and accounts for 6 of the 14 failed rows in the blind sample, so the score cannot pass without it.
4. **Repair the disagree case** (stage 1 spec for the definition, stage 3 generator). Never emit a disagree row whose description has no content word; either keep the vendor's account for it or redraw. Restrict the remaining disagree rows to pairs a business could produce (retailer selling outside its line), and drop pairs such as transit operator plus accounting software.
5. **Casing** (stage 3 generator, stage 1 for the rate). Cut whole-string Title Case and lowercase to well under 10% combined, and keep acronyms (BTW, VAT, SEPA, BEA NR, INV) intact when recasing. Cheap, and it removes the third family from the threshold.

Non-blocking:

6. Price points for single-item retail lines and fixed tariffs for day passes (stage 2 corpus price lists, stage 3).
7. Keep typos to hand-typed memo text and OCR confusion to invoices and scanned receipts; none on iDEAL, SEPA or pin strings (stage 3).
8. One reference per line; no payment terms on lines that start with a payment word; fewer terms on rows marked paid (stage 3).
9. Amount sanity: Mijndomein 1431.05, KPN bundle at 20, KvK as a 38-times recurring annual fee (stage 2 corpus).
10. Replace retired brand names or date them before the rename: Nuon, Powerpeers, Thalys, T-Mobile Thuis, RealtimeBoard (stage 2 corpus).
11. Vendor names: fewer trade-plus-compass-point inventions, especially in Rent (57% unverified); remove "Pandbeheer Van Alle Markten", "Werkspot Flexplekken", "Regionale Netbeheerder Oost" (stage 2 corpus).
12. Let unpaid invoices age into paid (stage 3).
13. Stage 4 auditor could carry three cheap counters so these do not depend on a reader: weekday histogram per document type, language by vendor type, "Overboeking" share per archetype.

## Round 2 versus round 3

Written last, after all scores and counts above were fixed. Round 2 used seed 11 and a different sample, so the scores are not a paired comparison.

| Round-2 item | Round 2 | Round 3 |
|---|---|---|
| Realism score, 60-row sample | 48/60 = 0.80 | 46/60 = 0.767 |
| Frozen price menus (vendors >= 10 rows, <= 3 amounts) | about 19.6% | 4.05% (162 rows); Microsoft 365 now 13 amounts, Zoom 44, Adobe 9, Dropbox 7, Slack 6 |
| Whole-euro amounts on USD-billed SaaS | 73% | 13.1% of reverse-charge rows |
| Rows with an 8-digit reference | 33% | 26.5%; two or more references on 1.6% |
| "Order" text on rent, fuel, transit, utility lines | present (2605, 3983, 2858) | 4 rows |
| Invoice or order wording on receipts | about 8% of sample rows | 0 rows carry invoice wording on a receipt |
| "SEPA Incasso" share | 14.0% | 16.6%; "algemeen doorlopend" 5.1%; I did not count it as an artifact |
| Stacked payment text | 2.0% | payment prefix plus terms 2.1%; terms text on paid rows 3.8% (round 2 reported zero) |
| Truncated / typo / OCR | 7.6% / 5.4% / 4.8% | 8.0% / 5.4% / 4.7% (unchanged) |
| Whole-euro share, Rent and Professional | 11% and 14% of totals | totals 12% and 12%; ex-VAT 81% and 67%, which is the right place for it |
| Weekend dates | 3.7% overall, 0% bank/invoice, receipts about 16% | 3.0% overall, 0% bank/invoice, receipts 12.9% |
| Over-tidy calendar | noted, not counted | counted: Monday 41.7% of bank/invoice rows, 37 bank lines on SEPA closing days |
| Disagree rows with unsupported true account | noted (Bruna, Etos) | 35 of 112 have no content word (0.9% of rows) |
| Invented vendor names | 9 of top 15 unverified | unchanged pattern, 110 unverified vendors, 13.9% of rows |

The three round-2 blocking items (frozen prices, order scaffolding, invoice wording on receipts) are cleared by the counts. The score did not improve: the failures moved from price and reference regularity to payment channel, language and stacking, two of which round 2 did not count. Round 2 judged a bank transfer to NS suspicious (2858) but did not measure the channel; language was mentioned once (2830).

## Process deviations

- CREW.md was read only after the blind pass, as instructed for this round, and then in full including the revision notes. The spec, corpus and generator were never opened.
- Stratification was by account only; difficulty lives in metadata. Sizes are 9/9/9/9/8/8/8.
- The weekday of each sampled row was printed during the blind pass; I still missed the Monday pattern while judging.
- The second sample and all counts were made with metadata open, so the 0.550 is not blind.
- A TF-IDF logistic regression on the vendor-disjoint split (description only 0.647, vendor only 0.304, both 0.669 test accuracy) was run as a quick separability check; that is stage 6 territory and is informational only.
- Whether individual foreign SaaS vendors offer SEPA debit, whether the named retired brands are truly retired at these dates, and whether any unrecognised vendor exists were not verified against any source.

## Gate

FAIL. Score 0.767 < 0.85; language/vendor mismatch 15.8% and invoice Monday excess 12.3% exceed 10%; casing 10.1% is marginally over; payment-channel mismatch is 9.0-9.6% with uncounted rows that could take it over. Blocking fixes 1 to 5.
