Background read: `docs/background.md` in full (including the ML categorization engine block), `docs/reports/vaultledger-ml-implementation-spec.md` sections 2, 5 and 6.4.2, the 2026-10-13 rows of `docs/reports/research/requests.md`, and rows 9 to 11 of `2026-10-12-customer-requirements.md` (unpassed draft, used only to avoid repeating it).

# The official RGS code list, and whether the 41 starter categories map to it

Scout: research-customer-scout. Date: 2026-10-13. Status: draft, not checked by the research skeptic. Nobody builds on it until `requests.md` shows "passed".

Why this exists: spec section 5 says every `rgs_code` stays null until the 41 starter micro categories have been checked against the real RGS, and the main executive ruled that no code is to be invented. This report answers request row 2 of 2026-10-13.

I am not an accountant or a lawyer. The mapping below is a reading of account names in the published list; it is not accounting advice. Section 6 lists what a Dutch accountant has to confirm.

## 1. Short answer

- The list is public and downloadable. The current definitive version is RGS 3.8; a 3.9 beta was published yesterday and 3.9 is planned for 11 December 2026.
- No licence statement was found on the publisher's site or in the file. A 2013 proposal to release RGS under CC0 is on the site; whether it was adopted, I could not verify.
- Of the 41 categories, 9 have one account-level (level 4) code whose name fits, 29 have several candidate codes, and 3 have no account-level code that fits. No code is recommended for the 32 that did not match.
- The main reason for "several candidates" is structural, not a gap in the search: the starter taxonomy sorts by what a payment is for, while RGS level 4 also splits by VAT rate, by kind of good, by kind of asset, by lender, and by legal form (sole trader against BV).

## 2. Sources

All read on 2026-10-13.

| Ref | What | URL |
|---|---|---|
| S1 | RGS site, home page | https://www.referentiegrootboekschema.nl/ |
| S2 | RGS site, "Over RGS" (governance) | https://www.referentiegrootboekschema.nl/over-rgs |
| S3 | RGS site, "RGS Taxonomie" (who maintains) | https://www.referentiegrootboekschema.nl/softwareontwikkelaars/rgs-taxonomie |
| S4 | RGS site, Kennisbank (list of all versions) | https://www.referentiegrootboekschema.nl/kbase |
| S5 | Kennisbank item "Definitieve versie RGS 3.8" | https://www.referentiegrootboekschema.nl/definitieve-versie-rgs-38 |
| S6 | Release notes for definitive 3.8 (docx) | https://www.referentiegrootboekschema.nl/releasenotes-bij-definitieve-versie-rgs-38 |
| S7 | News item "Bètaversie RGS 3.9 gepubliceerd" | https://www.referentiegrootboekschema.nl/Actueel/betaversie-rgs-39-gepubliceerd |
| S8 | Release calendar RGS 3.9 | https://www.referentiegrootboekschema.nl/releasekalender-rgs |
| S9 | "Opbouw RGS" (structure and levels) | https://www.referentiegrootboekschema.nl/opbouw-rgs |
| S10 | "Voorstel Licentievrij gebruik RGS" (pdf, 6 September 2013) | https://www.referentiegrootboekschema.nl/voorstel-licentievrij-gebruik-rgs |
| S11 | "Betrokken organisaties" | https://www.referentiegrootboekschema.nl/betrokken-organisaties |
| F | The downloaded file itself, sheet `Totaal-RGS3.8-def` unless another sheet is named | https://www.referentiegrootboekschema.nl/sites/default/files/kennisbank/RGS%203.8-def.xlsx |

## 3. Version, publisher, licence, download

