# Artefacts du chat

Un artefact est un livrable ou une vue de données autonome dans la conversation,
pas un composant React fourni par le modèle. Le catalogue de `artifacts.supported_artifacts`
est le contrat commun à tous les clients web du Harness, y compris sur mobile.
`artifacts.show_artifact(kind, payload)` publie une seule fois le résultat. Les
retours d'outils sont persistés ; les vues de providers restent temporaires.
L'apparition dans l'historique ne prouve ni affichage réussi ni lecture humaine.

## Inventaire et priorités

| Famille / usage | Type | État et limites |
| --- | --- | --- |
| Images, captures, résultats graphiques | `image` | Existant : raster PNG/JPEG/WebP/GIF vérifié, aperçu, agrandissement et téléchargement. |
| Parole, musique, sons demandés | `audio` | Existant : lecteur manuel, jamais d'autoplay, téléchargement. |
| PDF, bureautique, archives, gros jeux de données | `file` | Existant : fichier durable téléchargeable, pas d'exécution ni de lecteur intégré. |
| Notes, rapports, recettes, formules | `markdown` | Mis en service : document borné avec le rendu Markdown/KaTeX du chat et export `.md`. |
| Scripts, configurations, SQL, texte brut | `code` | Mis en service : texte littéral sélectionnable, copie et export ; étiquette de langage, pas de coloration syntaxique ni d'exécution. |
| Comparaisons, budgets, résultats structurés | `table` | Mis en service : filtre, tri, pagination 50 lignes et CSV de toutes les lignes filtrées dans l'ordre affiché. |
| Évolution, comparaison quantitative | `chart` | Mis en service : barres/courbes multi-séries, valeurs négatives, légende, tableau accessible et CSV. Axe horizontal catégoriel à pas constant ; pas d'analyse statistique implicite. |
| Historique, étapes, planning indicatif | `timeline` | Mis en service : chronologie verticale en lecture seule, ordre fourni conservé ; aucune création de tâche, rappel ou validation d'avancement. |
| Vidéo locale | futur lecteur `video` | Priorité suivante : utiliser `file` en attendant ; lecteur manuel, codecs et erreurs à traiter avant intégration. |
| PDF avec navigation dans les pages | futur lecteur spécialisé | Priorité suivante : `file` suffit pour la livraison ; décider d'un lecteur isolé et de ses coûts avant d'ajouter une dépendance. |
| Diagrammes de flux, séquences, graphes | futur `diagram` | Utile pour le développement. Pour l'instant, code source dans `code` et/ou image raster ; pas de SVG brut ni de moteur Mermaid implicite. |
| Diff de fichiers | futur `diff` | Le texte de diff peut déjà être livré en `code` ; vue côte à côte à considérer sur besoin concret. |
| Cartes et itinéraires | futur `map` | Différé : sources, confidentialité, chargement réseau et accessibilité demandent un contrat explicite. Table de coordonnées et liens explicites en attendant. |
| Présentations, galeries, carrousels | composition future | Plusieurs artefacts ou fichier exporté pour l'instant ; ne pas créer un second système documentaire. |
| Formulaires, cartes d'action, checklists modifiables | interaction future | Différé : nécessite identité d'action, permissions, validation, journal durable et confirmation ; un artefact ne déclenche pas une action. |
| HTML/JS, applications embarquées, SVG arbitraire | non pris en charge | Pas d'iframe arbitraire, `eval` ni `dangerouslySetInnerHTML`. Un fichier HTML peut être téléchargé volontairement, jamais exécuté dans le chat. |
| Météo, finance, tâches, fiches produit | données métier | Composer les types existants ; réserver un type spécialisé à un besoin réel, sans multiplier les widgets ad hoc. |

Cette première palette privilégie des livrables réutilisables sans nouvelle
dépendance de rendu. Elle n'est pas une promesse d'implémentation automatique de
tous les types différés. Utiliser le Markdown ordinaire pour une réponse simple.

## Contrats et exemples

