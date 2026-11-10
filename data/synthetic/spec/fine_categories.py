"""The 29 detailed expense categories and their parent account.

One detailed model can serve any chart of accounts: a customer's accounts are linked once
to these categories (see notebooks/model_experiments.ipynb, section 5).
fine_of() maps a free-text category label (a public dataset's label or a generator archetype)
to a detailed category; the first matching pattern wins.
"""
from __future__ import annotations

import re

SW, OF, PR, RE_, TR, UT, GE = ("Software & Subscriptions Expense", "Office Supplies Expense",
                               "Professional Services Expense", "Rent Expense", "Travel & Transport Expense",
                               "Utilities Expense", "General/Other Expense")

FINE = [  # (category, parent account, pattern)
    ("insurance_bank", GE, r"insurance|verzeker|\bbank|merchant fee"),
    ("registry_fees", PR, r"kvk|ip_registry|registry|taxes and licen|chamber of commerce"),
    ("legal_notary", PR, r"legal|\blaw|advocat|notar|solicitor|lawyer|attorney|ip_firm"),
    ("accounting_tax", PR, r"accountan|boekhoud|audit|tax_advice|tax advi|big_four|payroll_service|bookkeep"),
    ("consulting", PR, r"consult|advis|advies|hr_|recruit|translation|interpret|subcontract|contractor|"
                       r"uitbesteden|professional|temporary|contract labo"),
    ("cloud_hosting", SW, r"cloud|hosting|domain|server|api_saas"),
    ("software", SW, r"software|saas|subscription|\bict\b|\bit\b|computer serv|digital|\bapps?\b|web_builder|"
                     r"dev_tools|information and comm|information communication|internet services"),
    ("telecom", UT, r"telecom|telephone|phone|mobile|broadband|internet|communications"),
    ("energy", UT, r"energy|electric|\bgas\b|grid|energie|utilit|nutsvoorz"),
    ("water", UT, r"water"),
    ("coworking", RE_, r"cowork|flexwerk"),
    ("rent_lease", RE_, r"\brent|lease|leasing|\brates\b|huisvesting|office space|real estate|kantoorverhuur|"
                        r"vastgoed|landlord|property"),
    ("fuel_ev", TR, r"fuel|petrol|ev_charging|charging|mileage|motor|vehicle|automotive|roadside"),
    ("air_travel", TR, r"airline|air travel|flight"),
    ("hotel", TR, r"hotel|accommodation|lodging|verblijf|subsistence"),
    ("parking_toll", TR, r"parking|toll"),
    ("car_rental_taxi", TR, r"taxi|ride_share|car_rental|car_share|contract hire|car allowance|\bcar\b"),
    ("public_transport", TR, r"rail|train|transit|ov_tap|coach|\bbus|ferry|bike|scooter|commuter|transport|"
                             r"travel|vervoer|\breis"),
    ("it_hardware", OF, r"hardware|electronics|peripherals|cables|computer equip"),
    ("furniture", OF, r"furniture|furnishing"),
    ("printing", OF, r"print|copier|inkt|toner"),
    ("office_supplies", OF, r"office|stationery|papier|supplies|benodigdheden|kantoor|packaging|equipment|"
                            r"materials|wholesale"),
    ("meals_catering", GE, r"meal|catering|food|restaurant|\bbars?\b|cafe|kantine|representatie|entertain|"
                           r"hospitality"),
    ("advertising", GE, r"advertis|marketing|publicity|promotion|search_cloud_ads"),
    ("postage_shipping", GE, r"postage|shipping|courier|\bmail|freight"),
    ("training_membership", GE, r"training|education|opleiding|membership|dues|contribution|conference|"
                                r"seminar|sportschool|books|periodical"),
    ("repairs_cleaning", GE, r"repair|maintenance|cleaning|schoonmaak|sleutel|diy|garden"),
    ("retail_misc", GE, r"grocer|supermarket|department store|discount|drugstore|household|marketplace|gift|"
                        r"bloemist|liquor|kapper|retail|clothing|uniform|leisure"),
    ("other_general", GE, r"misc|general|other|overig|expenses?\b|services|diensten|cost of goods|events?\b"),
]
PARENT = {f: p for f, p, _ in FINE}
CATEGORIES = sorted(PARENT)
# used when an archetype's category belongs to a different account than the row's label
DEFAULT = {OF: "office_supplies", SW: "software", UT: "energy", RE_: "rent_lease", TR: "public_transport",
           PR: "consulting", GE: "other_general"}
# labels that are not an expense we classify (income, payroll, transfers, tax, ...)
EXCLUDE = re.compile(
    r"revenue|\bsales\b|gross receipts|income|receipts|refund|returns and allowances|transfer|owner|drawing|"
    r"funds introduced|director.?s.? loan|\bloans?\b|payroll|wage|salar|pension|sales tax payment|\bvat\b|"
    r"credit card payment|interest|dividend|saving|grant|benefit|care payments|social services clients|"
    r"depreciation|capital|fixed asset|needs review|ask the client|excluded|investment|\batm\b|"
    r"cash withdrawal|stock comp|accrued|personele exploitatie|externe inhuur|personeel", re.I)
_RX = [(f, re.compile(p, re.I)) for f, _, p in FINE]


def fine_of(label) -> str | None:
    """Detailed category for a free-text label, or None when excluded or unknown."""
    t = "" if label is None else str(label)
    if not t.strip() or t == "nan" or EXCLUDE.search(t):
        return None
    for f, rx in _RX:
        if rx.search(t):
            return f
    return None


def fine_for(archetype: str, account: str) -> str:
    """Category for a generated row: the archetype's category if it belongs to the row's account."""
    f = fine_of(archetype)
    return f if f and PARENT[f] == account else DEFAULT[account]
