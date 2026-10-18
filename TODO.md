# The Harness — backlog de la base neutre

Relevé du 10 octobre 2026. Le but est une application canonique de The Framework,
avec une identité configurable, des outils utiles et une composition lisible.
Privilégier les propriétaires clairs et la suppression de code à des adaptateurs.

## Remarques à reprendre après l'audit en cours — 17 octobre 2026

- [x] **Sessions canoniques et activité des sous-agents — 18 octobre.** Le Framework
  peut héberger plusieurs workers indépendants. Le Harness garde sa conversation
  par défaut, mais stocke désormais ses réglages, état d'extensions et bindings
  dans la session ; magasins parallèles et callbacks de persistance retirés.
  L'activité des sous-agents est étiquetée séparément, sans fusionner les historiques.
  Validation : 156 tests Harness, 54 JS, build et contrôle visuel ; Framework
  659 succès, 3 skips. Migration locale ponctuelle exécutée puis supprimée ;
  même session, même historique, mêmes réglages et fenêtre Chromium conservée.
- [x] **Vocabulaire d'événements Framework propre — 18 octobre.** Convertir
  ou filtrer les événements Responses à la frontière backend ; compléter LocalEvent
  pour que les consommateurs ne dépendent plus des signaux OpenAI verbatim.
  Livré : texte/raisonnement/outils, progression et délégations vocales normalisés ;
  le plugin Realtime déclare ses propres événements de cycle de vie. Interface et
  clients distants consomment le contrat Framework, sans fallback backend.
  Tests Framework/Harness, JS et builds réussis ; scénario visuel de streaming
  puis commit sans doublon. Serveur et UI installés mis à jour, même session,
  historique/archives JSON inchangés et fenêtre Chromium conservée.

- [x] **Livraison des surfaces et contrôles agentiques — 18 octobre.** Le service
  de surfaces initialise les bundles déclarés ; le Harness retire son chemin
  de secours dupliqué. Candidat persisté, publication/rollback explicites, copie
  atomique des versions et priorité à une version connue. Les contrôles ont été
  retirés des réglages à la demande de Baptiste, avec composant/CSS/traductions
  et anciens tests UI supprimés ; outils conservés dans `system`, état disponible
  via `system.surfaces`. Interface inspectée sur bureau/mobile et publiée sur
  l'installation ; même conversation, candidat retrouvé après restart et rollback
  disponible. Chaque device peut avoir sa propre surface, maintenue par l'agent :
  test desktop/mobile/Quest sur trois sources et historiques indépendants.
- [x] **Assemblage du client distant compacté — 18 octobre.** La fabrique serveur
  construit directement service et API, après collecte de toutes les contributions.
  Classe `RemoteClientAssembly`, état intermédiaire et fichier `composition.py`
  retirés ; l'API lit les protocoles et le runtime du service au lieu de les répéter
  en paramètres. Politiques/projections et personnalisation vocale restent produit ;
  aucune nouvelle primitive Framework. Contributions avant/après le plugin,
  permissions figées, pairing, authentification, révocation et reçus texte/voix testés.
  Validation : 153 tests Harness, 15 contrats Framework, 46 tests JS et build.
  Serveur installé redémarré : conversation, navigateur et clients appairés conservés.
- [x] **Chat intégré à l’hôte — 18 octobre.** `build_conversation()` fournit
  texte, pièces jointes et ingress partagé avec la voix ; plugin `CHAT` retiré
  du Harness et du starter. Clients distants injectés sur le même service, sans
  capacité artificielle. Aucun changement des routes ou du format de session.
  Installation redémarrée et UI publiée après aperçu ; même session et navigateur.
  Validation texte/voix, pièces jointes et clients distants ; suite Harness :
  151 succès, 46 tests JS et build.
- [x] **Aperçus authentifiés et desktop principal unique — 18 octobre.**
  `system.preview_surface` ouvre un onglet web privé par ticket unique, sans
  déplacer le desktop ni recopier ses cookies. Rôle lecture seule, badge explicite,
  brouillons/navigation testables mais écritures/voix/bridge refusés. Une seule
  connexion primaire aux événements ; aperçus concurrents sans effet sur la présence
  desktop ni les notifications. Cookie signé conservé au restart. Contrats partagés
  Framework/starter/Harness, scénarios Chromium réels et essai sur l'installation :
  même conversation et même onglet principal pendant l'aperçu. Validation :
  640 tests Framework, 151 Harness, suites JS et builds des deux interfaces.
- [x] **Suivi d’image intermittent corrigé — 18 octobre.** Un scroll peut être
  livré après l’agrandissement du contenu par l’image, avant son événement load.
  La distance au bas ne suffit donc pas à déduire un départ dans l’historique :
  le suivi se désactive sur un déplacement vers le haut et se réactive près du bas.
  Correction commune Harness/starter, sans affaiblir les garanties existantes.
  Test durable reproduisant cet ordre d’événements : rouge avant, vert après.
  Chargement immédiat/retardé et lecture de l’historique couverts ; suite Harness
  complète : 155 succès, puis 20 répétitions ciblées réussies (essai temporaire
  supprimé). Suites JS 53/25 et builds réussis, récupération navigateur
  du starter vérifiée. Interface publiée après aperçu ; historique, navigateur
  principal et brouillon conservés.
