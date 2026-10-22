Background read: `docs/background.md` in full (including the ML categorization engine block), `docs/reports/vaultledger-ml-implementation-spec.md` sections 2, 5 and 6.4.2, the 2026-10-13 rows of `docs/reports/research/requests.md`, and the three 2026-10-12 research drafts searched for earlier KvK or SBI findings (there are none beyond the invoice-field row).

# Is there an offline company-name-to-SBI source we may ship?

Scout: research-customer-scout. Date: 2026-10-13. Status: draft, not checked by the research skeptic. Nobody builds on it until `requests.md` shows "passed".

Why this exists: spec section 6.4.2 prefers an offline table (normalised company name to KvK SBI activity code) shipped with the app, marked [VERIFY], because looking a vendor up online would send its name off the device. The main executive ruled the activity field stays empty or export-learned until research passes. This report answers request row 1 of 2026-10-13.

I am not a lawyer. Everything below reports what the sources say or is marked as my inference. Section 6 lists what a lawyer or KVK itself has to confirm. Online lookups are out of scope by the constraint and were not evaluated.

## 1. Short answer

No usable source was found.

- The one KVK data set that is openly licensed (CC BY 4.0) has no company name and no KVK number in it, on purpose. It cannot map a name to anything.
- KVK's paid products do contain trade names with SBI codes, but KVK's published terms refuse permission for passing register data on to third parties, and require a separate request before personal data (which KVK says includes data of sole traders) is reused. Shipping a name table in an installer needs KVK's written agreement at the least; whether KVK would give it, I could not determine.
- The CBS SBI code table (code to description, no companies) may be shipped under CC BY 4.0 with attribution. It is useful, but it is not a name lookup.
- Third parties either republish KVK data under share-alike terms, sell it under contract, or carry no SBI code.

