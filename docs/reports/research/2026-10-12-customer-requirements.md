# Customer requirements: a startup in the Netherlands

Research crew, customer scout. Written 2026-10-12. All sources were read on
2026-10-12. Code checked on branch `demo-mode`.

I am not a lawyer or a tax adviser. This report summarises what official
pages say and what I conclude from them. Every item marked "confirm" needs a
Dutch accountant or tax adviser before we state it to a customer.

`sourced` means the linked page says it. `my inference` means I concluded it.

## Summary

The product today records five fields and one expense account per document
and exports two CSV files. That is enough for a spend overview. It is not
enough for a Dutch VAT return, a Dutch audit file, or the seven-year
retention duty, because the tool stores no VAT data, no supplier VAT number,
no invoice number and no copy of the document.

One planning decision needs correcting. `docs/planning/vaultledger-action-list.md`
says XAF 4.0 is "mandatory as of Jan 1, 2026". The Belastingdienst developer
portal says older XAF versions are phased out per 1 January 2027. I found no
official page saying a small company must produce an audit file at all, so
the legal status is unverified (confirm).

## Requirement table

Sources:
[S1] https://business.gov.nl/regulations/keeping-business-records/
[S2] https://business.gov.nl/regulations/invoice-requirements/
[S3] https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/zakelijk/btw/administratie_bijhouden/facturen_maken/factuureisen/factuureisen
[S4] https://business.gov.nl/finance-and-taxes/vat/vat-rates-and-exemptions/
[S5] https://www.belastingdienst.nl/wps/wcm/connect/bldcontenten/belastingdienst/business/vat/vat_in_the_netherlands/calculating_vat/reverse-charging_vat
[S6] https://odb.belastingdienst.nl/auditfiles/
[S7] https://odb.belastingdienst.nl/auditfiles/achtergrond-informatie-xaf4-0/
[S8] https://kpmg.com/us/en/taxnewsflash/news/2026/09/netherlands-mandatory-e-invoicing-digital-reporting-proposed-b2b-transactions.html (adviser summary, not the government letter itself)
[S9] https://autoriteitpersoonsgegevens.nl/nl/onderwerpen/algemene-informatie-avg/verwerkers
[S10] https://www.belastingdienst.nl/wps/wcm/connect/nl/btw/content/wijziging-aangiftetijdvak-btw
[S11] https://support.exact.com/portal/s/article/NL-AGSG-HNO-Video-ag-rg-agj-cijferimportmbvauditfilev?language=en_GB