- [x] **Identifiants DOM du navigateur agentique.** Captures désormais remplacées
  intégralement avec identifiants opaques et invalidation des anciennes références.
  Test Chromium sur nœuds cachés/tronqués ; parcours Réglages/Retour vérifié dans
  le navigateur installé le 18 octobre, sans ambiguïté de sélecteur.

- [x] **Parcours CLI de création et lancement — 18 octobre.** Le Framework prépare
  désormais l'environnement Python propre à l'application, Chromium, npm et UI
  dès `bootstrap` ; `--run` permet le lancement immédiat. Commandes `prepare`
  reprenable et `run`, diagnostic uv/Node/npm, reconstruction de l'UI éditée.
  Huit tests CLI/wheel, 621 tests Framework et essai réel hors dépôt avec chemins
  contenant des espaces ; aucun appel d'inférence pour cette validation.
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

- [x] **Artefacts natifs — 18 octobre.** Plugin partagé `ARTIFACTS` assemblé dans
  le Harness et le starter. Sorties d'outils/commandes persistées dans la session,
  sorties de providers temporaires pour le tour courant, sans persistance.
  Images vision exclues du chat ; artefacts image/fichier rendus, widgets par
  renderers applicatifs et fallback isolé. Copies durables authentifiées, route
  accessible aux clients desktop déjà autorisés. Tests de replay, renouvellement
  éphémère et résilience du chat ; aucune seconde timeline à maintenir.
  Validation : 146 tests Python Harness, 46 tests JS, build et contrôle visuel ;
  version activée localement après aperçu. Serveur redémarré avec même session
  et même révision, navigateur conservé ; précédente interface disponible.

- [x] **Bucket serveur commun — 18 octobre.** Toutes les nouvelles pièces jointes
  et publications partagent `data_root/bucket/`, sans racine distincte par type.
  Route authentifiée `/api/v1/bucket/...`, sous-dossiers et lecture par plages,
  accessible aux clients desktop distants autorisés. État privé hors bucket ;
  session limitée aux références et métadonnées. Baptiste précise que les données
  de test actuelles sont jetables : pas de migration ni d'alias de compatibilité.
  Si une migration est explicitement nécessaire ultérieurement, utiliser un script
  ponctuel dans `migrations/`, supprimable après exécution ; jamais dans le runtime.
  Validation : 616 tests Framework et scénario réel starter ; 132 tests backend
  Harness et test d'accès distant. Installation redémarrée ; lecture HTTP locale
  authentifiée avec Range validée sur un fichier temporaire du bucket nettoyé ensuite.
  Le défaut de défilement observé alors est corrigé dans la tranche dédiée ci-dessus.

- [x] **Suivi du bas lors du chargement d'une image — 18 octobre.** L'ajustement
  est maintenant un effet de layout, exécuté avant l'affichage et les événements
  de scroll, au lieu d'un effet passif susceptible de perdre `follow.current`.
  Même correction dans le starter. Tests Chromium avec chargement immédiat ou
  retardé, conservation de la position pendant la lecture de l'historique et
  reprise du suivi au retour en bas. Suite Harness : 150 succès avec la matrice
  chargement immédiat/retardé ; tests/builds JS et rendu vérifiés. Correction
  activée localement après aperçu, avec version précédente disponible. La course
  résiduelle scroll/load est corrigée dans la tranche dédiée ci-dessus.

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
- [x] **Bindings et voix — cohérence validée le 18 octobre.** Runtime installé,
  exposition à l'agent et contexte vocal restent distincts. Les changements rares
  de binding ferment/recréent l'appel avec la projection actuelle, sans retrait
  fictif d'un contexte déjà transmis au modèle. Providers mémoire/registre filtrés,
  producteurs nettoyés, tours vocaux réconciliés et relance corrélée au client.
  Arrêt manuel prioritaire ; voix désactivée sans relance ; appels périmés ignorés.
  Les dernières transcriptions acceptées restent enregistrables par le worker
  canonique après désactivation de la voix.
  Worker réel pour le changement depuis un outil suspendu, transport audio simulé
  pour la relance navigateur avec brouillon/historique conservés. Validation :
  654 tests Framework, 153 Harness réussis et un échec intermittent de suivi
  d’image à corriger ensuite ; 25/53 tests JS et builds réussis. Les services chargés
  ne garantissent toujours pas la disponibilité des fournisseurs externes.

## Priorité : simplifier l'application canonique

