# Mer de nuages

Indice de mer de nuages à l'aube pour six sommets autour de Grenoble (Mont Rachais, Fort Saint Eynard, Moucherotte, Chamechaude, Grande Moucherolle, Grand Veymont), pour décider la veille s'il vaut la peine de monter de nuit.

## Fonctionnement

- `scripts/forecast.py` interroge Open-Meteo (AROME France et ICON-D2, niveaux 1000 à 700 hPa) pour la vallée que domine chaque sommet, à l'heure du lever.
- Il calcule un indice de mer (couche basse, sommet de couche sous le sommet visé, air sec au sommet, inversion, vent, persistance de la veille) puis un indice final pondéré par le ciel au dessus.
- GitHub Actions le lance trois fois par jour et publie `docs/data.json`, lu par la page `docs/index.html` (GitHub Pages).
- Notification ntfy le soir uniquement si l'indice du lendemain dépasse 80 et que les deux modèles sont d'accord.

## Mise en place

1. Activer GitHub Pages sur la branche `main`, dossier `/docs`.
2. Ajouter le secret `NTFY_TOPIC` (Settings, Secrets and variables, Actions).
3. Lancer une première fois le workflow à la main (onglet Actions).

## Calibrage

`docs/history.json` garde chaque prévision. En notant les matins réels (webcams, sorties), on pourra ajuster les poids et transformer l'indice en vraie probabilité.
