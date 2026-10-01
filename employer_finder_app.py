#!/usr/bin/env python3
"""
employer_finder_app.py  --  German Training & Employer Finder (Web UI)
──────────────────────────────────────────────────────────────────────
Run:   python employer_finder_app.py
Open:  http://localhost:8080
"""

import csv, io, json, math, os, queue, re, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# ── Field / program configuration ────────────────────────────────────────────

# Each Ausbildung field maps to:
#   ba_terms:      keywords to send to BA Jobbörse
#   osm_amenities: OSM amenity=* tags for local institutions
#   osm_crafts:    OSM craft=* tags for trade shops
#   inst_label:    human label for OSM-found institutions

FIELDS = {
    # Social / Education
    "erzieher": {
        "label": "Erzieher/in",
        "group": "Soziales & Erziehung",
        "ba_terms": ["Erzieher", "Erzieherin", "Kita Ausbildung"],
        "osm_amenities": ["kindergarten"],
        "osm_crafts": [],
        "inst_label": "Kita / Kindertageseinrichtung",
    },
    "kinderpfleger": {
        "label": "Kinderpfleger/in",
        "group": "Soziales & Erziehung",
        "ba_terms": ["Kinderpfleger"],
        "osm_amenities": ["kindergarten", "childcare"],
        "osm_crafts": [],
        "inst_label": "Kita / Kinderbetreuung",
    },
    "sozialassistent": {
        "label": "Sozialassistent/in",
        "group": "Soziales & Erziehung",
        "ba_terms": ["Sozialassistent", "Sozialbetreuer"],
        "osm_amenities": ["social_facility", "kindergarten"],
        "osm_crafts": [],
        "inst_label": "Soziale Einrichtung",
    },
    "heilerziehungspfleger": {
        "label": "Heilerziehungspfleger/in",
        "group": "Soziales & Erziehung",
        "ba_terms": ["Heilerziehungspfleger"],
        "osm_amenities": ["social_facility"],
        "osm_crafts": [],
        "inst_label": "Einrichtung für Menschen mit Behinderung",
    },
    # Healthcare / Nursing
    "pflegefachmann": {
        "label": "Pflegefachmann/-frau",
        "group": "Gesundheit & Pflege",
        "ba_terms": ["Pflegefachmann", "Pflegefachfrau", "Altenpfleger"],
        "osm_amenities": ["nursing_home", "social_facility"],
        "osm_crafts": [],
        "inst_label": "Altenheim / Pflegeheim",
    },
    "krankenpfleger": {
        "label": "Gesundheits- und Krankenpfleger/in",
        "group": "Gesundheit & Pflege",
        "ba_terms": ["Krankenpfleger", "Gesundheits- und Krankenpfleger"],
        "osm_amenities": ["hospital", "clinic"],
        "osm_crafts": [],
        "inst_label": "Krankenhaus / Klinik",
    },
    "mfa": {
        "label": "Medizinische/r Fachangestellte/r",
        "group": "Gesundheit & Pflege",
        "ba_terms": ["Medizinische Fachangestellte", "MFA"],
        "osm_amenities": ["clinic", "doctors"],
        "osm_crafts": [],
        "inst_label": "Arztpraxis / Medizinisches Zentrum",
    },
    "notfallsanitaeter": {
        "label": "Notfallsanitäter/in",
        "group": "Gesundheit & Pflege",
        "ba_terms": ["Notfallsanitäter", "Rettungssanitäter"],
        "osm_amenities": ["hospital"],
        "osm_crafts": [],
        "inst_label": "Rettungsdienst / Krankenhaus",
    },
    # Construction / Handwerk
    "zimmerer": {
        "label": "Zimmerer/in",
        "group": "Bau & Handwerk",
        "ba_terms": ["Zimmerer"],
        "osm_amenities": [],
        "osm_crafts": ["carpenter"],
        "inst_label": "Zimmerei / Holzbau",
    },
    "maurer": {
        "label": "Maurer/in",
        "group": "Bau & Handwerk",
        "ba_terms": ["Maurer"],
        "osm_amenities": [],
        "osm_crafts": ["bricklayer", "construction"],
        "inst_label": "Bauunternehmen",
    },
    "dachdecker": {
        "label": "Dachdecker/in",
        "group": "Bau & Handwerk",
        "ba_terms": ["Dachdecker"],
        "osm_amenities": [],
        "osm_crafts": ["roofer"],
        "inst_label": "Dachdeckerei",
    },
    "elektriker": {
        "label": "Elektroniker/in",
        "group": "Bau & Handwerk",
        "ba_terms": ["Elektroniker", "Elektriker"],
        "osm_amenities": [],
        "osm_crafts": ["electrician"],
        "inst_label": "Elektrobetrieb",
    },
    "maler": {
        "label": "Maler/in und Lackierer/in",
        "group": "Bau & Handwerk",
        "ba_terms": ["Maler", "Lackierer"],
        "osm_amenities": [],
        "osm_crafts": ["painter"],
        "inst_label": "Malerbetrieb",
    },
    "shk": {
        "label": "Anlagenmechaniker/in SHK",
        "group": "Bau & Handwerk",
        "ba_terms": ["Anlagenmechaniker", "SHK", "Klempner"],
        "osm_amenities": [],
        "osm_crafts": ["plumber", "heating_engineer"],
        "inst_label": "SHK-Betrieb",
    },
    # Gastronomy / Food
    "koch": {
        "label": "Koch/Köchin",
        "group": "Gastronomie & Lebensmittel",
        "ba_terms": ["Koch", "Köchin"],
        "osm_amenities": [],
        "osm_crafts": [],
        "inst_label": "Restaurant / Hotel",
    },
    "baecker": {
        "label": "Bäcker/in",
        "group": "Gastronomie & Lebensmittel",
        "ba_terms": ["Bäcker", "Bäckerei Ausbildung"],
        "osm_amenities": [],
        "osm_crafts": ["bakery"],
        "inst_label": "Bäckerei",
    },
    # Technical
    "kfz": {
        "label": "Kfz-Mechatroniker/in",
        "group": "Technik & Industrie",
        "ba_terms": ["Kfz-Mechatroniker", "Kraftfahrzeugmechatroniker"],
        "osm_amenities": [],
        "osm_crafts": ["car_repair", "tyres"],
        "inst_label": "Kfz-Werkstatt",
    },
    "mechatroniker": {
        "label": "Mechatroniker/in",
        "group": "Technik & Industrie",
        "ba_terms": ["Mechatroniker"],
        "osm_amenities": [],
        "osm_crafts": [],
        "inst_label": "Industrieunternehmen",
    },
    "fachinformatiker": {
        "label": "Fachinformatiker/in",
        "group": "Technik & Industrie",
        "ba_terms": ["Fachinformatiker"],
        "osm_amenities": [],
        "osm_crafts": [],
        "inst_label": "IT-Unternehmen",
    },
    # Commercial
    "kaufmann_einzelhandel": {
        "label": "Kaufmann/-frau im Einzelhandel",
        "group": "Kaufmännisch & Büro",
        "ba_terms": ["Kaufmann Einzelhandel", "Verkäufer Ausbildung"],
        "osm_amenities": [],
        "osm_crafts": [],
        "inst_label": "Einzelhandel",
    },
    "kaufmann_buero": {
        "label": "Kaufmann/-frau Büromanagement",
        "group": "Kaufmännisch & Büro",
        "ba_terms": ["Kaufmann Büromanagement", "Bürokaufmann"],
        "osm_amenities": [],
        "osm_crafts": [],
        "inst_label": "Unternehmen / Büro",
    },
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

BASE_H = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
JUNK_EXT = (".png", ".jpg", ".gif", ".svg", ".js", ".css", ".woff")


def _fetch(url, extra=None, timeout=15):
    h = {**BASE_H, **(extra or {})}
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            cs = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(cs, errors="replace")
    except Exception:
        return None


def _post(url, data: bytes, timeout=35):
    # Use minimal headers for Overpass — browser Accept headers cause 406
    h = {
        "User-Agent":   "EmployerFinder/3.0 (educational use)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept":       "*/*",
    }
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _emails(text):
    if not text:
        return []
    text = text.replace("[at]", "@").replace("(at)", "@")
    return [e for e in EMAIL_RE.findall(text)
            if not any(e.lower().endswith(j) for j in JUNK_EXT)]


# ── Geocoding ─────────────────────────────────────────────────────────────────

def geocode(location):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": location + ", Germany", "format": "json",
        "limit": 1, "countrycodes": "de",
    })
    data = _fetch(url, extra={"User-Agent": "EmployerFinder/3.0 (educational)"})
    if data:
        try:
            d = json.loads(data)
            if d:
                return float(d[0]["lat"]), float(d[0]["lon"]), d[0]["display_name"]
        except Exception:
            pass
    return None, None, ""


