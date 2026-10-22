"""Fond de carte et relief pour la page.

1. Recupere une grille d'altitudes reelles (Copernicus DEM GLO-90) via l'API
   elevation d'Open-Meteo, sur l'emprise de la carte -> docs/dem.json
   (la page s'en sert pour dessiner la nappe de nuages selon l'altitude de la couche).
2. Dessine la carte dans la DA de la page (relief gris leger, courbes de niveau
   fines, quadrillage) -> docs/carte.png

A lancer une seule fois (ou quand l'emprise change) :
    pip install numpy scipy matplotlib
    python scripts/basemap.py
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# Emprise de la carte : rapport largeur / hauteur en km = 354 / 240 (taille affichee).
BBOX = {"lat0": 45.015, "lat1": 45.310, "lon0": 5.423, "lon1": 6.037}
NX, NY = 72, 49          # grille d'environ 680 m, 3528 points
# L'API gratuite compte chaque point comme un appel : 600 par minute et 5000 par heure.
# Par paquets de 100, on attend donc 11 s entre deux requetes (environ 7 min au total).
PAUSE = 11
WIDTH, HEIGHT = 354, 240  # taille affichee en px (rendu en x2)


def fetch_dem():
    lats, lons = [], []
    for j in range(NY):
        lat = BBOX["lat1"] - (BBOX["lat1"] - BBOX["lat0"]) * j / (NY - 1)
        for i in range(NX):
            lon = BBOX["lon0"] + (BBOX["lon1"] - BBOX["lon0"]) * i / (NX - 1)
            lats.append(round(lat, 5))
            lons.append(round(lon, 5))
    z = []
    for k in range(0, len(lats), 100):
        q = urllib.parse.urlencode({"latitude": ",".join(map(str, lats[k:k + 100])),
                                    "longitude": ",".join(map(str, lons[k:k + 100]))})
        for attempt in range(6):
            try:
                with urllib.request.urlopen("https://api.open-meteo.com/v1/elevation?" + q, timeout=60) as r:
                    z += json.load(r)["elevation"]
                break
            except Exception as e:  # limite de debit ou coupure : on attend la minute suivante
                print(f"  requete {k // 100 + 1} refusee ({e}), nouvel essai dans 65 s", file=sys.stderr, flush=True)
                if attempt == 5:
                    raise
                time.sleep(65)
        print(f"{min(k + 100, len(lats))}/{len(lats)}", file=sys.stderr, flush=True)
        time.sleep(PAUSE)
    return {"bbox": BBOX, "nx": NX, "ny": NY, "source": "Copernicus DEM GLO-90 via Open-Meteo",
            "z": [round(v) for v in z]}


def render(dem):
    import numpy as np
    from scipy import ndimage
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource

    z = np.array(dem["z"], dtype=float).reshape(dem["ny"], dem["nx"])
    # sur-echantillonnage pour des courbes lisses, en coordonnees pixels (x2)
    W, H = WIDTH * 2, HEIGHT * 2
    zf = ndimage.zoom(z, (H / z.shape[0], W / z.shape[1]), order=3)
    zf = ndimage.gaussian_filter(zf, 1.2)
    xs, ys = np.arange(zf.shape[1]), np.arange(zf.shape[0])
    import math
    lat_mid = (dem["bbox"]["lat0"] + dem["bbox"]["lat1"]) / 2
    px_m = (dem["bbox"]["lon1"] - dem["bbox"]["lon0"]) * 111320 * math.cos(math.radians(lat_mid)) / W
    hs = LightSource(azdeg=315, altdeg=45).hillshade(zf, vert_exag=2.5, dx=px_m, dy=px_m)

    fig = plt.figure(figsize=(W / 200, H / 200), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    bg = np.array([0xFB, 0xFB, 0xF8]) / 255
    ink = np.array([0x5B, 0x66, 0x70]) / 255
    a = np.clip((0.80 - hs) * 0.6, 0, 0.34)[:, :, None]
    ax.imshow(bg * (1 - a) + ink * a, extent=[0, W, H, 0], interpolation="bilinear")
    for g in range(0, W + 1, 60):
        ax.axvline(g, color="#ECEEE7", lw=0.4, zorder=1)
    for g in range(0, H + 1, 60):
        ax.axhline(g, color="#ECEEE7", lw=0.4, zorder=1)
    ax.contour(xs, ys, zf, levels=[l for l in range(100, 4000, 100) if l % 500],
               colors="#C4CAD1", linewidths=0.3, zorder=2)
    ax.contour(xs, ys, zf, levels=list(range(500, 4000, 500)), colors="#97A1AB", linewidths=0.6, zorder=2)
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    fig.savefig(DOCS / "carte.png")
    plt.close(fig)


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    path = DOCS / "dem.json"
    if path.exists() and "--refresh" not in sys.argv:
        dem = json.loads(path.read_text())
    else:
        dem = fetch_dem()
        path.write_text(json.dumps(dem, separators=(",", ":")))
    render(dem)
    print("dem.json et carte.png prêts")