| Item | Finding | Source | Mark |
|---|---|---|---|
| Current definitive version | RGS 3.8. The Kennisbank lists "RGS 3.8 - definitieve versie" as the newest definitive entry; above it is only "RGS 3.9 - consultatieversie" (alpha and beta) | S4, S5 | sourced |
| Date of 3.8 | The release notes are signed "Taakgroep RGS, .. december 2025" (day left blank in the document). The file's server date is 10 December 2025 and its internal last-saved date is 5 December 2025. A Kennisbank item published with it is named "NT20_RGS_20251210". So: December 2025, most likely published 10 December 2025 | S6; HTTP `Last-Modified` header and `docProps/core.xml` of F; S4 | month sourced; the exact day is my inference |
| What 3.8 is based on | The file's first sheet says it is the definitive RGS 3.8 "op basis van NT20-FT20" (the 2026 Dutch reporting taxonomies) | F, sheet `Recap` | sourced |
| Next version | 3.9 beta released by the Taakgroep RGS, news item dated 12 October 2026. Calendar: RGS 3.9 definitive 11 December 2026; RGS Taxonomie 3.9 on 15 January 2027. The beta note says 40 new codes and that the core since 3.0 is intact | S7, S8 | sourced |
| Who publishes and maintains | A public-private cooperation under the governance of SBR (Standard Business Reporting) since 2015. The Taakgroep RGS releases new versions; its Werkgroep Semantiek maintains the content. The taxonomy page names the "RGS Beheergroep" with software vendors, intermediaries, the Tax Administration, CBS, KVK, banks and Logius | S1, S2, S3, S11 | sourced. S2 says "Taakgroep" and S3 says "Beheergroep"; I could not verify whether these are two names for one body or an old and a new name |
| Licence or terms of reuse | None found. No licence, copyright or reuse statement on S1, S2, S3, S4, S5, S9 or S11, and none in the file (the word "licentie" occurs in F only inside two account names, `WOmzNooNdl` "Overige netto-omzet waarvan licenties overige netto-omzet" and `WBedOrgOct` "Octrooi en licentiekosten organisatiekosten") | S1 to S5, S9, S11, F | sourced that nothing is stated; "none exists" is not proven |
| The CC0 proposal | A memo of 6 September 2013 to the participants of an RGS meeting proposes Creative Commons Zero, states the aim that the standard "is and stays free of licence costs", and asks participants to agree in writing. It is a proposal. I found no record on the site that it was adopted | S10 | sourced for the proposal; adoption: could not verify |
| Rule on changing codes | As long as one refers to RGS as the standard, reference codes may not be changed or extended; requests go to the maintainer. The numeric "referentienummer" is only an example and a company may use its own numbering and its own descriptions | S9 | sourced |
| Download location | Kennisbank item S5, direct file link in row F | S5 | sourced |
| Format | One Excel workbook (xlsx), 2,508,990 bytes; the site states 2.39 MB. Six sheets: `Recap`, `Totaal-RGS3.8-def`, `RGS3.8-versus-RGS3.7`, `MKB-RGS3.8-def`, `WoCo-RGS3.8-def`, `Zorg-RGS3.8-beta` | F, S5 | sourced |
| Other forms | An XBRL "RGS Taxonomie" exists for each version; an English-labels workbook dated 13 September 2021 is in the Kennisbank. Neither was downloaded or checked | S3, S4 | sourced that they exist; contents not checked |

Where the file is: `C:\Users\ilhan\.claude\jobs\d0396725\tmp\rgs-download\RGS-3.8-def.xlsx` (outside the repository, alone in that folder). SHA-256 `5c47edd7a2dd23900e85f392dea9dd027ea45d44bf6973bf6400d4760e48e07a`. It was read as data with a standard-library script kept in a separate folder and run with `python -I`; nothing in it was executed.

What needs a professional's confirmation: whether a closed-source product may ship the code list (codes and Dutch names) inside its installer. The stated aim in S10 and the fact that commercial packages build on RGS (S11 lists vendors) point to yes, but no licence text says so. My inference only. A written answer from the maintainer through the site's contact form would settle it.

## 4. How the list is built (needed to read the table)

The meaning of the levels is sourced from S9; the examples and row counts are from F. (S9 gives its own example chain; its level-5 example code is not in the 3.8 file, so the examples here are taken from the file instead.)