- [x] **Bootstrap et chemins — résolution centralisée.**
  Racine machine explicite, puis environnement, puis défaut installé ; session
  explicite isolée sauf surcharge. Serveur, navigateur, contrôle et dotenv
  partagent cette sélection. Les tests couvrent les racines distinctes et le
  déplacement des données ; les instances personnalisées ne peuvent pas piloter
  les unités installées. Un test multiprocessus couvre deux serveurs et deux
  daemons navigateur isolés, leurs credentials et leur nettoyage.
- [x] **Cycle de vie desktop — assemblage partagé le 18 octobre.**
  `server_process.py` délègue verrou, socket, découverte, credentials et arrêt
  à `LocalServer`, également utilisé par le starter. Le navigateur conserve son
  processus indépendant et son contexte RPC possède explicitement Chromium.
  systemd reste le superviseur du Harness, sans nouvelle couche de supervision.
  Remplacement serveur sur la même adresse : conversation, cookie navigateur,
  page et brouillon conservés ; tests avec vrais processus et Chromium isolé.
  Validation : 626 tests Framework, 148 tests Harness et reprise Chromium des
  deux applications. Installation locale redémarrée : même conversation, même
  processus/onglets navigateur, même port et token de contrôle renouvelé.
- [ ] **Compléments d'intégration Ubuntu.** Session desktop complète
  (launcher/tray/fermeture de fenêtre), UI compilée tardivement en vrai et
  changement majeur du Python système. Ces essais manuels restent distincts
  de l'assemblage et de la continuité maintenant couverts automatiquement.
- [ ] **Clients distants — surfaces et autorité à concevoir.**
  `plugins/client_remote/{api,server,policy,service}.py`, `client_mode.py`.
  Assemblage nettoyé ; permissions et protocoles produit restent côté application.
  La base livrée
  fournit les APIs de pairing ; elle n'inclut pas l'ancienne UI mobile/distante.
  Décider explicitement quelles surfaces distantes sont souhaitées avant refonte.
  Premier lot livré : suppression des projecteurs sans consommateurs et de la
  branche de révocation vocale inactive ; état `assistant: {}` conservé sans
  snapshots worker inutiles. Soumissions locales/distantes via le même ingress
  du framework, injecté par le service `chat` de l’hôte conversationnel. Reçus idempotents,
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
  Les notices utilisent `canonical_transport.primary_event_connection_count`, plutôt que
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

- [x] **Fermeture bloquée d'un aperçu — 18 octobre.** Bug Chromium/Playwright
  reproduit en faisant courir reload et close : acquittement natif sans fermeture,
  puis retries ordinaires bloqués même après navigation. Traces protocole locales
  et source Playwright cohérentes avec le bug amont #42068. Le Framework reprend
  désormais le seul onglet via une autre commande native et attend sa fermeture ;
  chaque tentative est bornée, échec explicite si nécessaire. Aucun reset global
  des autres onglets ou de la conversation. Essai avec le runtime du Harness :
  30 cycles réussis, dont 29 fermetures récupérées ; autre onglet et brouillon
  conservés. Déclencheur exact de l'ancien aperçu non prouvable après sa disparition.
  Référence : https://github.com/microsoft/playwright/issues/42068.
  Validation : 691 tests Framework réussis (3 skips), 157 Harness ; Chromium
  visible 10 blocages/10 reprises. Correction activée dans le daemon installé,
  trois aperçus authentifiés rechargés puis fermés, session et brouillon conservés.
  Commit Framework : f44b75d.

- [x] **Trois prérequis avant refonte API — 18 octobre.** Références navigateur
  corrigées, XML mémoire sorti de Realtime et migration de profils retirée,
  factories de services optionnels dégradables sans perdre le chat (y compris
  sessions supplémentaires). Framework : 687 succès, 3 skips ; Harness : 157.
  Serveur et navigateur installés actualisés. Conversation, archive, configuration
  et bindings conservés ; aucun changement des payloads ni du code UI.

- [x] **Première tranche API Application — 18 octobre.** Définition réutilisable
  Application et unique build public, hôte ApplicationHost distinct du pilote
  SessionRuntime. HarnessSession personnalise ce dernier ; session_factory et
  session_extensions explicitent la construction par session. Le canal de capacités
  est bridge des deux côtés ; schémas de session, événements et protocoles inchangés.
  Starter/Harness/docs adaptés sans alias ou migration. 694 tests Framework réussis
  (3 skips), 157 Harness. Serveur installé actualisé, JSON de session strictement
  identique, même processus navigateur ; catalogue et aperçu authentifié vérifiés.

- [ ] **Périmètre API précisé : une application active.** Baptiste ne demande pas
  plusieurs instances simultanées de la même app. Simplifier la prochaine tranche
  dans ce sens : sessions et clients multiples conservés, construction/reprise
  fiables, aucun vocabulaire ou couche dédié aux copies concurrentes de l'app.
  Définition importable par les workers sans démarrage serveur toujours nécessaire.
