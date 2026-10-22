"""Indice de mer de nuages a l'aube pour des sommets autour de Grenoble.

Source : API Open-Meteo, modeles AROME France (Meteo-France, 2,5 km)
et ICON-D2 (DWD, 2 km), niveaux de pression + nuages + vent.
Sortie : docs/data.json (lu par la page) et docs/history.json.
"""
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# Point de vallee = colonne d'air ou se forme la mer vue depuis le sommet.
VALLEYS = {
    "grenoble": {"name": "Cuvette grenobloise", "lat": 45.188, "lon": 5.724},
    "gresivaudan": {"name": "Grésivaudan", "lat": 45.270, "lon": 5.880},
    "trieves": {"name": "Trièves", "lat": 44.870, "lon": 5.650},
}

# Coordonnees approximatives des sommets (affichage sur la carte uniquement).
# label : cote de l'etiquette sur la carte, pour eviter les chevauchements.
SUMMITS = [
    {"id": "rachais", "name": "Mont Rachais", "massif": "Chartreuse", "alt": 1046, "valley": "grenoble",
     "lat": 45.2167, "lon": 5.7292, "label": "left"},
    {"id": "eynard", "name": "Fort Saint Eynard", "massif": "Chartreuse", "alt": 1338, "valley": "gresivaudan",
     "lat": 45.2361, "lon": 5.7614, "label": "right"},
    {"id": "moucherotte", "name": "Moucherotte", "massif": "Vercors", "alt": 1901, "valley": "grenoble",
     "lat": 45.1456, "lon": 5.6389, "label": "right"},
    {"id": "chamechaude", "name": "Chamechaude", "massif": "Chartreuse", "alt": 2082, "valley": "gresivaudan",
     "lat": 45.2878, "lon": 5.7875, "label": "left"},
    {"id": "moucherolle", "name": "Grande Moucherolle", "massif": "Vercors", "alt": 2284, "valley": "grenoble",
     "lat": 45.0350, "lon": 5.5795, "label": "right"},
    {"id": "veymont", "name": "Grand Veymont", "massif": "Vercors", "alt": 2341, "valley": "trieves",
     "lat": 44.8722, "lon": 5.5253, "label": "right"},
]

MODELS = ["meteofrance_arome_france", "icon_d2"]
MODEL_LABEL = {"meteofrance_arome_france": "AROME", "icon_d2": "ICON-D2"}
# 775, 825 et 875 hPa : absents d'Open-Meteo pour les deux modeles.
# 975 : ICON-D2 seulement. 750 : AROME seulement.
LEVELS = [1000, 975, 950, 925, 900, 850, 800, 750, 700]