| Level | Meaning | Example from F | Rows in F |
|---|---|---|---|
| 1 | Balance sheet or profit and loss (`W` "WINST- EN VERLIESREKENING") | `B` "BALANS" | 2 |
| 2 | Hoofdrubriek (main heading) | `BSch` "Kortlopende schulden" | 42 |
| 3 | Rubriek (heading) | `BSchBep` "Belastingen en premies sociale verzekeringen" | 295 |
| 4 | Grootboekrekening (ledger account). This is the "Rekeningen" level the spec asks for | `BSchBepBtw` "Te betalen Omzetbelasting" | 1,479 |
| 5 | Mutatie (movement within an account) | `BSchBepBtwAfo` "Afgedragen omzetbelasting " | 3,162 |

The row counts are my own count of sheet `Totaal-RGS3.8-def` (4,980 rows carrying a code). Two things do not add up and are reported as found, not explained:

- The `Recap` sheet's own example gives 4,976 codes in total.
- One level-3 code appears twice with two different names: `WKprKvg` "Kosten van grond- en hulpstoffen / halffabrikaten" and `WKprKvg` "Kosten van personeel". It is the only repeated code. One of the two is presumably a slip in the published file (my inference). It does not touch any code used below.

Each row also carries filter columns. Those used below: `Basis` (in the basic set), `EZ/VOF` and `BV` (specific to sole traders and partnerships, or to a BV), `Inactief` (no longer to be used), `Agro`.

## 5. The 41 categories against RGS 3.8

Rules I applied:

- Every code and name is copied from sheet `Totaal-RGS3.8-def` of F (columns `Referentiecode`, `Omschrijving`, `Nivo`). Nothing is written from memory. A script check of this report against the file is described in section 7.
- "match": exactly one level-4 code whose name covers the category, with no sibling level-4 code that an ordinary small BV would pick equally often. Near neighbours are still named in the reasoning.
- "several candidates": more than one code fits and the choice depends on something the category name does not say. The candidates are listed; none is picked. The code and name columns stay empty on purpose.
- "no account-level match": no level-4 code names the thing. The nearest codes are listed for the reader, not as a mapping.
- Source for every row: F.

