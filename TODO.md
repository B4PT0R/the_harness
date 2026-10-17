# The Harness — backlog de la base neutre

Relevé du 10 octobre 2026. Le but est une application canonique de The Framework,
avec une identité configurable, des outils utiles et une composition lisible.
Privilégier les propriétaires clairs et la suppression de code à des adaptateurs.

## Remarques à reprendre après l'audit en cours — 17 octobre 2026

- [ ] **Simplifier le parcours CLI de création et lancement.** Le bootstrap du
  Framework copie actuellement le starter puis laisse l'installation npm,
  Chromium, le build et le lancement à effectuer séparément. Viser un parcours
  évident, avec environnement Python propre à l'application, préparation
  reprenable et diagnostic des prérequis. Intégrer cette proposition à l'audit
  des primitives ; implémentation dans un lot ultérieur.
- [x] **Ouverture du navigateur local rétablie.** Le daemon avait accumulé 337
  pilotes Node/Playwright et atteint sa limite de descripteurs (1019 ouverts,
  limite souple de 1024). `BrowserSession` dans le Framework nettoie désormais
  les échecs et annulations de lancement, sérialise start/stop et ignore les
  événements tardifs d'un ancien contexte. Tests de régression et quatre vrais
  lancements échoués sans processus enfant restant. Seul le service navigateur
  a été redémarré ; serveur et identifiant de conversation conservés. Ouverture
  et rendu contrôlés, fonctionnement confirmé par Baptiste. Après reprise :
  un pilote et 11 descripteurs pour le daemon.
- [x] **Stabiliser la langue des tests navigateur.** État de départ de l'audit :
  `uv run pytest -q` donne 137 succès et 6 échecs, tous en attente d'un bouton
  « Réglages ». Cause confirmée sur le même montage de test : navigateur en
  `en-US`, bouton « Settings » présent, puis bouton « Réglages » disponible après
  sélection explicite du français. La fixture fixe désormais `fr-FR` pour rendre
  les scénarios déterministes ; la suite Python complète passe.
  Ne pas assimiler ces échecs à la panne d'ouverture de l'installation.

Pour la refonte envisagée, Baptiste accepte les ruptures des API Python du
Framework et l'adaptation coordonnée du Harness. Ne pas conserver des couches de
compatibilité sans consommateur réel ; préserver la conversation et les données.

- [x] **Premier lot d'assemblage partagé — 17 octobre.** Le starter et le Harness
  utilisent `ApplicationSpec.build_conversation` pour le socle conversationnel.
  `server_process` délègue la création du superviseur ; contexte à entrées fixes,
  options par plugin et vue en lecture seule des services démarrés. Proxies de
  construction pour la voix et la sécurité distante retirés, paramètres sans
  consommateur supprimés. Validation : 600 tests Framework, 144 tests Harness,
  tests et builds JavaScript des deux interfaces. Scénario Chromium réel du
  starter : redémarrage, historique, aperçu, publication et rollback. Instance
  installée redémarrée avec conversation et processus navigateur conservés.
- [x] **Reconnexion sans alerte périmée.** Le client efface seulement l'erreur
  de déconnexion lorsque le worker répond de nouveau, en conservant les erreurs
  d'envoi. Régression navigateur et aperçu réel après restart, avec brouillon
  préservé et même conversation. Interface vérifiée puis publiée localement,
  avec version précédente disponible pour rollback.

## Livré dans cette passe

- [x] Ancienne application désinstallée et dépôt archivé dans `~/dev/the_succubus`.
- [x] Données anciennes préservées ; nouveaux chemins `~/.the_harness_assistant`
  et `~/TheHarness`, sans import de sessions, mémoire, médias ou secrets.
  Ancien runtime renommé `~/TheSuccubus` ; première instance neutre
  `~/TheHarnessAssistant` supprimée à la demande de Baptiste.
- [x] Prompts neutres ; suppression des états de personnage, haptique, studios de
  génération spécialisés, webcam, application mobile/VR et bundles associés.
- [x] Prompts spécialisés rétablis à partir de `the_succubus` et adaptés : rôle,
  continuité héritée/récente, compression, inventaire exhaustif, intégration mémoire,
  provenance, couverture finale et critères de complétion. Sans présupposés de
  l’ancienne application ; tests du contenu et du câblage réel des spécialistes.
- [x] Interface neutre basée sur le starter, chat/pièces jointes/voix du framework.
- [x] Instructions de mémoire/voix conservées comme politique application, sans
  reconstruction du transport ni contrôleur de plaisir.
- [x] Installation locale sans publication automatique par Tailscale.

## Priorité : frontières et sécurité