Chaque type structuré accepte `title` et `description` facultatifs. Les champs
inconnus sont refusés. Limites serveur : 300 Ko JSON UTF-8 par payload, titre 300
caractères, description 2000. Préférer un fichier accompagné d'un aperçu au-delà.
Ces données sont enregistrées dans l'historique ; ne pas y inclure de secrets.

Depuis une cellule Pynteract (proxy `agent`) :

```python
await agent.call("artifacts.show_artifact", kind="markdown", payload={
    "title": "Compte rendu", "content": "## Décision\n\nOption **A** retenue."
}, user_feedback="Je présente le compte rendu dans le chat.")
```

Les autres payloads minimaux (`show_artifact` accepte aussi les types médias
existants via `path`, un chemin local de fichier copié dans le bucket authentifié) :

```json
{"kind":"code","payload":{"content":"print('Bonjour')\n","language":"python","filename":"hello.py"}}
{"kind":"table","payload":{"columns":["Option","Coût"],"rows":[["A",12],["B",18]]}}
{"kind":"chart","payload":{"chart_type":"line","labels":["Jan","Fév"],"series":[{"name":"Volume","values":[12,18]}],"unit":"unités"}}
{"kind":"timeline","payload":{"entries":[{"label":"Étape 1","title":"Préparer","detail":"Rassembler les éléments."},{"label":"Étape 2","title":"Vérifier"}]}}
```

- `markdown` / `code` : `content` obligatoire, 100000 caractères maximum.
  Pour `code`, langage par défaut `text` (40 caractères max), nom `snippet.txt`
  (200 max). Les noms d'export ne peuvent pas sélectionner un chemin local.
- `table` : 1–30 colonnes non vides, uniques, étiquettes de 200 caractères max ;
  0–2000 lignes rectangulaires. Cellules string/number/bool/null, nombres finis.
  Pas de HTML ni de liens actifs dans les cellules. Le filtre est local et ne
  modifie pas les données ; le tri numérique conserve les nombres comme nombres.
- `chart` : `chart_type` vaut `bar` (défaut) ou `line` ; 1–200 `labels` (200 caractères
  max), 1–6 `series` avec `name` (1–200 caractères) et `values` numériques finis,
  exactement un par label ; `unit` facultatif, 40 caractères max. Données complètes
  sous le graphique, défilement horizontal si nécessaire ; pas de chargement réseau.
- `timeline` : 1–100 `entries` en ordre d'affichage, avec `label` (100 max), `title`
  (300 max) et `detail` facultatif (2000 max), littéraux. Dates non interprétées.

## Sécurité, persistance et extension

Les modèles, le catalogue et les limites appartiennent à
`the_harness/plugins/artifacts/agent.py`. Le plugin réutilise le service Framework
sans modifier son transport : copie durable des fichiers dans le bucket,
authentification, ordre canonique, relecture après reconnexion/compaction. Les
payloads structurés sont du JSON dans le même historique, pas un magasin parallèle.

Les rendus sont dans `ui/src/components/DataArtifacts.jsx`, enregistrés par
`Artifact.jsx`. Le Markdown conserve ses protections existantes (HTML non exécuté,
KaTeX non fiable), le code est du texte React échappé, les graphiques sont du SVG
construit par l'application à partir de valeurs numériques, jamais du SVG reçu.
Les CSV citent les cellules et neutralisent les chaînes pouvant devenir des
formules de tableur ; les valeurs numériques négatives restent numériques.
Aucun export ou accès presse-papiers n'arrive sans clic humain. Les filtres, tris
et pages sont locaux et réinitialisés à la relecture, sans mutation de l'artefact.

Un type inconnu ou défectueux reste lisible en JSON de secours. Pour un nouveau
type : déclarer un modèle `Artifact`, son payload et son exemple dans le plugin,
puis un renderer et des tests (catalogue → validation → historique → affichage
bureau/mobile). Le Framework propose déjà cette extension ; ne pas dupliquer son
mécanisme. Aucun client connecté ne change la palette annoncée à l'agent.