SAT_RH = 93    # couche nuageuse
BASE_MAX = 900  # base de la couche au plus a 900 m au dessus du fond de vallee
DRY_RH = 80    # air sec au dessus


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def fetch(valley):
    hourly = ["temperature_2m", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "pressure_msl"]
    for p in LEVELS:
        hourly += [f"temperature_{p}hPa", f"relative_humidity_{p}hPa",
                   f"geopotential_height_{p}hPa", f"wind_speed_{p}hPa"]
    q = {
        "latitude": valley["lat"], "longitude": valley["lon"],
        "hourly": ",".join(hourly), "daily": "sunrise",
        "models": ",".join(MODELS), "timezone": "Europe/Paris",
        "past_days": 1, "forecast_days": 3,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def series(h, var, model):
    return h.get(f"{var}_{model}") or h.get(var)


def at(arr, i):
    if arr is None or i >= len(arr):
        return None
    return arr[i]


def column(h, model, i):
    """Profil vertical trie par altitude : [(z, T, RH, vent)]."""
    col = []
    for p in LEVELS:
        z = at(series(h, f"geopotential_height_{p}hPa", model), i)
        t = at(series(h, f"temperature_{p}hPa", model), i)
        rh = at(series(h, f"relative_humidity_{p}hPa", model), i)
        w = at(series(h, f"wind_speed_{p}hPa", model), i)
        if None in (z, t, rh):
            continue
        col.append((z, t, rh, w))
    col.sort()
    return col


def interp(col, z, k):
    """Valeur interpolee a l'altitude z (k : 1=T, 2=RH, 3=vent)."""
    pts = [(c[0], c[k]) for c in col if c[k] is not None]
    if not pts:
        return None
    if z <= pts[0][0]:
        return pts[0][1]
    for (z0, v0), (z1, v1) in zip(pts, pts[1:]):
        if z0 <= z <= z1:
            return v0 + (v1 - v0) * (z - z0) / (z1 - z0)
    return pts[-1][1]


def cloud_top(col, ground, low):
    """Sommet de la couche nuageuse basse partie du fond de vallee.

    Renvoie (sommet en m, epaisse) ou (None, False).
    Une couche saturee qui commence haut (nuages moyens d'un front) n'est pas
    une mer de nuages : on l'ignore. Une couche saturee jusqu'au dernier niveau
    est marquee epaisse (les sommets sont dedans).
    """
    if low is None or low < 20:
        return None, False
    above = [c for c in col if ground + 30 < c[0] < 3200]
    first = next((j for j, c in enumerate(above) if c[2] >= SAT_RH), None)
    if first is None or above[first][0] > ground + BASE_MAX:
        return None, False
    j = first
    while j + 1 < len(above) and above[j + 1][2] >= SAT_RH:
        j += 1
    if j + 1 == len(above):
        return above[j][0], True
    z, rh = above[j][0], above[j][2]
    nz, nrh = above[j + 1][0], above[j + 1][2]
    frac = clamp((rh - SAT_RH) / max(rh - nrh, 1))
    return z + (nz - z) * frac, False


def score_one(h, model, i, summit, ground):
    col = column(h, model, i)
    if len(col) < 4:
        return None
    Z = summit["alt"]
    low = at(series(h, "cloud_cover_low", model), i) or 0
    mid = at(series(h, "cloud_cover_mid", model), i) or 0
    high = at(series(h, "cloud_cover_high", model), i) or 0
    t2 = at(series(h, "temperature_2m", model), i)

    top, deep = cloud_top(col, ground, low)
    rh_sum = interp(col, Z + 50, 2)
    t_sum = interp(col, Z, 1)
    wind = interp(col, Z, 3) or 0
    # inversion : ecart entre la temperature au sommet et celle attendue
    # avec un gradient standard de 6,5 C par km depuis le fond de vallee
    inv = None
    if t2 is not None and t_sum is not None:
        inv = t_sum - (t2 - 6.5 * (Z - ground) / 1000)

    # 1. presence d'une couche basse
    s_cloud = clamp((low - 25) / 55)
    if top is None:
        s_cloud = min(s_cloud, 0.25)
    # 2. sommet de couche sous le sommet, avec marge
    if top is None:
        s_below = 0.0
    else:
        s_below = clamp((Z - top + 50) / 350)
    # 3. air sec au sommet
    s_dry = clamp((92 - (rh_sum if rh_sum is not None else 100)) / 30)
    # 4. inversion
    s_inv = clamp(((inv if inv is not None else 0) + 1) / 7)
    # 5. vent faible
    s_wind = clamp((40 - wind) / 25)
    # ciel pour le lever de soleil
    s_sky = clamp(1 - (mid + 0.6 * high) / 100)

    sea = s_cloud * (s_below ** 0.8) * (0.35 + 0.65 * s_dry) * (0.5 + 0.5 * s_inv) * (0.55 + 0.45 * s_wind)
    return {
        "sea": round(100 * clamp(sea ** 0.75)),
        "sky": round(100 * s_sky),
        "top": None if top is None else round(top),
        "deep": deep,
        "low": round(low), "mid": round(mid), "high": round(high),
        "rh_summit": None if rh_sum is None else round(rh_sum),
        "inversion": None if inv is None else round(inv, 1),
        "wind": round(wind),
        "parts": {k: round(v, 2) for k, v in
                  {"couche": s_cloud, "sous_sommet": s_below, "sec": s_dry,
                   "inversion": s_inv, "vent": s_wind, "ciel": s_sky}.items()},
    }


def persistence(h, model, sunrise_idx, ground, summit):
    """Etat de la veille a 17h : mer deja presente sous le sommet ?"""
    i = sunrise_idx - 13  # environ 17h la veille
    if i < 0:
        return None
    r = score_one(h, model, i, summit, ground)
    return None if r is None else r["sea"]


def hour_index(times, iso_sunrise):
    sr = datetime.fromisoformat(iso_sunrise)
    target = sr.replace(minute=0) + (timedelta(hours=1) if sr.minute >= 30 else timedelta())
    key = target.strftime("%Y-%m-%dT%H:%M")
    return times.index(key) if key in times else None


def combine(per_model, persist):
    vals = [m for m in per_model.values() if m]
    if not vals:
        return None
    sea = sum(m["sea"] for m in vals) / len(vals)
    sky = sum(m["sky"] for m in vals) / len(vals)
    spread = max(m["sea"] for m in vals) - min(m["sea"] for m in vals)
    p = [x for x in persist if x is not None]
    if p:
        # la persistance pese : une mer deja en place la veille tient souvent
        sea = 0.75 * sea + 0.25 * (sum(p) / len(p))
    worth = sea * (0.45 + 0.55 * sky / 100)
    tops = [m["top"] for m in vals if m["top"] is not None]
    with_top = [m for m in vals if m["top"] is not None]
    return {
        "sea": round(sea), "sky": round(sky), "worth": round(worth),
        "agreement": round(100 - spread),
        "top": round(sum(tops) / len(tops)) if tops else None,
        "deep": bool(with_top) and all(m.get("deep") for m in with_top),
        "mid": round(sum(m["mid"] for m in vals) / len(vals)),
        "high": round(sum(m["high"] for m in vals) / len(vals)),
        "persist": round(sum(p) / len(p)) if p else None,
    }


def mean_column(h, i):
    """Colonne moyenne des modeles (humidite moyennee niveau par niveau)."""
    col = []
    for p in LEVELS:
        vals = []
        for m in MODELS:
            z = at(series(h, f"geopotential_height_{p}hPa", m), i)
            t = at(series(h, f"temperature_{p}hPa", m), i)
            rh = at(series(h, f"relative_humidity_{p}hPa", m), i)
            if None not in (z, t, rh):
                vals.append((z, t, rh))
        if vals:
            n = len(vals)
            col.append((sum(v[0] for v in vals) / n, sum(v[1] for v in vals) / n, sum(v[2] for v in vals) / n, None))
    col.sort()
    return col


def cloud_layers(col, ground):
    """Couches saturees de la colonne : [[base, sommet, ouverte vers le haut], ...]."""
    pts = [c for c in col if ground + 30 < c[0] < 3200]
    out, j = [], 0
    while j < len(pts):
        if pts[j][2] >= SAT_RH:
            start = j
            while j + 1 < len(pts) and pts[j + 1][2] >= SAT_RH:
                j += 1
            if start == 0:
                base = ground
            else:
                lo, hi = pts[start - 1], pts[start]
                base = lo[0] + (hi[0] - lo[0]) * clamp((SAT_RH - lo[2]) / max(hi[2] - lo[2], 1))
            if j + 1 == len(pts):
                top, open_ = pts[j][0], True
            else:
                hi, nx = pts[j], pts[j + 1]
                top = hi[0] + (nx[0] - hi[0]) * clamp((hi[2] - SAT_RH) / max(hi[2] - nx[2], 1))
                open_ = False
            out.append([round(base), round(top), open_])
        j += 1
    return out


def valley_hour(h, i, ground):
    """Etat du ciel dans la vallee a l'heure i, sur la colonne moyenne des modeles.

    top / deep : mer de nuages (couche partie du fond de vallee), sinon None.
    layers : couches en altitude, qui ne touchent pas le fond (base, sommet, ouverte).
    """
    col = mean_column(h, i)
    if len(col) < 4:
        return None
    cover = {}
    for k in ("cloud_cover_low", "cloud_cover_mid", "cloud_cover_high"):
        v = [at(series(h, k, m), i) for m in MODELS]
        v = [x for x in v if x is not None]
        cover[k] = round(sum(v) / len(v)) if v else 0
    layers = cloud_layers(col, ground)
    sea = None
    if layers and layers[0][0] <= ground + BASE_MAX and cover["cloud_cover_low"] >= 20:
        sea = layers.pop(0)
    elif layers and layers[0][0] <= ground + BASE_MAX:
        layers.pop(0)  # humidite au sol sans nuages bas annonces : brume, on l'ignore
    return {"top": sea[1] if sea else None, "deep": bool(sea and sea[2]), "layers": layers,
            "low": cover["cloud_cover_low"], "mid": cover["cloud_cover_mid"], "high": cover["cloud_cover_high"]}


def overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def smooth(arr):
    """Retire ce qui n'apparait qu'une heure isolee (bruit des modeles)."""
    out = []
    for k, v in enumerate(arr):
        if not v:
            out.append(v)
            continue
        nb = [arr[j] for j in (k - 1, k + 1) if 0 <= j < len(arr) and arr[j]]
        v = dict(v)
        if v["top"] is not None and nb and all(n["top"] is None for n in nb):
            v["top"], v["deep"] = None, False
        v["layers"] = [l for l in v["layers"]
                       if not nb or any(overlaps(l, m) for n in nb for m in n["layers"])]
        out.append(v)
    return out


def timeline(cache, last_sunrise):
    """Heure par heure, de maintenant jusqu'a 3 h apres le dernier lever prevu."""
    now = datetime.now(PARIS).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = datetime.fromisoformat(last_sunrise) + timedelta(hours=3) if last_sunrise else now + timedelta(hours=36)
    hours, valleys = [], {}
    any_data = next(iter(cache.values()))["hourly"]["time"]
    for t in any_data:
        dt = datetime.fromisoformat(t)
        if now <= dt <= end:
            hours.append(t)
    for vid, data in cache.items():
        h = data["hourly"]
        ground = data.get("elevation", 220)
        idx = {t: k for k, t in enumerate(h["time"])}
        valleys[vid] = smooth([valley_hour(h, idx[t], ground) if t in idx else None for t in hours])
    return {"hours": hours, "valleys": valleys}


def run():
    now = datetime.now(timezone.utc)
    out = {"generated": now.isoformat(timespec="minutes"), "models": [MODEL_LABEL[m] for m in MODELS],
           "valleys": VALLEYS, "summits": [], "days": []}
    cache = {}
    for s in SUMMITS:
        v = VALLEYS[s["valley"]]
        if s["valley"] not in cache:
            cache[s["valley"]] = fetch(v)
        data = cache[s["valley"]]
        h = data["hourly"]
        times = h["time"]
        ground = data.get("elevation", 220)
        daily = data["daily"]
        sunrises = daily.get(f"sunrise_{MODELS[0]}") or daily.get("sunrise") or []
        days = []
        for sr in sunrises:
            if datetime.fromisoformat(sr).replace(tzinfo=PARIS) < datetime.now(PARIS):
                continue
            i = hour_index(times, sr)
            if i is None:
                continue
            per = {MODEL_LABEL[m]: score_one(h, m, i, s, ground) for m in MODELS}
            pers = [persistence(h, m, i, ground, s) for m in MODELS]
            c = combine(per, pers)
            if c is None:
                continue
            days.append({"date": sr[:10], "sunrise": sr[11:16], **c, "models": per})
        out["summits"].append({**{k: s[k] for k in ("id", "name", "massif", "alt", "lat", "lon", "label")},
                               "valley": v["name"], "valley_id": s["valley"], "days": days})
    dates = sorted({d["date"] for s in out["summits"] for d in s["days"]})
    out["days"] = dates
    sunrises = sorted({f"{d['date']}T{d['sunrise']}" for s in out["summits"] for d in s["days"]})
    out["sunrises"] = sunrises
    out["timeline"] = timeline(cache, sunrises[-1] if sunrises else None)
    return out


def notify(out):
    topic = os.environ.get("NTFY_TOPIC")
    threshold = int(os.environ.get("NOTIFY_THRESHOLD", "80"))
    if not topic:
        return
    tomorrow = (datetime.now(PARIS) + timedelta(days=1)).strftime("%Y-%m-%d")
    state_file = DOCS / "notified.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    if state.get("date") == tomorrow:
        return
    best = None
    for s in out["summits"]:
        for d in s["days"]:
            if d["date"] == tomorrow and d["worth"] >= threshold and d["agreement"] >= 70:
                if best is None or d["worth"] > best[1]["worth"]:
                    best = (s, d)
    if not best:
        return
    s, d = best
    h, m = d["sunrise"].split(":")
    body = (f"{s['name']} ({s['alt']} m) : indice {d['worth']}/100. "
            f"Mer vers {d['top']} m, lever à {int(h)}h{m}.")
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                 headers={"Title": "Mer de nuages demain matin", "Priority": "high",
                                          "Tags": "cloud"})
    urllib.request.urlopen(req, timeout=30)
    state_file.write_text(json.dumps({"date": tomorrow}))


def append_history(out):
    path = DOCS / "history.json"
    hist = json.loads(path.read_text()) if path.exists() else []
    stamp = out["generated"]
    for s in out["summits"]:
        for d in s["days"][:2]:
            hist.append({"run": stamp, "summit": s["id"], "date": d["date"],
                         "sea": d["sea"], "sky": d["sky"], "worth": d["worth"], "top": d["top"]})
    path.write_text(json.dumps(hist[-4000:], separators=(",", ":")))


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    result = run()
    (DOCS / "data.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    append_history(result)
    if "--notify" in sys.argv:
        notify(result)
    print(json.dumps([(s["name"], [(d["date"], d["worth"]) for d in s["days"]]) for s in result["summits"]],
                     ensure_ascii=False))