| # | Category | Official RGS code | Official RGS name | Level | Result | Reasoning | Source |
|---|---|---|---|---|---|---|---|
| 1 | sales_domestic | (none picked) | | | several candidates | RGS splits revenue first by kind (three level-3 headings: `WOmzNop` "Netto-omzet uit leveringen geproduceerde goederen opbrengsten uit de verkoop van goederen", `WOmzNoh` "Netto-omzet uit verkoop van handelsgoederen opbrengsten uit de verkoop van goederen", `WOmzNod` "Opbrengsten uit het verlenen van diensten") and then by VAT box at level 4, for example `WOmzNodOdh` "1a. Netto-omzet uit verleende diensten belast met hoog tarief" and `WOmzNodOdl` "1b. Netto-omzet uit verleende diensten belast met laag tarief". Only the level-2 heading `WOmz` "Netto-omzet" covers the category | F |
| 2 | sales_eu | (none picked) | | | several candidates | One per kind of revenue: `WOmzNopOli` "3b. Netto-omzet uit leveringen geproduceerde goederen naar landen binnen EU", `WOmzNohOli` "3b. Netto-omzet uit leveringen handelsgoederen naar landen binnen de EU", `WOmzNodOdi` "3b. Netto-omzet uit verleende diensten naar landen binnen de EU" | F |
| 3 | sales_non_eu | (none picked) | | | several candidates | One per kind of revenue: `WOmzNopOln` "3a. Netto-omzet uit leveringen geproduceerde goederen naar landen buiten EU (uitvoer)", `WOmzNohOln` "3a. Netto-omzet uit leveringen handelsgoederen naar landen buiten de EU (uitvoer)", `WOmzNodOdb` "3a. Netto-omzet uit verleende diensten naar landen buiten de EU (uitvoer)" | F |
| 4 | other_income | (none picked) | | | several candidates | `WOvbOvoOvo` "Overige opbrengsten niet elders genoemd baten uit overige activiteiten" (other operating income) or, inside net revenue, `WOmzNooNdo` "Opbrengsten uit overige bronnen overige netto-omzet". Which one depends on whether the income counts as revenue | F |
| 5 | purchases_inventory | (none picked) | | | several candidates | `WKprInhInh` "Inkoopwaarde handelsgoederen" for trade goods; `WKprKvgKvg` "Kosten van grond- en hulpstoffen, ingekocht in Nederland kosten van grond- en hulpstoffen" and `WKprKvgKgi` "Kosten van grond- en hulpstoffen, ingekocht in het buitenland kosten van grond- en hulpstoffen" for materials; a company that books stock on the balance sheet uses heading `BVrdHan` "Handelsgoederen" (level 3) | F |
| 6 | subcontracting | `WKprKuwKuw` | Kosten van uitbesteed werk | 4 | match | Name fits directly; in the basic set. Neighbours that are a different thing: `WBedOvpZzp` "Ingehuurde ZZP-ers overige personeelskosten", `WBedEemWdd` "Werk door derden, overig" | F |
| 7 | freight_in | (none) | | | no account-level match | No level-4 code for inbound freight in the basic set. The only code with "vracht" in its name is on the sales side: `WBedVkkVrk` "Vrachtkosten verkoop gerelateerde kosten". Nearest others: `WBedTraAki` "Afhandelingskosten import", `WBedTraOtr` "Overige transportkosten transportkosten", and `WKprAklTra` "Transportkosten toegerekende kosten", which is flagged Agro and is not in the basic set | F |
| 8 | salaries | (none picked) | | | several candidates | The cost account is `WPerLesLon` "Lonen en salarissen", with `WPerLesSld` "Bezoldiging van bestuurders en gewezen bestuurders lonen en salarissen" for a director. But a bank row that pays net wages settles a liability, `BSchSalNet` "Netto lonen overige schulden". Which one a bank row gets depends on how payroll is booked (my inference; accountant to confirm) | F |
| 9 | payroll_tax_pension | (none picked) | | | several candidates | The category joins two RGS areas. Payroll tax: `BSchBepLhe` "Te betalen Loonheffing belastingen en premies sociale verzekeringen" (liability) and `WPerSolPsv` "Premies sociale verzekeringen sociale lasten" (cost). Pension: `WPerPenPen` "Pensioenpremies pensioenlasten" (cost) and `BSchOvsStp` "Te betalen pensioenpremies schulden ter zake van pensioenen" (liability). No single code can hold both | F |
| 10 | travel_reimbursement | (none picked) | | | several candidates | `WBedOvpRkv` "Reiskostenvergoeding", `WBedAutKil` "Kilometervergoeding autokosten en andere vervoermiddelen", `WBedVkkKmz` "Kilometervergoeding zakelijke reizen verkoop gerelateerde kosten", `WBedVkkKmw` "Kilometervergoeding woon-werkverkeer verkoop gerelateerde kosten" | F |
| 11 | training_education | `WBedOvpOpk` | Opleidingskosten | 4 | match | Name fits directly; in the basic set. Neighbour: `WBedOvpLbo` "Loopbaanontwikkeling" | F |
| 12 | rent | `WBedHuiBeh` | Betaalde huur huisvestingskosten | 4 | match | Rent paid for premises; in the basic set. Rent of equipment is elsewhere (`WBedEemHui` "Huur inventaris exploitatie- en machinekosten") and is not what the HOUSING category means | F |
| 13 | energy | (none picked) | | | several candidates | `WBedHuiGwe` "Gas,water en elektra (algemeen)", `WBedHuiGas` "Energiekosten gas", `WBedHuiElk` "Energiekosten elektra". The combined account also contains water, which the starter taxonomy keeps separate | F |
| 14 | water | `WBedHuiWat` | Energiekosten water | 4 | match | Name fits directly; in the basic set. Caveat: a company that uses the combined `WBedHuiGwe` "Gas,water en elektra (algemeen)" has no separate water account, and water-board levies sit in `WBedHuiMez` "Milieuheffingen en zuiveringsleges huisvestingskosten" | F |
| 15 | cleaning_maintenance | (none picked) | | | several candidates | The category joins two accounts: `WBedHuiSch` "Schoonmaakkosten huisvestingskosten" and `WBedHuiOng` "Onderhoud gebouwen huisvestingskosten" (also `WBedHuiOnt` "Onderhoud terreinen huisvestingskosten") | F |
| 16 | software_subscriptions | `WBedKanSof` | Kosten software abonnementen | 4 | match | Name fits directly; in the basic set. Neighbours: `WBedKanKoa` "Kosten automatisering kantoorkosten", `WBedKanCea` "Contributies en abonnementen kantoorkosten" | F |
| 17 | hardware | (none picked) | | | several candidates | No code names computers or hardware. Expensed purchases: `WBedKanKak` "Kleine aanschaffingen kantoorinventaris kantoorkosten", `WBedEemKai` "Kleine aanschaffingen inventaris exploitatie- en machinekosten", `WBedKanKoa` "Kosten automatisering kantoorkosten". Capitalised purchases: `BMvaBeiVvp` "Verkrijgings- of vervaardigingsprijs inventaris". Expense or asset is an accounting decision the category does not carry | F |
| 18 | telecom_internet | (none picked) | | | several candidates | `WBedKanTef` "Telefoonkosten kantoorkosten" and `WBedKanCom` "Communicatie". No cost account names internet; the only code with "internet" in its name is a bank account, `BLimBanInb` "Internetrekening  tegoeden bij banken" | F |
| 19 | office_supplies | `WBedKanKan` | Kantoorbenodigdheden kantoorkosten | 4 | match | Name fits directly; in the basic set | F |
| 20 | fuel | (none picked) | | | several candidates | By kind of asset: `WBedAutBra` "Brandstofkosten auto's autokosten en andere vervoermiddelen", `WBedTraBrr` "Brandstofkosten transportmiddelen transportkosten", `WBedEemBrm` "Brandstof machines exploitatie- en machinekosten". For a company with only passenger cars the first is the likely one (my inference) | F |
| 21 | public_transport | (none) | | | no account-level match | No code names public transport or train. Nearest: `WBedVkkRev` "Reis- en verblijfkosten verkoop gerelateerde kosten", `WBedOvpRkv` "Reiskostenvergoeding" | F |
| 22 | parking | (none picked) | | | several candidates | Two codes by kind of asset: `WBedAutPar` "Parkeerkosten auto's autokosten en andere vervoermiddelen" and `WBedTraPar` "Parkeerkosten transportmiddelen transportkosten" | F |
| 23 | car_lease | (none picked) | | | several candidates | Operational lease: `WBedAutOpa` "Operational leasing auto's autokosten en andere vervoermiddelen" (or `WBedTraOpt` "Operational leasing transportmiddelen transportkosten"). Financial lease is a liability, heading `BLasFlv` "Financiële lease verplichtingen (langlopend)" (level 3), with interest in `WFbeRlsRlv` "Rentelasten leaseverplichtingen" | F |
| 24 | taxi_ride_hailing | (none) | | | no account-level match | No code names taxi. Nearest: `WBedVkkRev` "Reis- en verblijfkosten verkoop gerelateerde kosten" | F |
| 25 | advertising | `WBedVkkRea` | Reclame- en advertentiekosten verkoop gerelateerde kosten | 4 | match | Name fits directly; in the basic set. Neighbour: `WBedVkkWeb` "Websitekosten verkoop gerelateerde kosten" | F |
| 26 | representation_meals | `WBedVkkRep` | Representatiekosten verkoop gerelateerde kosten | 4 | match | Name fits; in the basic set. Staff meals are a different account: `WBedOvpMlv` "Maaltijden en consumpties personeel". Whether a business meal is representation or staff cost matters for tax and is the accountant's call | F |
| 27 | gifts_relations | `WBedVkkRel` | Relatiegeschenken verkoop gerelateerde kosten | 4 | match | Name fits directly; in the basic set. Neighbour: `WBedVkkKer` "Kerstpakketten relaties verkoop gerelateerde kosten" | F |
| 28 | accounting_fees | (none picked) | | | several candidates | Two codes: `WBedAeaAea` "Accountants- en advieskosten" and `WBedKanBoe` "Boekhouding kantoorkosten" | F |
| 29 | legal_fees | (none picked) | | | several candidates | Two codes: `WBedAeaAej` "Advocaat en juridisch advies accountants- en advieskosten" and `WBedAeaNot` "Notariskosten accountants- en advieskosten". If the category is meant to exclude the notary, the first alone would be a match | F |
| 30 | consulting | (none picked) | | | several candidates | `WBedAeaAdv` "Overige advieskosten accountants- en advieskosten", `WBedAssAvk` "Overige advieskosten", `WBedOvpMaf` "Management fee overige personeelskosten" | F |
| 31 | bank_fees | (none picked) | | | several candidates | Two codes: `WBedAdlBan` "Bankkosten administratieve lasten" and `WFbeOrlRkb` "Rente en kosten bank" | F |
| 32 | interest | (none picked) | | | several candidates | RGS splits interest by direction and by counterparty. Paid: for example `WFbeRlsRlk` "Rentelasten  kredietinstellingen", `WFbeRlsRle` "Rentelasten overige leningen", `WFbeOrlRlb` "Rentelasten belastingen". Received: for example `WFbeRlmObr` "Rentebaten bankrekeningen rentebaten en soortgelijke opbrengsten". Only the level-2 heading `WFbe` "Financiële baten en lasten" covers the category | F |
| 33 | insurance | (none picked) | | | several candidates | By what is insured: `WBedAssBea` "Bedrijfsaansprakelijkheidsverzekering assurantiekosten", `WBedAssOva` "Overige assurantiepremies assurantiekosten", `WBedAutAsa` "Assurantiepremie auto's autokosten en andere vervoermiddelen", `WBedHuiAoz` "Assurantiepremies onroerende zaak huisvestingskosten", `WBedKanAss` "Assurantiepremie kantoorkosten" | F |
| 34 | vat_payment | (none picked) | | | several candidates | Two level-4 codes: `BSchBepBtw` "Te betalen Omzetbelasting" and `BSchBepBaf` "Omzetbelasting afdracht". The payment itself is a level-5 movement, `BSchBepBtwAfo` "Afgedragen omzetbelasting " | F |
| 35 | vat_refund | (none picked) | | | several candidates | `BVorVbkTvo` "Terug te vorderen Omzetbelasting vorderingen uit hoofde van belastingen" (receivable) or the same payable account as in row 34, `BSchBepBtw` "Te betalen Omzetbelasting", when the company keeps one VAT account | F |
| 36 | corporate_income_tax | (none picked) | | | several candidates | A bank payment settles `BSchBepVpb` "Te betalen vennootschapsbelasting" (flagged BV); a refund is `BVorVbkTvv` "Terug te vorderen Vennootschapsbelasting vorderingen uit hoofde van belastingen"; the cost for the year is `WBelBgrBgr` "Belastingen uit huidig boekjaar belastingen over de winst of het verlies"; there is also `BSchShbShb` "Schulden uit hoofde van belasting naar de winst" | F |
| 37 | other_taxes | (none picked) | | | several candidates | A remainder category spread over many codes, for example `WBedAdlOvb` "Overige belastingen administratieve lasten", `BSchBepOvb` "Overige belastingen", `WBedHuiOnz` "Onroerende zaakbelasting huisvestingskosten", `WBedAutMot` "Motorrijtuigenbelasting auto's autokosten en andere vervoermiddelen" | F |
| 38 | own_account_transfer | (none picked) | | | several candidates | A transfer is not an account in RGS; it is a movement between two bank accounts. The other side is whichever account receives it, for example `BLimBanRba` "Rekening-courant bank tegoeden bij banken", `BLimBanSpa` "(Bedrijfs)spaarrekening", `BLimBanDep` "Depositorekening  tegoeden bij banken", possibly through heading `BLimKru` "Kruisposten" (level 3) | F |
| 39 | loan_repayment | (none picked) | | | several candidates | By lender and term: `BLasSakLca` "Cumulatieve aflossingen leningen van kredietinstellingen (langlopend)", `BLasAoeCla` "Cumulatieve aflossingen andere obligaties en onderhandse leningen (langlopend)", `BLasOlsAfl` "Cumulatieve aflossingen overige schulden (langlopend)", `BSchAosLvk` "Leningen van kredietinstellingen (kortlopend)" | F |
| 40 | owner_withdrawal | (none picked) | | | several candidates | Depends on legal form. Sole trader or partnership: `BEivKapPro` "Privé-opnamen" (flagged EZ/VOF). BV: a current account such as `BVorOvrRca` "Rekening-courant aandeelhouders (kortlopend)" or `BSchOvsRcb` "Rekening-courant bestuurders (Kortlopend)", or a dividend, `BSchOvsTbd` "Te betalen dividenduitkeringen overige schulden" (all three flagged BV) | F |
| 41 | owner_deposit | (none picked) | | | several candidates | Depends on legal form. Sole trader or partnership: `BEivKapPrs` "Privé-stortingen" (flagged EZ/VOF). BV: `BSchOvsSaa` "Schulden aan aandeelhouders" for a shareholder loan, or share capital under headings `BEivGok` "Aandelenkapitaal" and `BEivAgi` "Agio" (both level 3, flagged BV) | F |

