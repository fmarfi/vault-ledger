"""Add real e-invoice line items to corpus/descriptions.json (family "einvoice").

    .venv/Scripts/python -I data/synthetic/spec/build_einvoice_lines.py

Source: the public e-invoice examples under data/external/documents/{peppol_bis3, nlcius_si_ubl,
en16931_validation, xrechnung_testsuite, zugferd_corpus}. Only the line-item texts (UBL Item/Name and
Description, CII SpecifiedTradeProduct/Name and Description) are used; seller names are not taken.
Each usable line is labelled by hand below with an account and a VAT rate. Dutch and English lines are
kept as written; German and Swedish lines are translated faithfully (marked "translated") because the
product reads Dutch and English. Placeholder lines ("article 4", "Produkt 1") and lines whose account
is unclear (construction, medical, "Service fee") are left out.
Invoices whose usable lines share one account also give a joined description, the way the product's
e-invoice reader shows them: "line 1; line 2; line 3 (+N more)".
Idempotent: the "einvoice" family is replaced on each run.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from defusedxml import ElementTree as SafeET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCS = ROOT / "data" / "external" / "documents"
SOURCES = ["peppol_bis3", "nlcius_si_ubl", "en16931_validation", "xrechnung_testsuite", "zugferd_corpus"]
OUT = HERE / "corpus" / "descriptions.json"
FAMILY = "einvoice"
sys.path.insert(0, str(HERE))
from build_corpus import keyword_free  # noqa: E402

RE_ = "Rent Expense"
UT = "Utilities Expense"
SW = "Software & Subscriptions Expense"
TR = "Travel & Transport Expense"
OF = "Office Supplies Expense"
PS = "Professional Services Expense"
GO = "General/Other Expense"

# original line text -> (account, vat_rate, [(text, language), ...]); first entry with the source's own
# language when it is Dutch or English, otherwise translations only
L = {
    # office supplies and equipment
    "Laptop computer": (OF, "0.21", [("Laptop computer", "en"), ("Laptop", "nl")]),
    "Processor: Intel Core 2 Duo SU9400 LV (1.4GHz). RAM: 3MB. Screen 1440x900":
        (OF, "0.21", [("Processor: Intel Core 2 Duo SU9400 LV (1.4GHz). RAM: 3MB. Screen 1440x900", "en")]),
    "Network cable": (OF, "0.21", [("Network cable", "en"), ("Netwerkkabel", "nl")]),
    "Printing paper": (OF, "0.21", [("Printing paper", "en"), ("Printpapier", "nl")]),
    "Printing paper, 2mm": (OF, "0.21", [("Printing paper, 2mm", "en")]),
    "Parker Pen": (OF, "0.21", [("Parker Pen", "en")]),
    "Parker Pen, Black, model Sansa": (OF, "0.21", [("Parker Pen, Black, model Sansa", "en"),
                                                    ("Parker pen, zwart, model Sansa", "nl")]),
    "BLOCKNOTE A5": (OF, "0.21", [("BLOCKNOTE A5", "nl")]),
    "BALPENNEN 50 ST BLAUW": (OF, "0.21", [("BALPENNEN 50 ST BLAUW", "nl")]),
    "Trennblätter A4": (OF, "0.21", [("Tabbladen A4", "nl"), ("Divider sheets A4", "en")]),
    "Drehstuhl": (OF, "0.21", [("Draaistoel", "nl"), ("Swivel chair", "en")]),
    "Keyboard/Maus - weiß": (OF, "0.21", [("Keyboard/muis - wit", "nl"), ("Keyboard/mouse - white", "en")]),
    "MX Master": (OF, "0.21", [("MX Master", "en")]),
    "Tastatur Deutsch": (OF, "0.21", [("Toetsenbord Duits", "nl"), ("Keyboard German layout", "en")]),
    "Beamer-Deckenhalterung": (OF, "0.21", [("Beamer plafondbeugel", "nl"), ("Projector ceiling mount", "en")]),
    "Huawei E5573 Mobiler 4G Hotspot sw": (OF, "0.21", [("Huawei E5573 mobiele 4G hotspot zw", "nl"),
                                                        ("Huawei E5573 mobile 4G hotspot blk", "en")]),
    "Mobile model A": (OF, "0.21", [("Mobile model A", "en")]),
    "Mobile model B": (OF, "0.21", [("Mobile model B", "en")]),
    "Protection cover (plastic)": (OF, "0.21", [("Protection cover (plastic)", "en")]),
    "Protection cover, plastic": (OF, "0.21", [("Protection cover, plastic", "en"), ("Beschermhoes, kunststof", "nl")]),
    "UIT Desktop m/59, 2-160 GB": (OF, "0.21", [("UIT Desktop m/59, 2-160 GB", "en")]),
    "LCD Display 3.5": (OF, "0.21", [("LCD Display 3.5", "en")]),
    # general / other: food, drinks, cleaning, shipping, insurance, waste, repairs
    "American Cookies": (GO, "0.09", [("American Cookies", "en")]),
    "PATAT FRITES 10MM 10KG": (GO, "0.09", [("PATAT FRITES 10MM 10KG", "nl")]),
    "POT KETCHUP 3 LT": (GO, "0.09", [("POT KETCHUP 3 LT", "nl")]),
    "FRITESSAUS 3 LRR": (GO, "0.09", [("FRITESSAUS 3 LRR", "nl")]),
    "KOFFIE BLIK 3,5KG SNELF": (GO, "0.09", [("KOFFIE BLIK 3,5KG SNELF", "nl")]),
    "KOFFIE 3.5 KG BLIK STAND": (GO, "0.09", [("KOFFIE 3.5 KG BLIK STAND", "nl")]),
    "SUIKERKLONT": (GO, "0.09", [("SUIKERKLONT", "nl")]),
    "1 KG UL BLOKJES": (GO, "0.09", [("1 KG UL BLOKJES", "nl")]),
    "CHIPS NAT KLEIN ZAKJES": (GO, "0.09", [("CHIPS NAT KLEIN ZAKJES", "nl")]),
    "CHIPS PAP KLEINE ZAKJES": (GO, "0.09", [("CHIPS PAP KLEINE ZAKJES", "nl")]),
    "TR KL PAKJES APPELSAP": (GO, "0.09", [("TR KL PAKJES APPELSAP", "nl")]),
    "KRAT BIER": (GO, "0.21", [("KRAT BIER", "nl")]),
    "STATIEGELD": (GO, "0", [("STATIEGELD", "nl")]),
    "BLEEK 3 X 750 ML": (GO, "0.21", [("BLEEK 3 X 750 ML", "nl")]),
    "WC PAPIER": (GO, "0.21", [("WC PAPIER", "nl")]),
    "KAAS 50PL. JONG BEL. 1KG": (GO, "0.09", [("KAAS 50PL. JONG BEL. 1KG", "nl")]),
    "PKAAS 50PL. JONG BEL. 1KG": (GO, "0.09", [("PKAAS 50PL. JONG BEL. 1KG", "nl")]),
    "PK CHOCOLADEMELK": (GO, "0.09", [("PK CHOCOLADEMELK", "nl")]),
    "PK CHOCOLADEMEL": (GO, "0.09", [("PK CHOCOLADEMEL", "nl")]),
    "EM FRITUURVET": (GO, "0.09", [("EM FRITUURVET", "nl")]),
    "FRITUUR VET 10 KG RETOUR": (GO, "0.09", [("FRITUUR VET 10 KG RETOUR", "nl")]),
    "Joghurt Banane": (GO, "0.09", [("Yoghurt banaan", "nl")]),
    "Mineralwasser Medium 12 x 1,0l PET": (GO, "0.09", [("Mineraalwater medium 12 x 1,0l PET", "nl"),
                                                        ("Mineral water medium 12 x 1.0l PET", "en")]),
    "Pfand": (GO, "0", [("Statiegeld", "nl"), ("Deposit", "en")]),
    "Food (VAT 12%)": (GO, "0.09", [("Food (VAT 12%)", "en")]),
    "Ballons": (GO, "0.21", [("Ballonnen", "nl"), ("Balloons", "en")]),
    "Porto + Versandkosten": (GO, "0.21", [("Porto + verzendkosten", "nl"), ("Postage + shipping", "en")]),
    "Versandkosten": (GO, "0.21", [("Verzendkosten", "nl"), ("Shipping costs", "en")]),
    "Lieferkosten": (GO, "0.21", [("Bezorgkosten", "nl"), ("Delivery charge", "en")]),
    "Entsorgung": (GO, "0.21", [("Afvoer afval", "nl"), ("Waste disposal", "en")]),
    "Behältermiete": (GO, "0.21", [("Containerhuur", "nl"), ("Container hire", "en")]),
    "Tür Instandsetzung": (GO, "0.21", [("Deur herstellen", "nl"), ("Door repair", "en")]),
    "Verbundene Wohngebäudeversicherung": (GO, "0", [("Opstalverzekering", "nl"), ("Buildings insurance", "en")]),
    "Underhållsförsäkring": (GO, "0", [("Onderhoudsverzekering", "nl"), ("Maintenance insurance", "en")]),
    "Newspaper (VAT 6%)": (SW, "0.09", [("Newspaper (VAT 6%)", "en")]),
    # subscriptions and software
    "Paper subscription": (SW, "0.09", [("Paper subscription", "en")]),
    "Subscription fee 1st quarter": (SW, "0.21", [("Subscription fee 1st quarter", "en")]),
    "Zeitschrift Inland": (SW, "0.09", [("Tijdschrift binnenland", "nl"), ("Magazine domestic", "en")]),
    "Heft 13 2016 bis 24 2016": (SW, "0.09", [("Nummer 13 {year} t/m 24 {year}", "nl"), ("Issue 13 {year} to 24 {year}", "en")]),
    "IExpress licentiekosten": (SW, "0.21", [("IExpress licentiekosten", "nl")]),
    "Killer antivirusprogram": (SW, "0.21", [("Killer antivirus program", "en")]),
    "Abonnemang, förlängning": (SW, "0.21", [("Abonnement, verlenging", "nl"), ("Subscription, renewal", "en")]),
    # utilities: energy, grid, water, telecom
    "Arbeitspreis Gas": (UT, "0.21", [("Leveringstarief gas", "nl"), ("Gas unit rate", "en")]),
    "Grundpreis Gas": (UT, "0.21", [("Vaste leveringskosten gas", "nl"), ("Gas standing charge", "en")]),
    "Arbeitspreis Strom": (UT, "0.21", [("Leveringstarief stroom", "nl"), ("Electricity unit rate", "en")]),
    "Grundpreis Strom": (UT, "0.21", [("Vaste leveringskosten stroom", "nl"), ("Electricity standing charge", "en")]),
    "Arbeitspreis Wasser": (UT, "0.09", [("Verbruik water", "nl"), ("Water usage", "en")]),
    "Grundpreis Wasser": (UT, "0.09", [("Vastrecht water", "nl"), ("Water standing charge", "en")]),
    "Getransporteerde kWh’s": (UT, "0.21", [("Getransporteerde kWh’s", "nl")]),
    "Getransporteerde kWh's": (UT, "0.21", [("Getransporteerde kWh's", "nl")]),
    "Systeemdiensten": (UT, "0.21", [("Systeemdiensten", "nl")]),
    "Contract transportvermogen": (UT, "0.21", [("Contract transportvermogen", "nl")]),
    "Maximaal afgenomen vermogen": (UT, "0.21", [("Maximaal afgenomen vermogen", "nl")]),
    "Vastrecht Transportdienst": (UT, "0.21", [("Vastrecht Transportdienst", "nl")]),
    "Vastrecht Aansluitdienst": (UT, "0.21", [("Vastrecht Aansluitdienst", "nl")]),
    "Huur Transformatoren": (UT, "0.21", [("Huur Transformatoren", "nl")]),
    "Huur Schakelinstallaties": (UT, "0.21", [("Huur Schakelinstallaties", "nl")]),
    "Huur Overige Apparaten": (UT, "0.21", [("Huur Overige Apparaten", "nl")]),
    "Huur Meterdiensten": (UT, "0.21", [("Huur Meterdiensten", "nl")]),
    "Abschlag Monat": (UT, "0.21", [("Termijnbedrag {maand}", "nl"), ("Monthly instalment {month}", "en")]),
    "Energiepreis": (UT, "0.21", [("Energieprijs", "nl"), ("Energy price", "en")]),
    "Arbeitspreis Netznutzung": (UT, "0.21", [("Transporttarief netgebruik", "nl"), ("Network usage rate", "en")]),
    "Messstellenbetrieb Netz": (UT, "0.21", [("Meterhuur net", "nl"), ("Metering point operation", "en")]),
    "Energiesteuer": (UT, "0.21", [("Energiebelasting", "nl"), ("Energy tax", "en")]),
    "Messpreis": (UT, "0.21", [("Meettarief", "nl"), ("Metering charge", "en")]),
    "Grundpreis Netz": (UT, "0.21", [("Vastrecht netbeheer", "nl"), ("Network standing charge", "en")]),
    "Fast elpris, bundet 1 år": (UT, "0.21", [("Vaste stroomprijs, 1 jaar vast", "nl"), ("Fixed electricity price, 1-year term", "en")]),
    "El-förbrukning": (UT, "0.21", [("Stroomverbruik", "nl"), ("Electricity consumption", "en")]),
    "Elöverföring, tariff 4b": (UT, "0.21", [("Transport elektriciteit, tarief 4b", "nl"), ("Power transmission, tariff 4b", "en")]),
    "Energiskatt": (UT, "0.21", [("Energiebelasting", "nl"), ("Energy tax", "en")]),
    "Eergiskatt": (UT, "0.21", [("Energy tax", "en")]),
    "Samtal i Sverige: fasta nätet, öppn.avg": (UT, "0.21", [("Gesprekken NL: vast net, starttarief", "nl"), ("Calls domestic: landline, connection fee", "en")]),
    "Samtal i Sverige: fasta nätet, tid": (UT, "0.21", [("Gesprekken NL: vast net, minuten", "nl"), ("Calls domestic: landline, time", "en")]),
    "Samtal i Sverige: vårt mobilnät, öppn.avg": (UT, "0.21", [("Gesprekken NL: eigen mobiel net, starttarief", "nl")]),
    "Samtal i Sverige: vårt mobilnät, tid": (UT, "0.21", [("Calls domestic: own mobile network, time", "en")]),
    "Samtal i Sverige: andra mobilop., öppn.avg": (UT, "0.21", [("Calls domestic: other mobile op., connection fee", "en")]),
    "Samtal i Sverige: andra mobilop., tid": (UT, "0.21", [("Gesprekken NL: andere mobiele op., minuten", "nl")]),
    "Datatrafik: Internet/WAP": (UT, "0.21", [("Dataverkeer: internet/WAP", "nl"), ("Data traffic: Internet/WAP", "en")]),
    "Mobile4U, UK: Utgående samtal, tid": (UT, "0.21", [("Roaming UK: uitgaande gesprekken, minuten", "nl"), ("Roaming UK: outgoing calls, time", "en")]),
    "Mobile4U, UK: Utgående SMS": (UT, "0.21", [("Roaming UK: uitgaande sms", "nl"), ("Roaming UK: outgoing SMS", "en")]),
    "Fast månadsavgift": (UT, "0.21", [("Vast maandbedrag", "nl"), ("Fixed monthly fee", "en")]),
    "Rörlig avgift": (UT, "0.21", [("Variabele kosten", "nl"), ("Variable charge", "en")]),
    # travel and transport: hotel, taxi, flights, car rental, fuel, vehicle tax, public transport
    "Übernachtung. 2 Nächte Hotel": (TR, "0.09", [("Overnachting. 2 nachten hotel", "nl"), ("Accommodation. 2 nights hotel", "en")]),
    "Verpflegung Frühstück": (TR, "0.09", [("Verzorging ontbijt", "nl"), ("Meals breakfast", "en")]),
    "Fahrtkosten, Taxi Berlin": (TR, "0.09", [("Reiskosten, taxi Berlijn", "nl"), ("Travel costs, taxi Berlin", "en")]),
    "Fahrtkosten, Taxi Nürnberg": (TR, "0.09", [("Reiskosten, taxi Neurenberg", "nl"), ("Travel costs, taxi Nuremberg", "en")]),
    "Reisekostenpauschale": (TR, "0", [("Reiskosten forfaitair", "nl"), ("Travel expenses, flat rate", "en")]),
    "Flugschein": (TR, "0", [("Vliegticket", "nl"), ("Flight ticket", "en")]),
    "Flug Storno Inland": (TR, "0", [("Annulering binnenlandse vlucht", "nl"), ("Domestic flight cancellation", "en")]),
    "Flygbiljett": (TR, "0", [("Ticket", "en")]),
    "Arvode flygbokning": (TR, "0.21", [("Boekingskosten vlucht", "nl"), ("Flight booking fee", "en")]),
    "Stockholm - Lillby": (TR, "0", [("Stockholm - Lillby", "en")]),
    "Högtrafik": (TR, "0.09", [("Spitstarief", "nl"), ("Peak fare", "en")]),
    "Nattaxa": (TR, "0.09", [("Nachttarief", "nl"), ("Night fare", "en")]),
    "4-Fahrten-Karte Berlin AB": (TR, "0.09", [("4-rittenkaart Berlijn AB", "nl"), ("4-trip ticket Berlin AB", "en")]),
    "Gültig ab 20.09.2018 15:39 Uhr bis 20.09.2018 17:39 Uhr Abschnitt: 1/4":
        (TR, "0.09", [("Geldig van {date} 15:39 tot {date} 17:39 deel: 1/4", "nl"),
                      ("Valid from {date} 15:39 until {date} 17:39 section: 1/4", "en")]),
    "Miettage": (TR, "0.21", [("Huurdagen", "nl"), ("Rental days", "en")]),
    "Vollkasko": (TR, "0.21", [("Allrisk dekking", "nl"), ("Collision damage cover", "en")]),
    "minimale Selbstbeteiligung": (TR, "0.21", [("Minimaal eigen risico", "nl"), ("Minimum excess", "en")]),
    "Navigationssystem - Garantie": (TR, "0.21", [("Navigatiesysteem - garantie", "nl"), ("Sat nav - guarantee", "en")]),
    "Personen-Unfallversicherung": (TR, "0.21", [("Inzittendenverzekering", "nl"), ("Personal accident insurance", "en")]),
    "Choice Upgrade": (TR, "0.21", [("Choice Upgrade", "en")]),
    "Fahrzeug AB der Klasse C": (TR, "0.21", [("Voertuig AB klasse C", "nl"), ("Vehicle AB class C", "en")]),
    "Bilkategori D, obegränsad körsträcka dag 1.": (TR, "0.21", [("Autocategorie D, onbeperkt aantal km dag 1.", "nl"), ("Car category D, unlimited mileage day 1.", "en")]),
    "Hyrestid i dagar": (TR, "0.21", [("Huurperiode in dagen", "nl"), ("Rental period in days", "en")]),
    "Återlämning Arlanda": (TR, "0.21", [("Inleveren Schiphol", "nl"), ("Return Arlanda", "en")]),
    "Annan återlämningsort": (TR, "0.21", [("Andere inleverlocatie", "nl"), ("One-way drop-off", "en")]),
    "Självriskreducering cdr": (TR, "0.21", [("Verlaging eigen risico CDW", "nl"), ("Excess reduction CDW", "en")]),
    "Bilstöldsförsäkring tp": (TR, "0.21", [("Diefstaldekking TP", "nl"), ("Theft protection TP", "en")]),
    "Drivmedel": (TR, "0.21", [("Brandstof", "nl"), ("Fuel", "en")]),
    "DIZEL": (TR, "0.21", [("DIESEL", "nl")]),
    "Petrol (VAT 25%)": (TR, "0.21", [("Petrol (VAT 25%)", "en")]),
    "Road tax": (TR, "0", [("Road tax", "en"), ("Motorrijtuigenbelasting", "nl")]),
    "Weight-based tax, vehicles >3000 KGM": (TR, "0", [("Weight-based tax, vehicles >3000 KGM", "en")]),
    # professional services: consulting, specification and development work, training
    "Beratung": (PS, "0.21", [("Advies", "nl"), ("Consulting", "en")]),
    "Anforderungsmanagement": (PS, "0.21", [("Requirements management", "en"), ("Requirementsmanagement", "nl")]),
    "Anforderungmanagement": (PS, "0.21", [("Requirements management", "en")]),
    "Anforderungmanagament": (PS, "0.21", [("Requirementsmanagement", "nl")]),
    "Anforderungsaufnahme": (PS, "0.21", [("Inventarisatie eisen", "nl"), ("Requirements gathering", "en")]),
    "Erstellung Lastenheft bis Abnahme": (PS, "0.21", [("Opstellen programma van eisen tot acceptatie", "nl"), ("Drafting requirements spec until sign-off", "en")]),
    "Lastenheft": (PS, "0.21", [("Programma van eisen", "nl"), ("Requirements specification", "en")]),
    "Erstellung Pflichtenheft bis Abnahme": (PS, "0.21", [("Opstellen functioneel ontwerp tot acceptatie", "nl"), ("Drafting functional spec until sign-off", "en")]),
    "Pflichtenheft": (PS, "0.21", [("Functioneel ontwerp", "nl"), ("Functional specification", "en")]),
    "Entwicklung System bis Implementierung": (PS, "0.21", [("Ontwikkeling systeem tot implementatie", "nl"), ("System development up to go-live", "en")]),
    "Entwicklung": (PS, "0.21", [("Ontwikkeling", "nl"), ("Development", "en")]),
    "Professional consulting services for project management": (PS, "0.21", [("Professional consulting services for project management", "en")]),
    "Consulting Services": (PS, "0.21", [("Consulting Services", "en")]),
    "Training course delivery": (PS, "0.21", [("Training course delivery", "en")]),
    "Training Services - Advanced Level": (PS, "0.21", [("Training Services - Advanced Level", "en")]),
    "Seminar": (PS, "0.21", [("Seminar", "en"), ("Seminar", "nl")]),
    "Seminarunterlagen": (PS, "0.21", [("Seminarmateriaal", "nl"), ("Seminar handouts", "en")]),
    "Teilnahmegebühr": (PS, "0.21", [("Deelnamekosten", "nl"), ("Attendance fee", "en")]),
    "Fremdleistung Anbieter A": (PS, "0.21", [("Inhuur derden leverancier A", "nl"), ("Third-party services supplier A", "en")]),
    "Fremdleistung Anbieter B": (PS, "0.21", [("Inhuur derden leverancier B", "nl")]),
    "Paketierung der Anwendung \"Kofax 10.2\" für 180 Geräte": (PS, "0.21", [("Paketteren applicatie \"Kofax 10.2\" voor 180 apparaten", "nl"), ("Packaging of application \"Kofax 10.2\" for 180 devices", "en")]),
    "Festpreis": (PS, "0.21", [("Vaste prijs", "nl"), ("Fixed price", "en")]),
    "Fastpris": (PS, "0.21", [("Fixed fee", "en")]),
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


KEY = {norm(k): v for k, v in L.items()}
loc = lambda t: t.rsplit("}", 1)[-1]  # noqa: E731


def invoice_lines(root) -> list[str]:
    out = []
    for el in root.iter():
        if loc(el.tag) in ("Item", "SpecifiedTradeProduct"):
            for ch in el:
                if loc(ch.tag) in ("Name", "Description") and (ch.text or "").strip():
                    out.append(" ".join(ch.text.split()))
    return out


def joined(names: list[str]) -> str:
    names = list(dict.fromkeys(names))
    head = "; ".join(names[:3])
    return head + (f" (+{len(names) - 3} more)" if len(names) > 3 else "")


def main() -> None:
    rows, seen_src = {}, Counter()
    unmatched = Counter()
    for d in SOURCES:
        for p in sorted((DOCS / d).rglob("*.xml")):
            if ".git" in p.parts:
                continue
            try:
                root = SafeET.parse(str(p), forbid_dtd=True).getroot()
            except Exception:
                continue
            if loc(root.tag) not in ("Invoice", "CrossIndustryInvoice"):
                continue
            hits = []
            for t in invoice_lines(root):
                lab = KEY.get(norm(t))
                if lab is None:
                    unmatched[t] += 1
                    continue
                hits.append(lab)
                acc, vat, outs = lab
                for text, lang in outs:
                    rows[(acc, text, lang, vat)] = "einvoice" if norm(text) == norm(t) else "einvoice_translated"
                seen_src[d] += 1
            accs = {h[0] for h in hits}
            if len(hits) >= 2 and len(accs) == 1:   # one-account invoice: the reader's joined description
                acc = hits[0][0]
                for lang in ("nl", "en"):
                    names = [next((x for x, lg in h[2] if lg == lang), None) for h in hits]
                    names = [n for n in names if n]
                    if len(set(names)) >= 2:
                        rows[(acc, joined(names), lang, hits[0][1])] = "einvoice_joined"
    desc = json.loads(OUT.read_text(encoding="utf-8"))
    for acc in desc:
        desc[acc].pop(FAMILY, None)
    add = Counter()
    for (acc, text, lang, vat), origin in sorted(rows.items()):
        desc[acc].setdefault(FAMILY, []).append(
            {"text": text, "language": lang, "doc_type": "invoice", "vat_rate": vat,
             "keyword_free": keyword_free(text, acc), "origin": origin})
        add[acc] += 1
    OUT.write_text(json.dumps(desc, indent=1, ensure_ascii=False), encoding="utf-8")
    print("lines matched per source:", dict(seen_src))
    print("unique unmatched line texts:", len(unmatched))
    for acc in sorted(desc):
        fam = desc[acc].get(FAMILY, [])
        kf = sum(x["keyword_free"] for x in fam)
        print(f"{acc:34s} einvoice={len(fam):3d} keyword_free={kf:3d} "
              f"nl={sum(x['language'] == 'nl' for x in fam)} en={sum(x['language'] == 'en' for x in fam)}")


if __name__ == "__main__":
    main()
