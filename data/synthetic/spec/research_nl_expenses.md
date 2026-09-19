# Research input: NL SME/ZZP expense realism (for synth-spec-architect)

Web-search summaries only, not full page reads. **S** = sourced, **A** = assumption.
Verify against a few real documents before treating any A as fact.

## Class mix by transaction count, freelancer (all A -- no authoritative split found)
Software & Subscriptions 25-30%, Travel & Transport 20-25%, Office Supplies 12-15%,
Utilities 10-12%, Professional Services 8-10%, Rent 5-8% (few but large),
General/Other 8-12%. By EUR value, Rent and Professional Services dominate.

## Amounts (EUR)
- S: Google Workspace Starter 6.90 / Standard 13.80 per user per month
  (medhacloud.com). Microsoft 365 Business Standard from ~10.93 (m365.de; unverified
  ex-VAT). Accountant for ZZP 600-2,500/yr, typically 700-2,000 (qonto.com). KvK
  registration 85.15 one-off (zzp-kompas.nl).
- A: SaaS is point masses (5-15, 20-60, 100+) times seats. Rent near-constant
  (flexdesk 150-400, office 500-1,500). Energy 60-250/mo lognormal with winter uplift;
  telecom 10-80 near-fixed. Office supplies lognormal, median ~30, tail 500+.
  Travel: NS 5-40, OV tap 2-30, fuel 40-100, parking 2-25, OV subscription 100-400.
  Professional: notaris 300-1,500 heavy tail, consultant 200-5,000 lognormal (sigma ~1),
  round-number bias for fees. Discretionary spend lognormal; subscriptions/rent/telecom
  fixed.

## Wording
- S (Belastingdienst): invoice fields are factuurnummer, factuurdatum, delivery date,
  nature of services, price ex BTW, BTW rate, BTW amount. Terms 14 or 30 days.
  Bank channels: "SEPA Incasso", "SEPA Overboeking", "Betaalautomaat".
- A: invoice numbers "2026-0142", "INV-2026-00123", "F2026/0087". Periods "Periode
  01-08-2026 t/m 31-08-2026", "Q3 2026", "Aug 2026". NL: Factuur, Totaal excl. BTW,
  BTW 21%, Te betalen voor, Reeds voldaan. EN: Invoice, Subtotal, VAT (21%), Total due.
  BTW verlegd / reverse charge for EU suppliers (Google/Microsoft/Adobe Ireland). Bank
  lines: "SEPA Incasso algemeen doorlopend ... Omschrijving: Factuur 2026-0142",
  "BEA NR:xxxx Q-PARK AMSTERDAM", "iDEAL ... bol.com".
- A vendors: Energy Eneco/Vattenfall/Essent/Greenchoice, water Vitens/Dunea, grid
  Stedin/Liander. Telecom KPN/Odido/Vodafone/Ziggo. Office Staples/Bol.com/Amazon.nl/
  Action/Coolblue/Viking. Software Microsoft/Google/Adobe/Slack/Zoom/Dropbox/Notion/
  GitHub/Moneybird/Exact. Travel NS/GVB/RET/HTM/Shell/BP/Tango/Q-Park/Parkmobile/
  EasyPark/Uber/Swapfiets. Professional notaris, accountantskantoor, KvK.

## Ambiguous vendors (hard-case test set; treatment is A unless noted)
- S: Bol.com is a marketplace; the invoice comes from the seller (bol.com help pages).
- Bol/Amazon/Coolblue/Action: Office Supplies if stationery/ink/small hardware,
  Software if licenses, else General/Other and **escalate**.
- Albert Heijn/HEMA: groceries mostly General/Other or private; HEMA can be office.
- Google Workspace = Software; Google Ads = no account, so General/Other; AWS/Azure/
  Cloud = Software. Shell/Tango: fuel = Travel, shop items ambiguous.

## Recurrence and payment
- S: BTW deadlines 2026: Q1 30 Apr, Q2 31 Jul, Q3 31 Oct, Q4 31 Jan 2027 (kvk.nl).
  KOR exempts up to EUR 20,000 turnover.
- A: rent monthly on the 1st; energy monthly incasso with an annual settlement that can
  be a credit; telecom monthly; SaaS monthly/annual on a fixed day-of-month; domains/
  insurance/KvK annual. Paid share: subscriptions/utilities/rent/receipts 90-100% paid
  at document date; professional B2B invoices 40-60% unpaid at receipt, terms 14 vs 30
  days about 30/70, overdue tail 5-10%.
