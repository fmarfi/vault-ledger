"""Checks the stage-2 vendor/description corpus (data/synthetic/spec/corpus/*.json).

Run: PYTHONPATH=src .venv/bin/python data/synthetic/check_corpus.py
Exit code 1 on any FAIL. Keyword lexicons below are the checker's own independent
regexes; they must agree with each description's `keyword_free` flag.
"""
import json, re, sys
from collections import Counter
from pathlib import Path

CORPUS = Path(__file__).parent / "spec" / "corpus"
MIN_VENDORS, MIN_DESC = 40, 80
HIGH_PRIOR = {"software": 120, "travel": 120, "office": 120}
FREE_BAND = (0.30, 0.45)
MAX_FRAME_SHARE = 0.03

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

def frame(s):
    return re.sub(r"\d+", "#", norm(s))

fails = []
def check(ok, msg):
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        fails.append(msg)

data = {p.stem: json.loads(p.read_text()) for p in sorted(CORPUS.glob("*.json"))}
accts = [k for k in data if k != "hard_cases"]
check(len(accts) == 7, f"7 account files present ({len(accts)})")
check("hard_cases" in data, "hard_cases.json present")

print(f"\n{'account':13}{'vend':>5}{'unv':>4}{'desc':>5}{'nl%':>5}{'free%':>7}{'lex%':>7}{'dup%':>6}{'maxFrame%':>10}")
total_unv = 0
for k in accts:
    d = data[k]
    V, D = d["vendors"], d["descriptions"]
    unv = sum(1 for v in V if v.get("unverified")); total_unv += unv
    need = HIGH_PRIOR.get(k, MIN_DESC)
    check(len(V) >= MIN_VENDORS, f"{k}: vendors {len(V)} >= {MIN_VENDORS}")
    check(len(D) >= need, f"{k}: descriptions {len(D)} >= {need}")
    flag_free = sum(d_["keyword_free"] for d_ in D) / len(D)
    lex = re.compile(LEX[k], re.I)
    lex_free_items = [d_ for d_ in D if not lex.search(d_["text"])]
    lex_free = len(lex_free_items) / len(D)
    bad_free = [d_["text"] for d_ in D if d_["keyword_free"] and lex.search(d_["text"])]
    check(not bad_free, f"{k}: flagged keyword-free lines contain no lexicon hit ({len(bad_free)} violations) {bad_free[:3]}")
    check(FREE_BAND[0] <= flag_free <= FREE_BAND[1], f"{k}: keyword-free share {flag_free:.2f} in {FREE_BAND}")
    check(lex_free >= 0.30, f"{k}: lexicon-measured free share {lex_free:.2f} >= 0.30")
    norms = [norm(d_["text"]) for d_ in D]
    dup = 1 - len(set(norms)) / len(norms)
    fc = Counter(frame(d_["text"]) for d_ in D)
    mf = max(fc.values()) / len(D)
    check(dup == 0, f"{k}: exact duplicate rate {dup:.3f}")
    check(mf <= MAX_FRAME_SHARE + 0.005 or max(fc.values()) <= 3, f"{k}: top digit-masked frame share {mf:.3f}")
    nl = sum(d_["lang"] == "nl" for d_ in D) / len(D)
    check(0.40 <= nl <= 0.70, f"{k}: NL share {nl:.2f} in [0.40,0.70]")
    print(f"{k:13}{len(V):>5}{unv:>4}{len(D):>5}{nl*100:>5.0f}{flag_free*100:>7.1f}{lex_free*100:>7.1f}{dup*100:>6.1f}{mf*100:>10.1f}")

# vendor overlap across the 7 accounts (names and aliases)
owner = {}
overlaps = []
for k in accts:
    for v in data[k]["vendors"]:
        for s in [v["name"]] + v["aliases"]:
            n = norm(s)
            if n in owner and owner[n] != k:
                overlaps.append((s, owner[n], k))
            owner.setdefault(n, k)
check(not overlaps, f"vendor/alias overlap across accounts: {len(overlaps)} {overlaps[:5]}")
hc = data.get("hard_cases", {"vendors": [], "descriptions": []})
hard_names = {norm(s) for v in hc["vendors"] for s in [v["name"]] + v["aliases"]}
shared = sorted(n for n in hard_names if n in owner)
print(f"INFO  hard-case vendor strings also in account files (deliberate): {shared}")
check(not shared, "hard-case vendors are not reused in account files")

# cross-account duplicate description strings (informational: generic strings are allowed)
allnorm = Counter(n for k in accts for n in {norm(x["text"]) for x in data[k]["descriptions"]})
cross = sum(1 for c in allnorm.values() if c > 1)
tot = sum(len(data[k]["descriptions"]) for k in accts)
print(f"INFO  strings shared by >1 account: {cross}; total descriptions {tot}; overall unique {len(allnorm)} ({len(allnorm)/tot:.3f})")

# hard cases
cases = Counter(d["case"] for d in hc["descriptions"])
print("INFO  hard-case descriptions:", dict(cases), "vendors:", len(hc["vendors"]))
check(len(cases) == 8, f"8 hard cases covered ({len(cases)})")
check(len({d["text"] for d in hc["descriptions"] if d["case"] != "generic_description"}) == sum(1 for d in hc["descriptions"] if d["case"] != "generic_description"), "hard-case descriptions distinct")
print(f"INFO  unverified vendors total: {total_unv}")
print("\nRESULT:", "FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)
