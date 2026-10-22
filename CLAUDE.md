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
- Sommet de couche : dernier niveau avec humidité au moins 93 % suivi d'un niveau plus sec.
- Indice mer = couche basse × sommet de couche sous le sommet visé × air sec au sommet × inversion × vent, puis 25 % de persistance (veille à 17h).
- Indice final = mer pondérée par le ciel (nuages moyens et hauts).
- Ce n'est pas une probabilité calibrée. `docs/history.json` garde les prévisions pour calibrer plus tard avec les observations réelles (webcams, sorties).

## État au 22 octobre 2026

- Code écrit dans un environnement sans accès à Open-Meteo : testé uniquement sur des profils synthétiques.
- À faire en premier : lancer `python scripts/forecast.py` sur les vraies données, vérifier que tous les niveaux de pression AROME et ICON-D2 arrivent bien (sinon adapter `LEVELS`), vérifier les clés suffixées par modèle (`_meteofrance_arome_france`, `_icon_d2`), y compris `sunrise` dans `daily`.
- Puis activer GitHub Pages (branche main, dossier `/docs`), ajouter le secret `NTFY_TOPIC`, lancer le workflow à la main.

## Préférences de Roman

- Réponses directes et concises, en français, sans formules qui sonnent IA.
- Jamais de tirets (—, –, -) en milieu de phrase, y compris dans les textes de la page.
- Heures affichées en HHhMM (8h11), jamais HH:MM.
- Préfère des modifications ciblées aux réécritures complètes.
