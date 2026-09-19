"""Helpers for the synthetic generator: sampling, dates, noise primitives, formatting.

Kept separate from generate_transactions.py so the generator stays readable.
Everything is deterministic given the caller's random.Random.
"""
import bisect
import calendar
import datetime as dt
import math
import random
import re

START = dt.date(2025, 1, 1)
END = dt.date(2026, 8, 31)

NL_M = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
        "september", "oktober", "november", "december"]
EN_M = ["January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December"]


def wchoice(rng, items, weights):
    tot = float(sum(weights))
    x = rng.random() * tot
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if x < acc:
            return it
    return items[-1]


def multinomial(rng, n, weights):
    tot = float(sum(weights))
    cum, acc = [], 0.0
    for w in weights:
        acc += w
        cum.append(acc)
    counts = [0] * len(weights)
    for _ in range(n):
        j = bisect.bisect_right(cum, rng.random() * tot)
        counts[min(j, len(weights) - 1)] += 1
    return counts


def money(v):
    return round(max(float(v), 0.01) + 1e-9, 2)


def add_months(y, m, k):
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def mk_date(y, m, day):
    return dt.date(y, m, min(day, calendar.monthrange(y, m)[1]))


def is_bd(d):
    return d.weekday() < 5


def roll_bd(d):
    """Next business day; falls back to previous one if that would pass END."""
    e = d
    while not is_bd(e):
        e += dt.timedelta(days=1)
    if e > END:
        e = d
        while not is_bd(e):
            e -= dt.timedelta(days=1)
    return e


def last_bdays(y, m, n=3):
    d = mk_date(y, m, 31)
    out = []
    while len(out) < n:
        if is_bd(d):
            out.append(d)
        d -= dt.timedelta(days=1)
    return out


def rand_date(rng):
    return START + dt.timedelta(days=rng.randint(0, (END - START).days))


def receipt_date(rng):
    """Card/retail dates: weekends allowed at a reduced weight (Sat 0.55, Sun 0.30)."""
    while True:
        d = rand_date(rng)
        w = d.weekday()
        if w < 5 or rng.random() < (0.55 if w == 5 else 0.30):
            return d


def invoice_date(rng, cluster_p=0.0):
    """Business-day invoice date; with prob cluster_p one of the last 3 business days of a month."""
    if cluster_p and rng.random() < cluster_p:
        while True:
            y, m = add_months(2025, 1, rng.randint(0, 19))
            d = rng.choice(last_bdays(y, m))
            if START <= d <= END:
                return d
    return roll_bd(rand_date(rng))


def fmt_num(x, lang):
    s = "%.2f" % x
    return s.replace(".", ",") if lang == "nl" else s


def month_name(d, lang):
    return (NL_M if lang == "nl" else EN_M)[d.month - 1]


def prev_month(d):
    y, m = add_months(d.year, d.month, -1)
    return dt.date(y, m, 1)


# ---------------------------------------------------------------- Zipf-Mandelbrot

def zm_weights(n, s, q):
    return [(r + 1 + q) ** (-s) for r in range(n)]


def zipf_mle(counts, q=0.0, lo=0.05, hi=3.0):
    """MLE of the exponent for p_r ~ (r+q)^-s over ranks 1..K (counts sorted desc, zeros kept)."""
    c = sorted(counts, reverse=True)
    K = len(c)
    if sum(c) == 0 or K < 2:
        return float("nan")

    def ll(s):
        w = [(r + 1 + q) ** (-s) for r in range(K)]
        z = math.log(sum(w))
        return sum(ci * (-s * math.log(r + 1 + q) - z) for r, ci in enumerate(c))
    a, b = lo, hi
    g = (math.sqrt(5) - 1) / 2
    for _ in range(80):
        x1, x2 = b - g * (b - a), a + g * (b - a)
        if ll(x1) > ll(x2):
            b = x2
        else:
            a = x1
    return (a + b) / 2


def chi2_sf_even(x, df):
    """Survival function of chi-square for even df."""
    k = df // 2
    h = x / 2.0
    return math.exp(-h) * sum(h ** i / math.factorial(i) for i in range(k))


# ---------------------------------------------------------------- noise primitives

KEY_NB = {
    "q": "wa", "w": "qes", "e": "wrd", "r": "etf", "t": "ryg", "y": "tuh", "u": "yij", "i": "uok",
    "o": "ipl", "p": "ol", "a": "qsz", "s": "awdx", "d": "sefc", "f": "drgv", "g": "fthb",
    "h": "gyjn", "j": "hukm", "k": "jil", "l": "kop", "z": "asx", "x": "zsc", "c": "xdv",
    "v": "cfb", "b": "vgn", "n": "bhm", "m": "nj",
}