# ── BA Jobbörse scraper ───────────────────────────────────────────────────────

BA_URL   = "https://www.arbeitsagentur.de/jobsuche/suche"
JSON_TAG = re.compile(
    r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
AGENCY_WORDS = [
    "personal", "personalservice", "personaldienstleistung",
    "zeitarbeit", "leiharbeit", "recrui", "headhunter",
    "pluss ", "primajob", "adecco", "manpower", "randstad",
    "truecare", "all.medi", "tempton", "piening",
    "eura personal", "pamec", "pasit", "akkodis",
]


def _is_agency(name):
    n = name.lower()
    return any(w in n for w in AGENCY_WORDS)


def _ba_page(term, location, radius, angebotsart, page):
    p = {"was": term, "page": page}
    if angebotsart:
        p["angebotsart"] = angebotsart
    if location:
        p["wo"] = location
        p["umkreis"] = str(radius)
    html = _fetch(BA_URL + "?" + urllib.parse.urlencode(p))
    if not html:
        return [], 0
    for raw in JSON_TAG.findall(html):
        try:
            d   = json.loads(raw)
            res = d.get("suchergebnis", {})
            jobs = res.get("ergebnisliste", [])
            if jobs:
                return jobs, res.get("maxErgebnisse", 0)
        except Exception:
            pass
    return [], 0


def ba_search(term, location, radius, angebotsart="4", max_pages=6):
    seen, records = set(), []
    total = None
    for page in range(1, max_pages + 1):
        jobs, t = _ba_page(term, location, radius, angebotsart, page)
        if total is None:
            total = t
        if not jobs:
            break
        for j in jobs:
            firm = (j.get("firma") or "").strip()
            if not firm or firm in seen:
                continue
            seen.add(firm)
            locs   = j.get("stellenlokationen", [{}])
            addr   = locs[0].get("adresse", {}) if locs else {}
            plz    = addr.get("plz", "")
            city   = addr.get("ort", "")
            street = addr.get("strasse", "")
            site   = (j.get("allianzpartnerUrl") or "").strip()
            if site and not site.startswith("http"):
                site = "https://" + site
            records.append({
                "name":       firm,
                "category":   "Arbeitgeber" if not _is_agency(firm) else "Personaldienstleister",
                "location":   f"{plz} {city}".strip(),
                "address":    ", ".join(filter(None, [street, f"{plz} {city}".strip()])),
                "email":      "",
                "phone":      "",
                "website":    site,
                "source":     "BA Jobbörse",
                "job_title":  (j.get("stellenangebotsTitel") or "").strip(),
            })
        pages_needed = -(-total // 25) if total else 1
        if page >= min(pages_needed, max_pages):
            break
        time.sleep(1.0)
    return records


# ── OSM Overpass ──────────────────────────────────────────────────────────────

OVERPASS = "https://overpass-api.de/api/interpreter"


def _bbox(lat, lon, radius_km):
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * math.cos(math.radians(lat)))
    return f"{lat-dlat:.4f},{lon-dlon:.4f},{lat+dlat:.4f},{lon+dlon:.4f}"


def osm_search(lat, lon, radius_km, amenities, crafts, inst_label):
    # Cap OSM radius at 20km — bbox queries time out beyond that for dense cities
    bb    = _bbox(lat, lon, min(radius_km, 20))
    parts = []
    for a in amenities:
        parts.append(f'  node["amenity"="{a}"]({bb});')
    for c in crafts:
        parts.append(f'  node["craft"="{c}"]({bb});')
    if not parts:
        return []

    query   = "[out:json][timeout:25];\n(\n" + "\n".join(parts) + "\n);\nout body 300;\n"
    payload = urllib.parse.urlencode({"data": query}).encode()
    data    = _post(OVERPASS, payload, timeout=30)
    if not data:
        return []

    # Limit to first 200 named results so the table stays readable
    seen, results = set(), []
    for el in data.get("elements", [])[:500]:
        tags = el.get("tags", {})
        name = (tags.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        if len(results) >= 200:
            break
        city    = tags.get("addr:city") or tags.get("addr:suburb") or ""
        street  = tags.get("addr:street") or ""
        housenr = tags.get("addr:housenumber") or ""
        loc_str = ", ".join(filter(None, [(street + " " + housenr).strip(), city]))
        results.append({
            "name":      name,
            "category":  inst_label,
            "location":  city or loc_str,
            "address":   loc_str,
            "email":     tags.get("email") or tags.get("contact:email") or "",
            "phone":     tags.get("phone") or tags.get("contact:phone") or "",
            "website":   tags.get("website") or tags.get("contact:website") or "",
            "source":    "OpenStreetMap",
            "job_title": "",
        })
    return results


# ── Main search orchestrator ──────────────────────────────────────────────────

WELFARE_ORGS = [
    ("Caritas Deutschland",
     "https://www.caritas.de/hilfeundberatung/onlineberatung/freiwilligendienste",
     "caritas"),
    ("Diakonie Deutschland",
     "https://www.diakonie.de/freiwilligendienste/fsj",
     "diakonie"),
    ("DRK - Deutsches Rotes Kreuz",
     "https://www.drk.de/helfen/freiwillig-engagieren/fsj/",
     "drk"),
    ("AWO - Arbeiterwohlfahrt",
     "https://www.awo.org/freiwilligendienste",
     "awo"),
    ("Johanniter-Unfall-Hilfe",
     "https://www.johanniter.de/die-johanniter/ehrenamt/freiwilligendienste/fsj/",
     "johanniter"),
    ("Malteser Hilfsdienst",
     "https://www.malteser.de/ueber-malteser/ehrenamt/fsj.html",
     "malteser"),
    ("IJGD",
     "https://www.ijgd.de/freiwilligendienste/fsj/",
     "ijgd"),
    ("Paritaetischer Wohlfahrtsverband",
     "https://www.paritaet.org/themen/freiwilligendienste.html",
     "paritaet"),
]


# ── Result cache (30-min TTL) ─────────────────────────────────────────────────

_CACHE     = {}   # key -> (timestamp, [results])
CACHE_TTL  = 1800

def _cache_key(prog, field, loc):
    return f"{prog}:{field}:{loc.strip().lower()}"


def _best_email(emails, hint=""):
    if not emails:
        return ""
    if hint:
        for e in emails:
            if hint.lower() in e.lower():
                return e
    for prefix in ("info@", "kontakt@", "contact@", "post@"):
        for e in emails:
            if e.lower().startswith(prefix):
                return e
    return emails[0]


def search_stream(program_type, field_key, location, radius):
    """
    Generator — yields result dicts as they arrive from BA + OSM in parallel.
    Caches full result list for 30 min so repeat searches are instant.
    """
    ck = _cache_key(program_type, field_key, location)
    if ck in _CACHE:
        ts, cached = _CACHE[ck]
        if time.time() - ts < CACHE_TTL:
            yield from cached
            return

    q          = queue.Queue()
    DONE       = object()
    all_res    = []
    seen       = set()
    lock       = threading.Lock()

    def emit(record):
        key = record["name"].strip().lower()
        with lock:
            if key and key not in seen:
                seen.add(key)
                all_res.append(record)
                q.put(record)

    lat, lon, _ = geocode(location)
    time.sleep(0.3)

    if program_type == "fsj":
        ba_terms = ["Freiwilliges Soziales Jahr"]
        osm_am   = ["hospital", "nursing_home", "kindergarten", "social_facility"]
        osm_cr   = []; inst_lbl = "Soziale Einrichtung (FSJ)";  cat = "FSJ Träger"
    elif program_type == "bfd":
        ba_terms = ["Bundesfreiwilligendienst"]
        osm_am   = ["hospital", "nursing_home", "kindergarten", "social_facility"]
        osm_cr   = []; inst_lbl = "Soziale Einrichtung (BFD)"; cat = "BFD Träger"
    else:
        cfg      = FIELDS.get(field_key, {})
        ba_terms = cfg.get("ba_terms", [field_key])[:1]
        osm_am   = cfg.get("osm_amenities", [])
        osm_cr   = cfg.get("osm_crafts", [])
        inst_lbl = cfg.get("inst_label", "Betrieb / Einrichtung")
        cat      = f"Ausbildung: {cfg.get('label', field_key)}"

    def ba_worker():
        try:
            for term in ba_terms:
                for rec in ba_search(term, location, radius, angebotsart="4", max_pages=3):
                    rec["category"] = cat if rec["category"] == "Arbeitgeber" else rec["category"]
                    emit(rec)
        finally:
            q.put(DONE)

    def osm_worker():
        try:
            time.sleep(2)
            if lat is not None and (osm_am or osm_cr):
                for rec in osm_search(lat, lon, radius, osm_am, osm_cr, inst_lbl):
                    emit(rec)
        finally:
            q.put(DONE)

    threading.Thread(target=ba_worker,  daemon=True).start()
    threading.Thread(target=osm_worker, daemon=True).start()

    done_count = 0
    while done_count < 2:
        item = q.get(timeout=50)
        if item is DONE:
            done_count += 1
        else:
            yield item

    # FSJ / BFD: national welfare orgs (fast, run after parallel workers finish)
    if program_type in ("fsj", "bfd"):
        for name, url, hint in WELFARE_ORGS:
            html = _fetch(url)
            if html:
                emails = _emails(html)
                domain = url.split("/")[2]
                rec = {
                    "name": name, "category": cat, "location": "Bundesweit",
                    "address": "", "email": _best_email(emails, hint),
                    "phone": "", "website": f"https://{domain}",
                    "source": domain, "job_title": "",
                }
                emit(rec)
                yield rec
            time.sleep(0.5)

    _CACHE[ck] = (time.time(), list(all_res))


# ── HTML UI ───────────────────────────────────────────────────────────────────

def _build_field_options():
    groups = {}
    for key, cfg in FIELDS.items():
        g = cfg["group"]
        groups.setdefault(g, []).append((key, cfg["label"]))
    html = ""
    for g, items in groups.items():
        html += f'<optgroup label="{g}">'
        for key, label in items:
            html += f'<option value="{key}">{label}</option>'
        html += "</optgroup>"
    return html


HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ausbildungsplatz-Finder</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:#f0f4f8;color:#1e293b;min-height:100vh}
  header{background:#1d4ed8;color:#fff;padding:1.2rem 2rem;
         display:flex;align-items:center;gap:1rem}
  header h1{font-size:1.4rem;font-weight:700}
  header span{font-size:.85rem;opacity:.8}
  .card{background:#fff;border-radius:.75rem;box-shadow:0 2px 8px rgba(0,0,0,.08);
        padding:1.75rem;margin:1.5rem auto;max-width:900px}
  h2{font-size:1rem;font-weight:600;color:#475569;margin-bottom:1.1rem;
     text-transform:uppercase;letter-spacing:.05em}
  .row{display:flex;gap:1rem;flex-wrap:wrap}
  .field{flex:1;min-width:180px}
  label{display:block;font-size:.8rem;font-weight:600;color:#64748b;
        margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.04em}
  select,input{width:100%;padding:.6rem .8rem;border:1.5px solid #cbd5e1;
               border-radius:.5rem;font-size:.95rem;color:#1e293b;
               background:#fff;transition:border-color .15s}
  select:focus,input:focus{outline:none;border-color:#1d4ed8}
  #field-wrap{display:none}
  .btn{padding:.7rem 1.8rem;border:none;border-radius:.5rem;font-size:.95rem;
       font-weight:600;cursor:pointer;transition:background .15s}
  .btn-primary{background:#1d4ed8;color:#fff}
  .btn-primary:hover{background:#1e40af}
  .btn-primary:disabled{background:#93c5fd;cursor:not-allowed}
  .btn-csv{background:#0f766e;color:#fff}
  .btn-csv:hover{background:#0d5c54}
  .actions{display:flex;gap:.75rem;align-items:center;margin-top:1.2rem}
  #status{font-size:.9rem;color:#475569}
  #spinner{display:none;width:18px;height:18px;border:2.5px solid #cbd5e1;
           border-top-color:#1d4ed8;border-radius:50%;animation:spin .7s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  #results-card{display:none}
  .meta{display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem}
  .meta-item{font-size:.85rem;color:#475569}
  .meta-item b{color:#1e293b}
  .filter-row{display:flex;gap:.75rem;align-items:center;margin-bottom:.9rem}
  .filter-row input{max-width:280px;font-size:.88rem}
  .tag{display:inline-block;padding:.15rem .55rem;border-radius:.9rem;
       font-size:.75rem;font-weight:600}
  .tag-direct{background:#dcfce7;color:#166534}
  .tag-agency{background:#fef9c3;color:#854d0e}
  .tag-osm{background:#dbeafe;color:#1e40af}
  .tag-ba{background:#f3f4f6;color:#374151}
  table{width:100%;border-collapse:collapse;font-size:.88rem}
  thead tr{background:#f8fafc;border-bottom:2px solid #e2e8f0}
  th{padding:.65rem .75rem;text-align:left;font-weight:600;color:#475569;
     font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
  td{padding:.6rem .75rem;border-bottom:1px solid #f1f5f9;vertical-align:top}
  tr:hover td{background:#f8fafc}
  td a{color:#1d4ed8;text-decoration:none}
  td a:hover{text-decoration:underline}
  .no-results{text-align:center;padding:2.5rem;color:#94a3b8;font-size:.95rem}
  @media(max-width:600px){.row{flex-direction:column}.actions{flex-wrap:wrap}}
</style>
</head>
<body>

<header>
  <div>
    <h1>Ausbildungsplatz & Träger Finder</h1>
    <span>FSJ · BFD · Ausbildung — Arbeitgeber, Schulen, Kliniken &amp; Einrichtungen</span>
  </div>
</header>

<div class="card">
  <h2>Suche</h2>
  <div class="row">
    <div class="field">
      <label>Programm / Abschluss</label>
      <select id="type" onchange="onTypeChange()">
        <option value="fsj">FSJ – Freiwilliges Soziales Jahr</option>
        <option value="bfd">BFD – Bundesfreiwilligendienst</option>
        <option value="ausbildung">Ausbildung (Beruf wählen)</option>
      </select>
    </div>
    <div class="field" id="field-wrap">
      <label>Ausbildungsberuf</label>
      <select id="field">FIELD_OPTIONS</select>
    </div>
    <div class="field">
      <label>Ort / PLZ</label>
      <input id="location" type="text" placeholder="z. B. Berlin, 10115 …">
    </div>
  </div>
  <div class="actions">
    <button class="btn btn-primary" id="search-btn" onclick="doSearch()">Suchen</button>
    <div id="spinner"></div>
    <span id="status"></span>
  </div>
</div>

<div class="card" id="results-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.75rem;margin-bottom:1rem">
    <h2 style="margin:0">Ergebnisse</h2>
    <button class="btn btn-csv" onclick="exportCSV()">CSV exportieren</button>
  </div>
  <div class="meta" id="meta-row"></div>
  <div class="filter-row">
    <input type="text" id="filter-input" placeholder="Filter: Name, Ort, E-Mail …"
           oninput="applyFilter()">
    <label style="display:flex;align-items:center;gap:.4rem;cursor:pointer;
                  font-size:.85rem;font-weight:normal;color:#475569;text-transform:none;letter-spacing:0">
      <input type="checkbox" id="hide-agency" onchange="applyFilter()">
      Personaldienstleister ausblenden
    </label>
  </div>
  <div style="overflow-x:auto">
    <table id="results-table">
      <thead>
        <tr>
          <th>#</th><th>Name</th><th>Kategorie</th><th>Ort</th>
          <th>E-Mail</th><th>Telefon</th><th>Website</th><th>Quelle</th>
        </tr>
      </thead>
      <tbody id="results-body"></tbody>
    </table>
  </div>
</div>

<script>
let allResults = [];
let activeSource = null;

function onTypeChange(){
  const t = document.getElementById('type').value;
  document.getElementById('field-wrap').style.display = t==='ausbildung' ? '' : 'none';
}

function setLoading(on){
  document.getElementById('search-btn').disabled = on;
  document.getElementById('spinner').style.display = on ? 'block' : 'none';
}

function statusMsg(msg){ document.getElementById('status').textContent = msg; }

function doSearch(){
  const loc = document.getElementById('location').value.trim();
  if(!loc){ alert('Bitte einen Ort eingeben.'); return; }
  const type  = document.getElementById('type').value;
  const field = document.getElementById('field').value;

  // Cancel any in-flight search
  if(activeSource){ activeSource.close(); activeSource = null; }

  setLoading(true);
  statusMsg('Suche läuft …');
  allResults = [];
  document.getElementById('results-body').innerHTML = '';
  document.getElementById('meta-row').innerHTML = '';
  document.getElementById('results-card').style.display = 'none';

  const params = new URLSearchParams({type, field, location: loc, radius: 100});
  const src = new EventSource('/api/search?' + params);
  activeSource = src;

  src.onmessage = (e) => {
    const r = JSON.parse(e.data);
    allResults.push(r);
    appendRow(r, allResults.length);
    updateMeta();
    if(allResults.length === 1){
      document.getElementById('results-card').style.display = '';
    }
    statusMsg(allResults.length + ' Ergebnisse …');
  };

  src.addEventListener('done', () => {
    src.close(); activeSource = null;
    setLoading(false);
    statusMsg('');
    if(!allResults.length){
      document.getElementById('results-body').innerHTML =
        '<tr><td colspan="8" class="no-results">Keine Ergebnisse. Ort prüfen oder anderen Suchbegriff wählen.</td></tr>';
      document.getElementById('results-card').style.display = '';
    }
    applyFilter();
  });

  src.onerror = () => {
    src.close(); activeSource = null;
    setLoading(false);
    if(!allResults.length) statusMsg('Verbindungsfehler. Bitte erneut versuchen.');
    else { statusMsg(''); applyFilter(); }
  };
}

function categoryTag(cat){
  const c = cat.toLowerCase();
  if(c.includes('personal'))  return `<span class="tag tag-agency">${cat}</span>`;
  if(c.startsWith('ausbildung') || c.includes('träger'))
                               return `<span class="tag tag-direct">${cat}</span>`;
  return `<span class="tag tag-osm">${cat}</span>`;
}

function appendRow(r, i){
  const email   = r.email   ? `<a href="mailto:${esc(r.email)}">${esc(r.email)}</a>` : '–';
  const website = r.website
    ? `<a href="${r.website.startsWith('http')?r.website:'https://'+r.website}" target="_blank" rel="noopener">Link</a>`
    : '–';
  const tr = document.createElement('tr');
  tr.dataset.agency = r.category.toLowerCase().includes('personal') ? '1' : '0';
  tr.dataset.search  = [r.name,r.category,r.location,r.email||'',r.address||''].join(' ').toLowerCase();
  tr.innerHTML = `
    <td>${i}</td>
    <td><b>${esc(r.name)}</b>${r.job_title?'<br><small style="color:#94a3b8">'+esc(r.job_title)+'</small>':''}</td>
    <td>${categoryTag(r.category)}</td>
    <td>${esc(r.location)}</td>
    <td>${email}</td>
    <td>${esc(r.phone)||'–'}</td>
    <td>${website}</td>
    <td><small style="color:#94a3b8">${esc(r.source)}</small></td>`;
  document.getElementById('results-body').appendChild(tr);
}

function updateMeta(){
  const direct    = allResults.filter(r => !r.category.toLowerCase().includes('personal')).length;
  const agencies  = allResults.length - direct;
  const withEmail = allResults.filter(r => r.email).length;
  document.getElementById('meta-row').innerHTML = `
    <div class="meta-item">Gesamt: <b>${allResults.length}</b></div>
    <div class="meta-item">Direktarbeitgeber / Einrichtungen: <b>${direct}</b></div>
    <div class="meta-item">Personaldienstleister: <b>${agencies}</b></div>
    <div class="meta-item">Mit E-Mail: <b>${withEmail}</b></div>`;
}

function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function applyFilter(){
  const q    = document.getElementById('filter-input').value.toLowerCase();
  const noAg = document.getElementById('hide-agency').checked;
  document.querySelectorAll('#results-body tr').forEach(tr => {
    if(!tr.dataset) return;
    const hide = (noAg && tr.dataset.agency==='1') || (q && !tr.dataset.search.includes(q));
    tr.style.display = hide ? 'none' : '';
  });
}

function exportCSV(){
  if(!allResults.length){ alert('Keine Daten zum Exportieren.'); return; }
  const params = new URLSearchParams({
    type:     document.getElementById('type').value,
    field:    document.getElementById('field').value,
    location: document.getElementById('location').value,
    radius:   100,
  });
  window.location = '/api/export?' + params;
}

document.addEventListener('keydown', e => {
  if(e.key==='Enter' && e.target.id==='location') doSearch();
});
</script>
</body>
</html>
""".replace("FIELD_OPTIONS", _build_field_options())


# ── HTTP server ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress default access logs

    def _send(self, code, content_type, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if path == "/":
            self._send(200, "text/html; charset=utf-8", HTML)

        elif path == "/api/search":
            prog     = params.get("type", "fsj")
            field    = params.get("field", "erzieher")
            location = params.get("location", "")

            if not location:
                self._send(400, "application/json", b'{"error":"location required"}')
                return

            # Server-Sent Events stream
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                for rec in search_stream(prog, field, location, 100):
                    msg = "data: " + json.dumps(rec, ensure_ascii=False) + "\n\n"
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"event: done\ndata: null\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif path == "/api/export":
            prog     = params.get("type", "fsj")
            field    = params.get("field", "erzieher")
            location = params.get("location", "")

            if not location:
                self._send(400, "text/plain", b"location required")
                return

            # Use cache if available, otherwise stream-collect
            ck = _cache_key(prog, field, location)
            if ck in _CACHE and time.time() - _CACHE[ck][0] < CACHE_TTL:
                results = _CACHE[ck][1]
            else:
                results = list(search_stream(prog, field, location, 100))

            buf = io.StringIO()
            w   = csv.DictWriter(buf, fieldnames=[
                "name", "category", "location", "address",
                "email", "phone", "website", "source", "job_title"
            ], extrasaction="ignore")
            w.writeheader()
            w.writerows(results)

            fname = f"{prog}_{field}_{location}_100km.csv".replace(" ", "_")
            body  = buf.getvalue().encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self._send(404, "text/plain", b"Not found")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ── Entry point ───────────────────────────────────────────────────────────────

PORT = int(os.environ.get("PORT", 8080))

if __name__ == "__main__":
    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Employer Finder running at  http://localhost:{PORT}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