| # | Level | Rule or need | Set by | Source | Meaning for us | Met today? |
|---|---|---|---|---|---|---|
| 1 | Must | Keep business records at least 7 years (10 for immovable property): general ledger, purchase and sales records, debtors and creditors | Tax Administration | [S1] sourced | Ledger and source documents must survive 7 years and a machine change | Partly. Ledger is an append-only CSV with zip backup and restore (`ledger.py`, `backup.py`). No retention feature, and no document copy |
| 2 | Must | Invoices are kept in the form received; a scan must hold the same information as the original; digital files must be readable on inspection | Tax Administration | [S1] [S2] sourced | We must keep the original file, or state clearly that the customer keeps it elsewhere | No. `webapp/app.py` `api_process` saves the upload to a temp file and deletes it after the pipeline runs; only the filename reaches `ledger.csv` |
| 3 | Must | Replacing paper originals with scans needs contact with the tax office | Tax Administration | [S1] sourced; exact conditions not verified | Do not tell a customer they can throw paper away (confirm) | Not applicable yet |
| 4 | Must | A valid invoice carries supplier VAT number, KVK number, invoice date, sequential invoice number, description, delivery date, amount excluding VAT, VAT rate, VAT amount | Tax Administration | [S3] sourced | To support input-VAT deduction we must capture these per document | No. `ExtractedFields` has vendor, description, date, amount, paid only |
| 5 | Must | VAT rates are 0%, 9% and 21%; amounts are shown per rate | Tax Administration | [S4] [S3] sourced | Need net, VAT and gross per rate, and a VAT code per line | No. One gross amount; no VAT account in `coa.py` |
| 6 | Must | Reverse charge: invoice shows no VAT and says "VAT reverse-charged"; buyer's VAT number is on it | Tax Administration | [S5] [S2] sourced. What the buyer reports in the return: not verified | Detect the reverse-charge wording and flag the entry | No |
| 7 | Must | VAT return is usually quarterly, filed digitally, due about one month after the quarter | Tax Administration | [S10] sourced | Periods must follow the invoice date and quarters | No. `reports.py` groups by `confirmed_at` calendar month, not document date |
| 8 | Must | Amounts in euro with Dutch formats | Customer | my inference | Euro sign, `1.234,56`, `dd-mm-yyyy` | No. `static/shared.js` prints `"$"`; parser test: `1.234,56` parsed as `1.23`, `25,00` and `12-10-2026` not matched (branch `extraction-locale` may address this; not checked) |
| 9 | Expected | Audit file XAF: only version 4.0 accepted from 1 January 2027; older versions phased out; RGS is defined more clearly in 4.0 | Tax Administration (ODB) | [S6] [S7] sourced. Whether a small company is obliged to supply one: not verified | Plan XAF 4.0, not 3.2. Corrects the action list date | No. CSV only |
| 10 | Expected | Accountant's package takes the books in: Exact accepts an XAF file or RGS-based import for a trial balance | Vendor | [S11] sourced for Exact only. Moneybird, Twinfield, e-Boekhouden: not verified | Export needs account codes, VAT code, journal and both sides of the entry | No. `books_csv` has Date, Vendor, Description, Amount, Account name; no account number, credit side or paid flag. `ledger.csv` does not store the credit account |
| 11 | Expected | Chart of accounts with numeric codes mapped to RGS | Sector standard | [S7] sourced that RGS is in XAF 4.0; mapping need is my inference | Add code and RGS reference per account | No. Names only; `generic-eu` template is not Dutch |
| 12 | Expected | Record of who posted or corrected what, and when | Accountant | my inference | Keep the audit CSV; add user and immutability | Partly. `audit_csv` has timestamp, confidence, corrected flag; no user, plain editable file |
| 13 | Expected | A supplier that processes personal data for the customer needs a processing agreement and appropriate security | Dutch Data Protection Authority | [S9] sourced | On-device with no vendor access probably avoids a processor role (my inference, confirm) | Design helps. README states no encryption at rest, no 2FA |
| 14 | Nice to have | E-invoicing: government position of 11 September 2026 is EN 16931 e-invoices for domestic B2B from 1 July 2030, reporting from 1 July 2031; not yet law | Dutch government | [S8] sourced, secondary | Later, read structured invoices directly; no OCR needed for those | No. Not needed for a first customer |
| 15 | Nice to have | Do not keep personal data beyond the retention period without a reason | GDPR, per [S2] | sourced | Offer deletion after 7 years | No |

## Workflow

I found no official source on how a Dutch founder and bookkeeper split the
work. The only sourced anchor is the quarterly VAT rhythm [S10]. My
inference: the founder collects documents through the quarter, the
bookkeeper codes them and files the return in the month after, and the
accountant does year-end. This should be asked in the customer meeting, not
assumed.

## The five gaps that matter most for a first customer

1. No VAT capture. Without net, VAT amount, rate, supplier VAT number and
   invoice number per document, the output cannot support a VAT return, which
   is the bookkeeper's main recurring task (rows 4 to 6).
2. Documents are not kept. The upload is deleted after processing, so the
   ledger row cannot be traced to its source and the customer must run a
   second archive to meet the retention duty (rows 1 and 2).
3. Dutch money and dates. The `$` sign is visible in a demo, and the parser
   misreads `1.234,56` as `1.23`, which is a wrong amount in the books
   (row 8).
4. The export is not importable. No account codes, no credit side, no VAT
   code, no RGS, no XAF. An accountant would retype it (rows 9 to 11).
5. Periods use the confirmation date. A December invoice confirmed in
   January lands in the wrong month and quarter (row 7).

## Not verified

- Whether a small company must be able to supply an XAF file, or only on
  request during an audit.
- The exact conditions for replacing paper with scans.
- Import formats of Moneybird, Twinfield and e-Boekhouden.
- The buyer's VAT-return treatment of reverse-charged purchases.
- The government's letter of 11 September 2026 itself; I read an adviser's
  summary.
- The two belastingdienst.nl retention pages I tried returned 404; retention
  facts come from business.gov.nl, the government's business portal.
- No library or model is recommended in this report, so no licence is listed.
