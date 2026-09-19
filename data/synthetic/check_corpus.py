"""Checks the stage-2 vendor/description corpus (data/synthetic/spec/corpus/*.json), revision 1.

Run: PYTHONPATH=src .venv/bin/python data/synthetic/check_corpus.py
Exit code 1 on any FAIL. Keyword lexicons below are the checker's own independent regexes.

Revision 1 structure per account file: `archetypes` (family, price model, VAT, doc mix), `pools`
(description templates per family, with placeholders) and `vendors` (each tied to ONE archetype).
A vendor's descriptions can only come from its archetype's family pool, so vendor/description
agreement holds by construction; this checker verifies the corpus is consistent with that.
"""
import json, re, string, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gen_helpers import legal_form

CORPUS = Path(__file__).parent / "spec" / "corpus"
MIN_VENDORS, MIN_TEMPLATES = 40, 8
FREE_BAND = (0.25, 0.80)   # widened in revision 1: shared generic vocabulary (needed for the exclusivity gate) raises the free share; see spec keyword_shortcut_band
PLACEHOLDERS = {"product", "plan", "users", "seats", "period", "month", "year", "fy", "pperiod", "q", "date",
                "inv", "ref", "cust", "city", "route", "flight", "hrs", "domain", "total", "net", "vat"}
NL_FORMS = {"BV", "NV", "VOF", "CV", "CUA", "HOLDINGBV", "LLP"}
GROUP = {"BV": "NL", "NV": "NL", "VOF": "NL", "CV": "NL", "CUA": "NL", "HOLDINGBV": "NL", "LLP": "NL",
         "INC": "US", "LLC": "US", "LTD": "IE/UK", "LIMITED": "IE/UK", "DAC": "IE/UK", "UNLIMITEDCOMPANY": "IE/UK",
         "GMBH": "DE", "AG": "DE", "SE": "DE"}
LANDLORD = {"vastgoed_bv_generic", "landlord_institutional"}
BANNED = ["(PERIOD)", "PLAUSIBLE", "1234", "5514", "4321"]