- [x] **Authentification en double — consolidée.**
  `the_harness/security.py`, `http_boundary.py`, `runtime_composition.py`.
  `HarnessSecurityPolicy` possède les credentials locaux, clients distants,
  scopes et allowlist desktop. Le middleware délègue l'authentification et protège
  les montages privés ; les endpoints déclaratifs du Framework appliquent leur
  auth/scope. HTTP et WebSocket locaux/distants partagent la frontière Host/Origin
  loopback. Les Origins natifs explicites exigent un bearer sur les sockets locaux,
  jamais un cookie. CORS et exceptions d'anciennes surfaces retirés. Tests couvrant
  Host/Origin, cookies, bearer, scopes, pairing/révocation et WebSocket.
  L'exposition hors loopback reste non supportée par cette base.
- [x] **Secret dans les logs — corrigé et vérifié.**
  `the_harness/server_process.py` imprime le descripteur contenant le token local.
  Le descripteur reste privé sur disque ; la sortie de démarrage se limite à
  host/port/pid. Absence du token vérifiée dans les logs isolés et le journal systemd.
- [ ] **Exposition à l'agent versus runtime installé — à examiner.**
  `application.py`, `agent_definition.py`, réglages de plugins.
  Vérifier les outils réellement activés au premier démarrage, leurs prérequis,
  la désactivation pendant une voix et l'isolation des mémoires. Un plugin chargé
  n'est pas une capacité prête ni une autorisation générale d'agir.

## Priorité : simplifier l'application canonique

- [x] **Bootstrap et chemins — résolution centralisée.**
  Racine machine explicite, puis environnement, puis défaut installé ; session
  explicite isolée sauf surcharge. Serveur, navigateur, contrôle et dotenv
  partagent cette sélection. Les tests couvrent les racines distinctes et le
  déplacement des données ; les instances personnalisées ne peuvent pas piloter
  les unités installées. Un test multiprocessus couvre deux serveurs et deux
  daemons navigateur isolés, leurs credentials et leur nettoyage.
- [ ] **Cycle de vie desktop — assemblage à harmoniser.**
  `server_process.py`, `browser_process.py`, `control.py`, `tray_process.py`,
  `packaging/systemd/`, `scripts/install-services.sh`.
  Comparaison avec `the_framework/starter/desktop.py` faite : systemd possède ici
  les processus, le serveur possède les workers et le navigateur reste indépendant.
  Compilation initiale ordonnée avant le serveur ; readiness exige un état sain ;
  ouverture réessayée sur 503 et absence de release signalée sans ouvrir de fenêtre.
  Arrêt SIGTERM nettoie le descripteur malgré le replay de signal d'Uvicorn.
  Tests : deux instances réelles, credentials non croisés, remplacement serveur,
  navigateur conservé, doublon refusé, fermeture et attente bornée.
  Restent la session Ubuntu complète (launcher/tray/fermeture de fenêtre), une UI
  compilée tardivement en vrai et le changement majeur du Python système.
- [ ] **Client distant restant — simplification possible.**
  `plugins/client_remote/{api,composition,policy,service}.py`, `client_mode.py`.
  Beaucoup de code reste côté app alors que le transport est générique. Cartographier
  ce qui relève de la lib, de l'autorisation produit et du client. La base livrée
  fournit les APIs de pairing ; elle n'inclut pas l'ancienne UI mobile/distante.
  Décider explicitement quelles surfaces distantes sont souhaitées avant refonte.
  Premier lot livré : suppression des projecteurs sans consommateurs et de la
  branche de révocation vocale inactive ; état `assistant: {}` conservé sans
  snapshots worker inutiles. Soumissions locales/distantes via le même ingress
  du framework, injecté par la capacité `conversation.ingress`. Reçus idempotents,
  protocoles et filtrage des chemins locaux préservés et testés. L'API distante
  et ses permissions restent côté application ; frontière HTTP/WebSocket désormais
  harmonisée avec les contrats de sécurité du Framework.
  Objectif confirmé par Baptiste : un nouveau client mobile sera développé pour
  le Harness actuel. Adapter plutôt que supprimer en bloc : préserver les bases
  utiles (pairing, transports, permissions, ingress et composition), sans figer
  les anciens contrats ni restaurer l'ancienne UI.
  `/remote-ui/` était le client mobile de l'ancienne application, pas une surface
  actuelle. Le contrôle indique désormais ce mode comme indisponible et refuse
  start/open/restart sans démarrer de services ni naviguer ; configuration et
  bases de pairing préservées pour le futur client.
- [x] **Notifications et présence UI — transport canonique raccordé.**
  Les notices utilisent `canonical_transport.event_connection_count`, plutôt que
  `application.connected`. Les clients distants restent indépendants ; connexion
  ne signifie pas visibilité ou attention. Tests des sockets locaux et distants.

- [x] **Robustesse des paramètres de notifications.**
  `_load` vérifie que le JSON est un objet : sinon, avertissement et valeurs par
  défaut sans écraser le fichier. Tests des valeurs non-objets, du JSON malformé
  et des préférences valides.

## Interface et identité