def op_typo(s, rng):
    idx = [i for i, c in enumerate(s) if c.isalpha() and 0 < i < len(s) - 1
           and s[i - 1].isalpha() and c.lower() in KEY_NB]
    if not idx:
        return None
    i = rng.choice(idx)
    c = s[i]
    k = rng.randint(0, 3)
    if k == 0:                       # keyboard-adjacent substitution
        r = rng.choice(KEY_NB[c.lower()])
        return s[:i] + (r.upper() if c.isupper() else r) + s[i + 1:]
    if k == 1:                       # dropped letter
        return s[:i] + s[i + 1:]
    if k == 2:                       # doubled letter
        return s[:i] + c + s[i:]
    if s[i + 1].isalpha():           # adjacent swap
        return s[:i] + s[i + 1] + c + s[i + 2:]
    return s[:i] + s[i + 1:]


OCR_LETTER = [("O", "0"), ("l", "1"), ("I", "1"), ("S", "5"), ("B", "8"), ("m", "rn")]
OCR_DIGIT = [("0", "O"), ("1", "l"), ("5", "S")]


def op_ocr(s, rng):
    cands = []
    for m in re.finditer(r"\S+", s):
        tok = m.group(0)
        if re.search(r"[.,]\d", tok):          # never touch money
            continue
        if re.search(r"\d", tok) and len(tok) >= 5:
            for a, b in OCR_DIGIT:
                for j, ch in enumerate(tok):
                    if ch == a:
                        cands.append((m.start() + j, a, b))
        elif tok.isalpha() and len(tok) >= 4:
            for a, b in OCR_LETTER:
                for j, ch in enumerate(tok):
                    if ch == a:
                        cands.append((m.start() + j, a, b))
    if not cands:
        return None
    i, a, b = rng.choice(cands)
    return s[:i] + b + s[i + len(a):]


ABBR = [(r"\bfactuur\b", "fact."), (r"\binvoice\b", "inv."), (r"\bmaandelijks\b", "mnd"),
        (r"\bmaand\b", "mnd"), (r"\bmonthly\b", "mthly"), (r"\babonnement\b", "abon."),
        (r"\bsubscription\b", "subscr."), (r"\bbetaling\b", "bet."), (r"\bkwartaal\b", "kw."),
        (r"\bperiode\b", "per."), (r"\bkenmerk\b", "kenm."), (r"\bnummer\b", "nr."),
        (r"\bpayment\b", "pmt"), (r"\bperiod\b", "per."), (r"\bannual\b", "ann."),
        (r"\bhours\b", "hrs"), (r"\buren\b", "u."), (r"\bklantnummer\b", "klantnr"),
        (r"\breference\b", "ref."), (r"\bquarterly\b", "qtrly"), (r"\bservice\b", "svc"),
        (r"\bdienstverlening\b", "dienstverl."), (r"\bkosten\b", "kst."), (r"\bwith\b", "w/"),
        (r"\bgebruikers\b", "gebr."), (r"\bkantoor\b", "kant.")]


def abbrev_candidates(s):
    return [(rx, rep) for rx, rep in ABBR if re.search(rx, s, re.I)]


def op_abbrev(s, rng):
    c = abbrev_candidates(s)
    if not c:
        return None
    rx, rep = rng.choice(c)
    return re.sub(rx, rep, s, count=1, flags=re.I)


def op_case(s, mode):
    return s.upper() if mode == "UPPER" else s.lower() if mode == "lower" else s.title()


LEGAL_RX = re.compile(
    r"\s(B\.?V\.?|N\.?V\.?|V\.?O\.?F\.?|C\.?V\.?|Holding B\.?V\.?|Inc\.?|LLC|Ltd\.?|Limited|GmbH|AG|SE|"
    r"SARL|S\.A\.|SA/NV|DAC|ApS|OU|OÜ|LLP|s\.r\.o\.|Pty Ltd|SL|Unlimited Company|Coöperatief U\.A\.)$", re.I)


def legal_form(s):
    """Canonical legal-form token of a vendor string ('' if none)."""
    m = LEGAL_RX.search(s.strip())
    if not m:
        return ""
    return re.sub(r"[^A-Za-z]", "", m.group(1)).upper()