LEX = {
 "software": r"abonnement|abon\b|subscr|licen[cs]|software|saas|cloud|hosting|domein|domain|workspace|\bseats?\b|gebruikers?|\busers?\b|\bplan\b|renewal|storage|opslag|\bapi\b|vpn|\bapp\b|\bcrm\b|\bide\b|webshop|virus|wachtwoord|password|e-signature|analytics|ci/cd|server|verlenging|hernieuwing|ontwikkel|developer|transcription|nieuwsbrief|email marketing|projectmanagement|facturatiesoftware|ai assistant|sslcert|ssl|web builder|video hosting|team chat|online agenda|tool",
 "travel": r"\bov\b|ov-|reis|trein|train|fuel|brandstof|tank|benzine|petrol|diesel|parkeer|parking|parkeren|parkmobile|easypark|q-park|taxi|\bride\b|\brit\b|ritten|uber|vlucht|flight|airline|ticket|chipkaart|retour|return|\bkm\b|transport|fiets|bike|laad|charging|kwh|autohuur|car rental|car sharing|deelauto|deelscooter|scooter|veerboot|ferry|tol\b|toll|vignet|wegenwacht|roadside|bus\b|schiphol|airport|kilometer|mileage|shuttle|lease|pech|treinabonnement|dal voordeel|public transport|ns flex|klm",
 "office": r"kantoor|office|papier|paper|toner|inkt|\bink\b|printer|\bpens?\b|balpen|stationery|schrijfwaren|ordner|nietjes|staples|schriften|notebooks?|bureau|desk|cartridge|hdmi|keyboard|toetsenbord|muis|mouse|usb|kabel|cable|stoel|chair|whiteboard|stiften|markers?|visitekaartjes|business cards|flyers|folders|etiketten|labels|shredder|versnipper|lamp|envelop|archie|monitor|laptop|webcam|headset|koptelefoon|stekkerdoos|power strip|lamineer|laminating|ssd|dockingstation|docking|batterij|batteries|voetensteun|footrest|verzend|packing|prikbord|notice board|onderhoudskit|maintenance kit|organi[sz]er|brievenbak|paper tray|kast|reception|kantoorinrichting|schrijf|plakband|tape|monitorarm|monitor arm|highlighter|markeer",
 "utilities": r"energie|energy|stroom|\bgas\b|gasverbruik|elektr|electric|water|internet|mobiel|mobile|telefo|phone|tarief|kwh|\bm3\b|voorschot|netbeheer|grid|glasvezel|fibre|broadband|\bsim\b|\bdata\b|verbruik|usage|meter|roaming|stadsverwarming|district heat|vastrecht|standing charge|\bode\b|energiebelasting|bundel|bundle|aansluiting|connection|sip trunk|televisie|utility|power consumption|heating",
 "professional": r"advies|advice|advis|consult|advocaat|attorney|legal|juridisch|notari|accountan|boekhoud|bookkeep|jaarrekening|honorarium|\bfees?\b|retainer|akte|deed|belasting|tax|aangifte|\bkvk\b|handelsregister|chamber of commerce|trade register|uren|hours|uurtarief|hourly|loonadministratie|payroll|vertaling|translation|merkregistratie|trademark|statuten|articles of association|coaching|gdpr|compliance|audit|freelance juridisch|hr consulting|business plan|ondernemingsplan|bijstand|legal support|duurzaamheid|adviesfactuur|consultancy",
 "rent": r"huur|rent|lease|verhuur|servicekosten|service charge|service costs|flex|werkplek|desk|cowork|kantoorruimte|office space|deposit|borg|\bm2\b|sqm|vergaderruimte|meeting room|atelier|studio|opslagbox|storage unit|praktijkruimte|treatment room|parkeerplaats|parking space|bedrijfsunit|business unit|bedrijfsruimte|indexatie|indexation|unit 2\.14|pand|huurpenning|huurnota|stookkosten",
 "general": r"lunch|representatie|catering|koffie|coffee|bloemen|flowers|cadeau|gift|kantine|diversen|miscellaneous|sundries|boodschappen|groceries|borrel|drinks|drankjes|relatiegeschenk|hamper|gereedschap|tools|verf|paint|schoonmaak|cleaning|diner|dinner|verzekering|insurance|lidmaatschap|membership|kerstpakket|season|planten|plants|sleutel|key cutting|wasserette|laundry|postzegels|stamps|greeting|kaart|cards|verzend|courier|afval|waste|fooi|tips|petty|uitje|outing|jubileum|anniversary|verjaardag|cakes|gebak|sandwich|snacks|hapjes|beverages|schoenmaker|shoes|wrap|volunteer|vrijwilliger|kerst|jumbo|thuisbezorgd|fleurop|gamma",
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


fails = []
def check(ok, msg):
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        fails.append(msg)


data = {p.stem: json.loads(p.read_text()) for p in sorted(CORPUS.glob("*.json"))}
accts = [k for k in data if k != "hard_cases"]
check(len(accts) == 7, f"7 account files present ({len(accts)})")
check("hard_cases" in data, "hard_cases.json present")

LEXK = {"Software & Subscriptions Expense": "software", "Travel & Transport Expense": "travel",
        "Office Supplies Expense": "office", "Utilities Expense": "utilities",
        "Professional Services Expense": "professional", "Rent Expense": "rent", "General/Other Expense": "general"}

all_names = {}
print(f"\n{'account':13}{'vend':>5}{'unv':>4}{'arch':>5}{'tmpl':>5}{'free%':>7}{'nl%':>5}")
total_unv = 0
for stem in accts:
    d = data[stem]
    acct = d["account"]
    V, A, P = d["vendors"], d["archetypes"], d["pools"]
    unv = sum(1 for v in V if v.get("unverified")); total_unv += unv
    check(len(V) >= MIN_VENDORS, f"{stem}: vendors {len(V)} >= {MIN_VENDORS}")
    bad_arch = [v["name"] for v in V if v["archetype"] not in A]
    check(not bad_arch, f"{stem}: every vendor archetype is defined {bad_arch[:3]}")
    fams = {a["family"] for a in A.values()}
    check(fams <= set(P), f"{stem}: every archetype family has a pool {sorted(fams - set(P))}")
    check(all(len(t) >= MIN_TEMPLATES for t in P.values()), f"{stem}: every pool has >= {MIN_TEMPLATES} templates")
    bad_ph = sorted({ph for pool in P.values() for t in pool for ph in re.findall(r"\{(\w+)\}", t["text"]) if ph not in PLACEHOLDERS})
    check(not bad_ph, f"{stem}: only known placeholders {bad_ph}")
    check(all("{" not in re.sub(r"\{\w+\}", "", t["text"]) for pool in P.values() for t in pool), f"{stem}: no stray braces")
    # a template may not name a corpus vendor (descriptions are archetype-level, vendor names come from {product})
    texts = [t["text"] for pool in P.values() for t in pool]
    check(not any(b in t for b in BANNED for t in texts), f"{stem}: no banned artifact strings in templates")
    # price attributes: template-mode templates need an amount range (or the archetype one)
    miss = [t["text"] for f, pool in P.items() for t in pool
            if any(a["family"] == f and a["mode"] == "template" for a in A.values()) and not t.get("amt")
            and not any(a["family"] == f and a.get("amt") for a in A.values())]
    check(not miss, f"{stem}: template-mode templates have amounts {miss[:2]}")
    lex = re.compile(LEX[LEXK[acct]], re.I)
    tmpls = [re.sub(r"\{\w+\}", " ", t["text"]) for pool in P.values() for t in pool]
    free = sum(1 for t in tmpls if not lex.search(t)) / len(tmpls)
    check(FREE_BAND[0] <= free <= FREE_BAND[1], f"{stem}: keyword-free template share {free:.2f} in {FREE_BAND}")
    nl = sum(t["lang"] == "nl" for pool in P.values() for t in pool) / len(tmpls)
    check(0.40 <= nl <= 0.70, f"{stem}: NL template share {nl:.2f} in [0.40,0.70]")
    # duplicate templates inside a family
    dup = [f for f, pool in P.items() if len({t["text"] for t in pool}) != len(pool)]
    check(not dup, f"{stem}: no duplicate templates within a family {dup}")
    # vendor hygiene: legal forms valid for the entity, one jurisdiction, no Holding on non-landlords
    bad = []
    for v in V:
        strings = [v["name"]] + v["aliases"]
        forms = [legal_form(s) for s in strings if legal_form(s)]
        groups = {GROUP.get(f, f) for f in forms}
        if len(groups) > 1:
            bad.append((v["name"], "mixed jurisdictions", sorted(groups)))
        if any(re.search(r"\bHolding\b", s) for s in strings) and v["archetype"] not in LANDLORD:
            bad.append((v["name"], "Holding on non-landlord"))
        if v.get("suffixes") and not (set(legal_form("x " + x) for x in v["suffixes"]) <= NL_FORMS):
            bad.append((v["name"], "non-Dutch noise suffix"))
        if v.get("suffixes") and v["country"] != "NL":
            bad.append((v["name"], "suffix on foreign entity"))
        if any(a == a.lower() and a != a.upper() for a in v["aliases"]):
            bad.append((v["name"], "lower-case alias copy"))
        if any(b in s for s in strings for b in BANNED):
            bad.append((v["name"], "banned string in vendor"))
    check(not bad, f"{stem}: vendor legal-form hygiene {bad[:3]}")
    for v in V:
        for s in [v["name"]] + v["aliases"]:
            n = norm(s)
            if n in all_names and all_names[n] != stem:
                check(False, f"vendor/alias overlap across accounts: {s} ({all_names[n]}, {stem})")
            all_names.setdefault(n, stem)
    print(f"{stem:13}{len(V):>5}{unv:>4}{len(A):>5}{len(tmpls):>5}{free*100:>7.1f}{nl*100:>5.0f}")

hc = data.get("hard_cases", {"vendors": [], "descriptions": [], "archetypes": {}})
hard_names = {norm(s) for v in hc["vendors"] for s in [v["name"]] + v["aliases"]}
check(not (hard_names & set(all_names)), "hard-case vendors are not reused in account files")
kinds = Counter((d["case"], d["kind"]) for d in hc["descriptions"])
import yaml
spec = yaml.safe_load((Path(__file__).parent / "spec" / "generative_spec.yaml").read_text())
need = [(c["id"], k) for c in spec["hard_cases"]["cases"] if "kinds" in c for k in c["kinds"]]
check(all(kinds[n] >= 2 for n in need), f"every (case, kind) in the spec has >= 2 corpus descriptions {[n for n in need if kinds[n] < 2]}")
check(len(hc["generic"]) >= 8, "generic description list has >= 8 entries")
tot_w = sum(c["weight"] for c in spec["hard_cases"]["cases"])
check(abs(tot_w - 1.0) < 1e-9, f"hard-case weights sum to 1 ({tot_w})")
print(f"INFO  unverified vendors total: {total_unv}")
print("\nRESULT:", "FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)
