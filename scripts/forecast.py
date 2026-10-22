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

SUMMITS = [
    {"id": "rachais", "name": "Mont Rachais", "massif": "Chartreuse", "alt": 1046, "valley": "grenoble"},
    {"id": "eynard", "name": "Fort Saint Eynard", "massif": "Chartreuse", "alt": 1338, "valley": "gresivaudan"},
    {"id": "moucherotte", "name": "Moucherotte", "massif": "Vercors", "alt": 1901, "valley": "grenoble"},
    {"id": "chamechaude", "name": "Chamechaude", "massif": "Chartreuse", "alt": 2082, "valley": "gresivaudan"},
    {"id": "moucherolle", "name": "Grande Moucherolle", "massif": "Vercors", "alt": 2284, "valley": "grenoble"},
    {"id": "veymont", "name": "Grand Veymont", "massif": "Vercors", "alt": 2341, "valley": "trieves"},
]

MODELS = ["meteofrance_arome_france", "icon_d2"]
MODEL_LABEL = {"meteofrance_arome_france": "AROME", "icon_d2": "ICON-D2"}
# 775, 825 et 875 hPa : absents d'Open-Meteo pour les deux modeles.
# 975 : ICON-D2 seulement. 750 : AROME seulement.
LEVELS = [1000, 975, 950, 925, 900, 850, 800, 750, 700]

SAT_RH = 93    # couche nuageuse
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


def cloud_top(col, ground):
    """Sommet de la couche saturee la plus basse (m), ou None."""
    above = [c for c in col if c[0] > ground + 30 and c[0] < 3200]
    top = None
    for j, (z, t, rh, w) in enumerate(above):
        if rh >= SAT_RH:
            nxt = above[j + 1] if j + 1 < len(above) else None
            if nxt is None:
                return z
            if nxt[2] < SAT_RH:
                # limite entre le dernier niveau sature et le suivant
                frac = clamp((rh - SAT_RH) / max(rh - nxt[2], 1))
                return z + (nxt[0] - z) * frac
            top = nxt[0]
        elif top is not None:
            return top
    return top


def score_one(h, model, i, summit, ground):
    col = column(h, model, i)
    if len(col) < 4:
        return None
    Z = summit["alt"]
    low = at(series(h, "cloud_cover_low", model), i) or 0
    mid = at(series(h, "cloud_cover_mid", model), i) or 0
    high = at(series(h, "cloud_cover_high", model), i) or 0
    t2 = at(series(h, "temperature_2m", model), i)

    top = cloud_top(col, ground)
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
    return {
        "sea": round(sea), "sky": round(sky), "worth": round(worth),
        "agreement": round(100 - spread),
        "top": round(sum(tops) / len(tops)) if tops else None,
        "persist": round(sum(p) / len(p)) if p else None,
    }


def run():
    now = datetime.now(timezone.utc)
    out = {"generated": now.isoformat(timespec="minutes"), "models": [MODEL_LABEL[m] for m in MODELS],
           "summits": [], "days": []}
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
        out["summits"].append({**{k: s[k] for k in ("id", "name", "massif", "alt")},
                               "valley": v["name"], "days": days})
    dates = sorted({d["date"] for s in out["summits"] for d in s["days"]})
    out["days"] = dates
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
