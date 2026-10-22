# Mer de nuages : contexte du projet

Roman veut savoir la veille s'il vaut la peine de monter de nuit sur un sommet autour de Grenoble pour voir le lever de soleil au dessus d'une mer de nuages. La rando de nuit n'est pas agréable : il ne part que si les chances sont bonnes.

## Livrables

- Page web à consulter (GitHub Pages, `docs/index.html`, lit `docs/data.json`).
- Notification ntfy uniquement si l'indice est très élevé (seuil 80, accord des modèles au moins 70, une seule fois par date, au passage du soir). Le topic ntfy reste dans les secrets GitHub, jamais dans le repo public.
- Même architecture que son autre projet weekendrail (repo fruzac/weekendrail) : GitHub Actions + GitHub Pages, pas de serveur chez lui.

## Sommets suivis

| Sommet | Altitude | Massif | Vallée observée |
|---|---|---|---|
| Mont Rachais | 1046 m | Chartreuse | Cuvette grenobloise |
| Fort Saint Eynard | 1338 m | Chartreuse | Grésivaudan |
| Moucherotte | 1901 m | Vercors | Cuvette grenobloise |
| Chamechaude | 2082 m | Chartreuse | Grésivaudan |
| Grande Moucherolle | 2284 m | Vercors | Cuvette grenobloise |
| Grand Veymont | 2341 m | Vercors | Trièves |

La Bastille a été écartée (trop basse). Il a aussi mentionné la Chartreuse en général : d'autres sommets pourront s'ajouter.

## Ce qu'il faut pour une mer de nuages à l'aube (synthèse des recherches)

1. Anticyclone stable, peu de vent : l'inversion s'installe dans les vallées et peut tenir des jours (Largeron et Staquet 2016 : à Grenoble, inversion persistante sur environ 1200 m, jusqu'à 20 °C d'écart la nuit).
2. Nuit claire et longue (saison fin septembre à février), refroidissement par rayonnement.
3. Humidité forte en bas, air sec et doux au dessus.
4. Sommet de la couche sous l'altitude du point visé, avec marge. Couche typique de 100 à 500 m d'épaisseur.
5. Pas de nuages moyens ou hauts : ils réchauffent le sommet de la couche et cachent le lever.
6. Pas de changement de régime (front, vent de sud ouest au sommet de la couche, chute de pression).
7. Persistance : la méthode de MeteoSuisse suppose que la limite de demain égale celle d'aujourd'hui, puis corrige. Les modèles captent mal ces couches fines, donc l'état de la veille pèse lourd.

## Logique du score (`scripts/forecast.py`)

- Open-Meteo, modèles `meteofrance_arome_france` et `icon_d2`, niveaux 1000 à 700 hPa (température, humidité, géopotentiel, vent), nuages bas, moyens, hauts, à l'heure du lever.
- Ne pas utiliser `cloud_cover_low` seul : il couvre tout jusqu'à 3 km, donc mélange la mer et le sommet.
- Sommet de couche : dernier niveau avec humidité au moins 93 % suivi d'un niveau plus sec, en partant de la première couche saturée. Retenue seulement si sa base est à moins de 900 m au dessus du fond de vallée et si les nuages bas dépassent 20 % (sinon ce sont les nuages moyens d'un front, pas une mer : bug corrigé le 22/10 où la page affichait tous les sommets noyés). Saturée jusqu'au dernier niveau : `deep`, couche épaisse.
- Indice mer = couche basse × sommet de couche sous le sommet visé × air sec au sommet × inversion × vent, puis 25 % de persistance (veille à 17h).
- Indice final = mer pondérée par le ciel (nuages moyens et hauts).
- Ce n'est pas une probabilité calibrée. `docs/history.json` garde les prévisions pour calibrer plus tard avec les observations réelles (webcams, sorties).

## La page (`docs/index.html`), validée par Roman sur maquette

DA « carnet technique » : fond papier #FBFBF8, encre ardoise, IBM Plex Mono et IBM Plex Sans Condensed, nappe de nuages toujours en hachures gris bleu avec bord pointillé, indice en vert (70 et plus), ambre (45 à 69), gris (en dessous). Pas de marron, pas de verdict « oui / non » : il veut juste voir les scores.

En haut, un curseur heure par heure (de maintenant jusqu'à 3 h après le dernier lever prévu) : il déplace la nappe sur la carte et dans les hauteurs comparées, avec une frise de l'altitude de la couche (cuvette) et des raccourcis « maintenant » et « lever ». Les indices restent ceux du prochain lever. Données : `timeline` dans data.json, par vallée et par heure, calculée sur la colonne moyenne des deux modèles : `top`/`deep` = mer de nuages (couche saturée partie du fond de vallée), `layers` = nuages accrochés en altitude [base, sommet, ouverte], plus `low`/`mid`/`high`. Lissage : ce qui n'apparaît qu'une heure isolée est retiré. Règle d'affichage demandée par Roman : une couche est une nappe horizontale, donc un sommet plus bas qu'un sommet « dans les nuages » de la même vallée l'est aussi, sauf si la couche est accrochée en altitude ; dans ce cas elle est dessinée flottante (de sa base à son sommet) et ne descend jamais jusqu'au sol.

Trois blocs, dans cet ordre :
1. Petite carte : `docs/carte.png` (relief réel Copernicus DEM, ombrage gris léger, courbes tous les 100 m) + nappe dessinée en canvas depuis `docs/dem.json` : remplissage depuis le fond de chaque vallée tant que le relief est sous l'altitude prévue de la couche. Sommets placés par lat/lon (`SUMMITS` dans forecast.py, champ `label` pour le côté de l'étiquette).
2. Hauteurs comparées : sommets à l'échelle côte à côte, silhouette propre à chaque sommet (`SHAPES` dans la page), bande hachurée à l'altitude de la couche de sa vallée, marge en blanc dans la silhouette ou en rouge si moins de 150 m.
3. Sommets : un bloc par pic, trié par indice (barre couche / sommet, marge, humidité au sommet, vent, ciel, accord des modèles, détail par modèle repliable).

`scripts/basemap.py` génère `dem.json` et `carte.png` une seule fois (le workflow le lance s'ils manquent). Emprise fixe `BBOX`, rapport 354 × 240 px.

## État au 22 octobre 2026

- Premières vraies données passées (niveaux 775, 825, 875 hPa retirés). Le 22 octobre : temps perturbé, couche jusqu'à environ 3060 m, indices à 0.
- `docs/dem.json` et `docs/carte.png` pas encore générés : le prochain passage du workflow (ou `python scripts/basemap.py` en local) les crée.
- Coordonnées des sommets approximatives : à vérifier sur la carte IGN.
- Reste à faire : activer GitHub Pages (branche main, dossier `/docs`), ajouter le secret `NTFY_TOPIC`, puis calibrer les poids avec de vraies sorties.

## Préférences de Roman

- Réponses directes et concises, en français, sans formules qui sonnent IA.
- Jamais de tirets (—, –, -) en milieu de phrase, y compris dans les textes de la page.
- Heures affichées en HHhMM (8h11), jamais HH:MM.
- Préfère des modifications ciblées aux réécritures complètes.