- [x] Pandora comme personnalité par défaut, commune au texte et à la voix.
  Instructions d'architecture partagées : framework stable et général, harness
  évolutif, auto-modification contrôlée et continuité de session préservée.

- [x] **Identité visuelle commune — livrée.** Nouvelle
  icône neutre pour le tray, le lanceur/dash desktop et les applications mobile/Quest
  lorsqu'elles seront réintroduites. Prévoir une source commune et des déclinaisons
  adaptées aux plateformes : silhouette lisible à petite taille, variante symbolique
  pour le tray, fonds et marges adaptés aux icônes de lancement. Vérifier le rendu
  réel sur fond clair/sombre. Source commune dans `scripts/build-icons.py`, SVG et
  PNG 512 px ; variante transparente de tray. Mobile/Quest : assets prêts, clients
  natifs toujours absents de cette base.
- [x] Socle UI partagé `@the-harness/ui` : shell, conversation, saisie, réglages,
  icônes et cycle de vie client séparés de l'entrée desktop. Banque FR/EN pour
  les labels, infobulles, noms accessibles et erreurs locales ; langue persistante.
  Textes d'ambiance retirés.
- [x] **Palette sobre — livrée et vérifiée.** Interfaces avec des
  gris anthracite et un accent bleu électrique. `ui/src/theme.css` centralise aussi
  typographie, espacements, rayons et dimensions ; `style.css` consomme les tokens
  communs
  pour fonds, surfaces, texte, actions, focus et états. Réserver l'accent aux éléments
  utiles, vérifier contraste et lisibilité, et comparer les captures des principales
  vues dans les mêmes conditions. Cette identité appartient à l'application ; le
  framework doit permettre de la configurer sans imposer cette palette aux autres apps.
- [x] Personnalité/instructions utilisateur configurables dans les réglages,
  sans reconstituer un personnage imposé. Même politique en texte et en voix.
- [x] Rendu Markdown/code/math restauré, sans HTML brut et avec liens sûrs.
  Validation sur une réponse réelle du backend et captures desktop/mobile.
- [x] Réglages : distinguer accès de l’agente et service actif, expliquer les
  prérequis et autorisations, désactiver les changements concurrents de binding.
  Erreurs HTTP non-JSON et réponses invalides traduites sans erreur de parsing brute.
  Tests JavaScript et navigateur ; interface publiée vérifiée sur bureau/petit écran.
- [x] Réglages plein écran avec sidebar verticale : Général, Conversation,
  Capacités, Interface, Avancé et Données. État des sections et brouillon de chat
  préservés ; retour clavier avec focus restauré, erreurs d’enregistrement visibles.
  Rendu bureau/petit écran vérifié ; 124 tests Python et 38 tests JS réussis.
- [x] Gestion des versions d’interface dans les réglages : construire, ouvrir
  l’aperçu, publier et revenir en arrière avec confirmation. Compilation annulable,
  même après réouverture ; état de compilation exposé par le framework.
  Tests des confirmations et de l’annulation sur bureau/petit écran.
- [ ] Vérification d’ensemble des activités/outils, navigation clavier et thèmes
  supplémentaires avant une nouvelle passe visuelle ; pas de refonte sans besoin.
- [x] Chargeurs JSON du mode client et du timing : documents non-objets traités
  sans AttributeError ni écrasement. Configuration client invalide refusée
  explicitement ; timing auxiliaire invalide ignoré. Tests de régression.
- [x] `turn_timing.py` conservé : middleware applicatif limité aux prompts,
  utilisé par le contexte live pour distinguer continuité et retour après absence.
  Écriture hors event loop et lecture auxiliaire tolérante déjà testées.

## Vérifications et limites de la passe

- [x] Finitions du 10 octobre : descripteur serveur JSON non-objet et ports booléens
  refusés sans suppression du fichier ; message de désinstallation corrigé.
  Framework : 578 tests réussis, 4 ignorés. Harness : 121 tests Python et 38 tests
  JavaScript réussis ; build production valide. Serveur redémarré sous supervision,
  santé vérifiée et nouvelle interface prévisualisée puis publiée localement.

- [x] Inférence réelle, pièce jointe texte et outil Bash vérifiés avec le backend.
  Modèle initial `gpt-5.5`, confirmé dans son catalogue et par une réponse réelle.
  Connexion/arrêt WebRTC réels vérifiés avec microphone simulé.
- [ ] Essai vocal humain pour apprécier micro physique, écoute et qualité audio.
- [x] Services neutres installés après tests et activés au démarrage. Santé worker,
  ouverture UI et redémarrage serveur avec navigateur préservé vérifiés. Anciennes
  données intactes ; aucune publication réseau hors loopback.
- [ ] Choisir une stratégie de versions framework/application et un dépôt distant
  pour la base neutre. Ne pas pousser vers l'ancien projet par défaut.