Count: 9 of 41 matched (rows 6, 11, 12, 14, 16, 19, 25, 26, 27). 29 have several candidates. 3 have no account-level match (rows 7, 21, 24).

All nine matched codes are level 4, debit (`D`) accounts, in the `Basis` set and not marked `Inactief` in F.

## 6. What this means for the product, and what needs a professional

- One line for the product: a single `rgs_code` per micro category cannot be filled for 32 of the 41 categories, so the field either stays null for those or the design changes; that is a decision, not a research finding. (my inference from section 5)
- Three ways the taxonomy and RGS could be brought together, none recommended here: (a) split or merge starter categories so each lands on one account, for example `payroll_tax_pension` into two and `cleaning_maintenance` into two; (b) map those categories at level 3 or level 2 instead of account level, which the spec's "at least at the account level" does not allow as written; (c) keep `rgs_code` null in the reference taxonomy and let the per-company mapping (spec 6.5) carry the company's own account, which already has an RGS code if their package is RGS-ready. (my inference)
- Bank rows against cost accounts: for wages, payroll tax, VAT, corporate tax and loan repayments a bank row usually settles a balance-sheet account while the cost was booked earlier from the payslip, return or invoice. Whether a bank-row category should point at the cost account or the liability account is an accounting design question for a Dutch accountant. (my inference; rows 8, 9, 34, 35, 36, 39)
- Legal form: rows 40 and 41 differ between a sole trader and a BV, and F marks the codes accordingly. The first customer's legal form is not known to me.
- Needs a professional's confirmation: every "match" row before it is shown to a customer (an accountant may read `WBedVkkRep` or `WBedHuiWat` more narrowly than the name suggests); the reuse terms of the list (section 3).
- Timing: RGS 3.9 definitive is planned for 11 December 2026 (S8). The beta note reports 40 new codes and corrections to descriptions (S7). The nine matched codes should be rechecked against 3.9 before anything ships; I did not open the 3.9 beta.

## 7. Self-check

- First line is "Background read:". Done.
- Every table row has a source column or a source in its cells. Done.
- Every RGS code in this report was checked by script against sheet `Totaal-RGS3.8-def` of the downloaded file: each code exists, and each quoted name equals the file's `Omschrijving` for that code after trimming surrounding spaces. Result of the run on 2026-10-13: 128 distinct codes in this report, 0 not in the file; 136 code-and-name pairs compared, 0 mismatches; the level stated for each of the nine matched codes equals the file's `Nivo`.
- Not checked: the XBRL taxonomy, the 3.9 beta file, the English-labels workbook, the `MKB-RGS3.8-def` sheet (the basic-set flag was read from the total sheet instead), and whether the first customer's accountant uses RGS at all.
- Product check: `rgs_code` is null today by ruling (background, ML track block). I did not open the `vaultledger-ml` code for this request: not checked.