So for now spec 6.4.2 falls back to its options 2 and 3 (learn the activity from the customer's own export, or leave it empty), which is what the ruling already says.

## 2. Sources

All read on 2026-10-13.

| Ref | What | URL |
|---|---|---|
| K1 | KVK, "Handelsregister Open Dataset Basis Bedrijfsgegevens" (page updated 7 August 2025) | https://www.kvk.nl/producten-bestellen/kvk-handelsregister-open-data-set/ |
| K2 | The data set itself, downloaded and inspected (file dated 12 October 2026) | https://www.kvk.nl/download/kvk-open-dataset-basis-bedrijfsgegevens.zip |
| K3 | data.overheid.nl catalogue entry for K1 | https://data.overheid.nl/dataset/kvk-handelsregister-open-dataset-basis-bedrijfsgegevens |
| K4 | KVK, "Gebruikersvoorwaarden Handelsregistergegevens" (page updated 17 June 2026) | https://www.kvk.nl/over-het-handelsregister/gebruikersvoorwaarden-handelsregistergegevens/ |
| K5 | KVK, "Gebruiksvoorwaarden Verstrekking en gebruik Handelsregistergegevens", in use since 1 January 2021, with annex on the Databankenwet (pdf) | https://production-site-nl.kvk.bloomreach.cloud/binaries/content/assets/kvkwebsite-nl/categorie/producten-bestellen/gebruiksvoorwaarden-verstrekking-en-gebruik-handelsregistergegevens.pdf |
| K6 | KVK, explanation of the annex, June 2021 (pdf) | https://production-site-nl.kvk.bloomreach.cloud/binaries/content/assets/kvkwebsite-nl/categorie/handelsregister/kvk-_toelichting_gebruiksvoorwaarden_verstrekking_en_gebruik_handelsregistergegevens.pdf |
| K7 | KVK, "Handelsregister selecties offline" (address file product) | https://www.kvk.nl/producten-bestellen/kvk-handelsregister-adressen-offline/ |
| K8 | KVK, "Handelsregister bestandsvergelijking" | https://www.kvk.nl/producten-bestellen/kvk-handelsregister-bestandsvergelijking/ |
| K9 | KVK, "KVK Dataservice" | https://www.kvk.nl/producten-bestellen/kvk-dataservice/ |
| K10 | KVK tariff sheet per 1 January 2026 (pdf), linked from https://www.kvk.nl/over-het-handelsregister/hoe-bepalen-wij-onze-tarieven/ | https://production-site-nl.kvk.bloomreach.cloud/binaries/content/assets/kvkwebsite-nl/categorie/handelsregister/tarievenoverzicht_1_januari_2026.pdf |
| K11 | KVK press release, 23 December 2021, on the VVZBI judgment | https://www.kvk.nl/pers/reactie-kvk-op-uitspraak-vonnis-vvzbi-kvk-december-2021/ |
| K12 | KVK, list of recognised partners (page updated 21 January 2026) | https://www.kvk.nl/over-het-handelsregister/betrouwbare-handelsregisterproducten-via-erkende-kvk-partners/ |
| K13 | KVK, "Overzicht Standaard Bedrijfsindeling (SBI-codes)" (page updated 13 October 2026) | https://www.kvk.nl/over-het-handelsregister/overzicht-standaard-bedrijfsindeling-sbi-codes-voor-activiteiten/ |
| C1 | CBS, "Standaard Bedrijfsindeling (SBI)" | https://www.cbs.nl/nl-nl/onze-diensten/methoden/classificaties/activiteiten/standaard-bedrijfsindeling--sbi-- |
| C2 | CBS, SBI 2025 structure, version 2026, Dutch and English (xlsx) | https://www.cbs.nl/-/media/cbs/onze-diensten/methoden/classificaties/documents/2025/sbi2025-structuur-versie-2026-code-zonder-puntjes-nl-en-en.xlsx |
| C3 | CBS, "Copyright" | https://www.cbs.nl/nl-nl/over-ons/website/copyright |
| A1 | Autoriteit Persoonsgegevens, news item of 10 August 2022 | https://autoriteitpersoonsgegevens.nl/nl/nieuws/ap-stel-grenzen-aan-opnieuw-gebruiken-van-persoonsgegevens-uit-overheidsdata |
| T1 | overheid.io, OpenKvK API documentation | https://overheid.io/documentatie/openkvk |
| T2 | overheid.io, general terms | https://overheid.io/algemene-voorwaarden |
| T3 | OpenCorporates, terms of use | https://opencorporates.com/terms-of-use-2/ |
| T4 | GLEIF, LEI data terms of use | https://www.gleif.org/en/meta/lei-data-terms-of-use |
| T5 | GLEIF, LEI common data file format 3.1 | https://www.gleif.org/en/about-lei/common-data-file-format/current-versions/level-1-data-lei-cdf-3-1-format |

## 3. Candidates

### 3.1 KVK Handelsregister Open Dataset Basis Bedrijfsgegevens

| Point | Finding | Source | Mark |
|---|---|---|---|
| Fields | Eight columns: `Datum aanvang`, `Actief`, `Insolventie`, `Rechtsvorm`, `Postcode regio`, `SBI activiteiten`, `Hoofdactiviteiten`, `Lidstaat` | K2 (header row of the file), K1 | sourced |
| Is the trade name in it? | No. KVK lists "Naam van de organisatie" and "Het KVK-nummer" among the data not supplied, and only the first two digits of the postcode are given. The file has no name or number column | K1, K2 | sourced |
| Why | KVK says the name, KVK number and address cannot be treated as non-personal in every case, that it cannot judge this case by case, and so leaves them out of the high-value data set | K1 | sourced |
| Licence | CC BY 4.0. Using the data set means accepting those terms | K1, K3 | sourced |
| Extra condition | It is not allowed to enrich the data set in a way that makes the data traceable to an individual person | K1 | sourced |
| Delivery terms | The page links "leveringsvoorwaarden"; the link is built by script and I could not open it | K1 | could not verify |
| Commercial redistribution | Allowed by CC BY 4.0 with attribution, subject to the enrichment ban above | K1 | sourced for the licence; what the unread delivery terms add: could not verify |
| Sole traders, personal data | None. KVK lists "Gegevens van eenmanszaken" as not supplied and says the data set contains no personal data. The file holds only two legal forms: 1,919,427 rows `BV` and 5,308 rows `NV` | K1; my count of K2 | sourced |
| Size | Zip 12,926,457 bytes; one CSV of 96,864,418 bytes; 1,924,735 data rows, semicolon-separated | K2 (my measurement) | sourced |
| Update frequency | Every working day | K1 | sourced |
| Delivery form | Zip with one CSV by public download. There is also an API that is queried by KVK number; that is an online lookup and out of scope | K1, K3 | sourced |

What it means for the product: it cannot serve as the name-to-SBI table, because there is nothing in it to match a vendor on. Combining it with names from elsewhere to rebuild the mapping is exactly the enrichment KVK forbids where it leads to a person (my inference from K1).

Verdict: may ship as far as the licence goes (CC BY 4.0, attribution), but it does not contain the mapping, so for this purpose it is not a usable source.

### 3.2 KVK paid bulk products

Products found: "Handelsregister selecties offline" (an address file on a selection), "Bestandsvergelijking" (KVK matches a file you send against the register), "Mutatieservice" (subscription to changes) and "Dataservice" (a SOAP connection, paid per query).

| Point | Finding | Source | Mark |
|---|---|---|---|
| Fields | Address file: name and address data plus optional extra fields, selectable by SBI code (main or secondary activity), legal form, region, head or branch office. The tariff sheet describes a record as "KVK-nummer en NAW" | K7, K10 | sourced. That the SBI code can be delivered as an extra field per record: my inference from K7 (it is a selection criterion and "extra rubrieken" can be ordered); not stated outright |
| Is the trade name in it? | Yes, the company name is part of the standard record | K7, K10 | sourced |
| Terms that apply | For contracts signed after 1 January 2021: K5 with its annex | K4 | sourced |
| Passing data on | KVK gives no permission for "doorgifte": passing on or making available register data to third parties in a way that does not differ in function from KVK's own supply, whatever the price. KVK's examples include making available one's own collection or database from which third parties can consult register data | K5 annex art. 1 and 3; K6; K4 | sourced |
| Reuse | "Hergebruik" in the sense of the reuse act is allowed if all other conditions are met; KVK's example is combining register data with other data into a product with added value. Placing register data side by side with other data in an app, portal or site is named as not being reuse but passing on | K5 annex art. 4(1); K6 | sourced |
| Serving many customers from one own database | Not allowed without agreement with KVK; the explanation says someone who serves several customers with the same sets of register data may do so only if agreed with KVK, not from an own collection | K6 (on art. 7) | sourced |
| Personal data | Reuse of personal data needs a separate request to KVK. KVK's examples of personal data: KVK numbers, address data and contact data of sole traders, and everything about officers | K5 annex art. 4(2); K6 | sourced |
| Other duties | Data may not be made searchable or sortable by natural person. Products built on register data must state the date the data was obtained and carry a fixed sentence referring to the register. Companies with the non-mailing indicator may not be approached for marketing | K5 annex art. 5(2), 6(1), 6(3); K7 | sourced |
| Sole traders | Included in the register products; the address-file page lets you select on legal form | K7 | sourced that legal form is a criterion; that sole traders are in the address file is my inference |
| Legal footing of the terms | On 22 December 2021 a court ruled, in a case brought by the trade association VVZBI, that KVK may not attach conditions to the use of register data on the basis of a database right. KVK said it would consider next steps. The same terms are still published on a KVK page updated 17 June 2026 | K11, K4 | sourced. Whether there was an appeal and what it decided: could not verify |
| Price | Tariff sheet 2026: address selection has a start cost of 334.00 and a per-record price of 0.05, extra fields 0.04 each; Mutatieservice 1,279.00 a year; Dataservice 1,279.00 once plus a price per query (euro) | K10, K9 | sourced, with a caution: the sheet's columns came out misaligned in text extraction, so the pairing of amounts and labels must be confirmed on the PDF |
| Size | Not stated by KVK. The open data set gives 1.92 million BV and NV registrations; sole traders and other forms come on top | K2 | my inference for scale only; total register size not checked |
| Update frequency and form | Address file: one-off delivery in Excel or CSV within five working days of the signed quote. Mutatieservice: subscription. Dataservice: live connection | K7, K9, K10 | sourced |

What it means for the product: this is the only place where name and SBI sit together officially, and KVK's own terms treat handing that pairing to our customers as something it does not permit by default. A lookup table inside an installer looks closer to KVK's example of "an own database from which third parties consult register data" than to its example of a value-added product (my inference; this is the point a lawyer must judge). At the listed per-record price, 1.9 million records would cost on the order of 96,000 euro before sole traders and before any update (my inference: 1,924,735 times 0.05; whether that rate applies at this volume is not verified).

Verdict: only under contract. Whether KVK would agree to redistribution inside a commercial product at all: could not determine.

### 3.3 CBS SBI code table

| Point | Finding | Source | Mark |
|---|---|---|---|
| Fields | Activity codes with Dutch and English descriptions. No companies | C1, C2 (file name and page description; I did not open the workbook) | sourced for what it is; the exact columns are not checked |
| Is the trade name in it? | No. It is a classification, not a register | C1 | sourced |
| Version | SBI 2025 is being introduced step by step from 2026; SBI 2008 and SBI 2025 are used side by side in that period. CBS publishes conversion tables between the two | C1 | sourced |
| KVK's use | Each registered business gets one or more SBI codes from KVK; KVK's own page links the CBS file "Standaard Bedrijfsindeling 2025 - Nederlands en Engels update 2026" | K13 | sourced. Which version a given KVK record carries today: could not verify |
| Licence | Unless stated otherwise, content of the CBS site is under CC BY 4.0; reuse is allowed if CBS is named as source and no impression is given that CBS endorses the derived work. The SBI page itself carries no separate licence line | C3, C1 | sourced |
| Commercial redistribution | Allowed under CC BY 4.0 with attribution | C3 | sourced; that no exception applies to this particular file is my inference (none is marked on the page) |
| Personal data | None | C1 | my inference from the nature of the table |
| Size | 137,481 bytes (xlsx) | C2 (download size measured) | sourced |
| Update frequency | SBI 2008 had yearly versions; the SBI 2025 file is labelled "versie 2026" | C1 | sourced |
| Delivery form | Public download, xlsx and pdf | C1 | sourced |

What it means for the product: it turns a code into the activity text the model reads. It helps only once a code is known from somewhere else, for example from the customer's own export or typed by the bookkeeper.

Verdict: may ship, with CBS named as source. It is not a name-to-SBI mapping.

### 3.4 Third parties

| Candidate | What it is and what it contains | Licence and terms | Personal data | Source | Verdict |
|---|---|---|---|---|---|
| OpenKvK through overheid.io | An online API over "the dataset of openKvK.nl". Its documentation shows `handelsnaam`, `kvknummer`, `sbi`, activity descriptions, address and `non_mailing_indicatie`. New registrations updated daily, address changes about weekly. It republishes register data; I found no statement of where it obtains it. No bulk download is offered on the page read | Its terms say information from the API may be reused under the Creative Commons Attribution-ShareAlike licence unless the output says otherwise. Share-alike is a copyleft condition on the data, which the no-copyleft decision rules out (my inference). Whether overheid.io can grant that licence over KVK data at all is not established | Yes. The documentation's own example record has legal form code `EMZ` (sole trader) | T1, T2 | may not ship |
| OpenCorporates | Global company database | Free access only for the public for personal use, journalists, NGOs and academics; corporations need a separate paid contract. The page links the ODbL, which is share-alike | Not checked | T3 | only under contract. Whether its Dutch records carry SBI codes: not checked |
| GLEIF LEI data | Legal entities that hold an LEI, with legal name and address | CC0 | Not checked; LEI holders are legal entities | T4, T5 | may ship as far as the licence goes, but not usable: I found no industry, NACE or activity field on the format page (text search of T5), and only entities with an LEI are covered |
| KVK's recognised partners (the KVK page lists, among others, Company.info, Creditsafe, Dun and Bradstreet, Bureau van Dijk, Graydon) | Commercial providers that deliver register data under an agreement with KVK | Each has its own contract; KVK says its agreement with partners contains general terms, including protection of the privacy of those registered. I did not read any partner's terms | Not checked | K12 | only under contract; not checked one by one |

Where a third party merely republishes KVK data: OpenKvK says so itself (T1). The recognised partners deliver data that KVK says comes straight from the register (K12). For OpenCorporates I did not check the origin of its Dutch records.

## 4. Sole traders and personal data

| Who says it | What | Source | Mark |
|---|---|---|---|
| KVK, about its open data | The company name, the KVK number and the business address cannot in every case be ruled out as personal data; KVK cannot assess this per case and so does not release them as open data | K1 | sourced |
| KVK, in its terms | Reuse of personal data needs a separate request; examples of personal data are KVK numbers, address and contact data of sole traders, and all data about officers | K5 annex art. 4(2) | sourced |
| KVK, in its terms | Register data may not be made searchable or sortable by natural person for third parties | K5 annex art. 6(1) | sourced |
| Dutch data protection authority (AP), 10 August 2022 | On the bill changing the reuse act, the AP advised writing into law that reuse of personal data from public registers is prohibited in principle, with exceptions set by rule. It names the Handelsregister and the Kadaster, and warns of data trading by combining register data with other sources | A1 | sourced. What became of that advice in the law as it stands today: could not verify |
| This report | A sole trader's trade name is often the person's own name, so a table of trade names with activity codes that includes sole traders is a table of people and what they do for a living. Shipping it to every customer's laptop would make us a controller distributing personal data with no way to correct or withdraw a record | none | my inference; needs a privacy lawyer |

I did not find an AP statement that addresses a vendor-lookup table of this kind directly.

## 5. Verdicts

| Candidate | Trade name in it? | Verdict | Source |
|---|---|---|---|
| KVK Open Dataset Basis Bedrijfsgegevens | No (anonymised; BV and NV only) | may ship under CC BY 4.0, but it holds no name-to-SBI mapping, so not usable for this | K1, K2 |
| KVK paid products (address selection, file comparison, Mutatieservice, Dataservice) | Yes | only under contract; whether KVK would allow redistribution in an installer: could not determine | K4, K5, K6, K7, K10 |
| CBS SBI code table | No (codes and descriptions) | may ship with attribution; useful as code-to-text, not as a lookup by name | C1, C2, C3 |
| OpenKvK through overheid.io | Yes | may not ship (share-alike terms, sole traders included, online API only, licence chain to KVK unproven) | T1, T2 |
| OpenCorporates | Yes (company names); SBI not checked | only under contract | T3 |
| GLEIF LEI data | Yes (legal names) | may ship as far as CC0 goes; no activity code found, so not usable | T4, T5 |
| KVK recognised partners | Presumably; not checked | only under contract; not checked one by one | K12 |

Overall: no usable source exists today that a closed-source product may ship without a contract. The request said that is a valid answer.

## 6. What needs a professional's or KVK's confirmation

1. Whether shipping a name-to-SBI table inside an installer is "doorgifte" or "hergebruik" under KVK's terms. Only KVK can say; a written question to KVK is the cheapest check.
2. Whether those terms bind us at all after the December 2021 judgment, and what happened on appeal. A lawyer, with the judgment itself (I read only KVK's press release).
3. Whether a table that includes sole traders can be distributed lawfully under the GDPR, and whether leaving out sole traders (BV and NV only) removes the problem. A privacy lawyer. KVK's own position is that even a BV's name cannot always be treated as non-personal (K1).
4. The exact attribution wording for the CBS table, and that no exception applies to that file.

## 7. What this means for the product

- One line: the activity field stays empty or export-learned, as already ruled; nothing found here changes that.
- Do we meet it today: the ruling says the field is empty or export-learned. I did not open the `vaultledger-ml` code for this request: not checked.
- If the customer's own export carries KVK numbers or SBI codes for its vendors, the CBS table alone is enough to give the model the activity text, with nothing leaving the device and no register data shipped by us (my inference). Whether Dutch bookkeeping exports carry either field is not checked.
- A route not asked about, noted only so it is not lost: a short hand-made list of large, well-known suppliers (legal entities only) with an activity code assigned by us from the CBS descriptions would contain no register data. It would be our own classification, not KVK's, and could not be called an SBI registration (my inference; not researched).

## 8. Self-check

- First line is "Background read:". Done.
- Every table row carries a source or is marked "none" with "my inference". Done.
- Not read or not checked, and said so where it matters: KVK's "leveringsvoorwaarden" for the open data set; the pre-2021 product terms (Dataservice, Informatie op maat); the VVZBI judgment itself and any appeal; the AP's full advice documents; the columns inside the CBS workbook; any partner's contract; the total number of registrations in the Handelsregister.
- Files downloaded for inspection are outside the repository under `C:\Users\ilhan\.claude\jobs\d0396725\tmp\kvk-download\` and were read as data only.
