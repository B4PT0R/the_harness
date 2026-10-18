# The Harness — backlog de la base neutre

- [x] **Redémarrage de secours indépendant du worker — 18 octobre.** L'API HTTP
  répondait mais les requêtes d'état/historique du worker expiraient ; le contrôle
  attendait alors la préparation gracieuse sans limite. Ajouter une sonde worker
  courte et une préparation bornée, puis permettre la récupération systemd en cas
  de panne réseau, timeout ou erreur serveur. Garder les erreurs d'authentification
  explicites. Récupération effectuée, agent reparti ; aucune nouvelle relance
  pendant son travail. Correctif du contrôle validé sur scénarios de panne isolés.
- [ ] **Isoler le blocage initial worker/relais — 18 octobre vers 18 h 22.**
  Barrière Realtime expirée à la fermeture, puis délais sur l'état et l'historique
  malgré un HTTP vivant ; le worker exécutait encore des outils. La récupération
  ne prouve pas l'origine de ce blocage. Examiner en priorité les tâches du relais
  et ses observateurs si cela se reproduit, sans interrompre un agent occupé.

- [x] **Continuité vocale sur redémarrage et publication UI — 18 octobre.**
  Pause de l'entrée, fin du tour vocal et des délégations, fermeture de l'appel
  puis drainage canonique avant remplacement. L'onglet conserve son intention
  vocale et reprend après reconnexion ; arrêt explicite prioritaire, aperçus
  exclus. Reprise des délégations du plugin system raccordée au service Realtime.
  Validation : Framework 756 succès / 4 skips, Harness 167 succès / 1 skip,
  tests JS et builds des deux interfaces ; véritable WebRTC avec audio après
  rechargement UI et remplacement serveur. Installation actualisée, conversation,
  réglages et fenêtre Chromium conservés lors du redémarrage contrôlé.

- [x] **Fermeture du navigateur interactif — 18 octobre.** La déconnexion native
  du contexte précède la sortie réelle de Chromium : arrêter Playwright à cet
  instant pouvait provoquer un SIGKILL avant l'écriture du profil. Le Framework
  attend désormais le processus via psutil, puis libère le pilote ; réouverture
  et annulation RPC respectent ce nettoyage. Tests : 760 Framework / 167 Harness,
  cycles natifs réels avec les deux versions Chromium installées, cookies et chat
  indépendant conservés. Propriétaire navigateur installé relancé, ancien crash
  acquitté par Chromium, profil vérifié Normal et conversation conservée.

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

- [x] **Application unique et singleton — 18 octobre.** Application porte désormais
  configuration et ressources ; ApplicationHost et les copies par session retirés.
  Application.current() n'est disponible que pendant le lifespan du serveur,
  avec libération après arrêt, échec ou annulation et exclusion des démarrages
  concurrents. Imports workers inertes. Sessions multiples explicites et isolées,
  aucun current_session global. BuildContext.application et les endpoints voient
  le même propriétaire ; HarnessSession reçoit ses services depuis le Framework.
  Starter et documentation alignés. Payloads et protocoles inchangés.
  Validation : 699 tests Framework réussis (3 skips), 157 Harness ; Ruff critique
  et diff vérifiés. Installation relancée : même navigateur, JSON de session
  conservé hors reçu technique du redémarrage ; chat, historique et contrôles retrouvés,
  aperçu authentifié ouvert/fermé. Le bridge de capacités n'est pas l'indicateur
  de connexion du chat.
- [x] **Plugins et BuildContext — 18 octobre.** Factories plates recevant contexte
  et services injectés ; références différées gardant les imports workers inertes.
  Services/API distants, fichiers locaux et UI déclarés directement ; notifications
  gardent leur contribution de politique avant construction. Découverte uniforme
  des routes/socket sur le service construit, sans flag "service". Starter aligné
  sur les défauts des plugins ; aucune nouvelle classe ou helper public, pas de
  changement des payloads. Documentation et exemples Framework mis à jour.
  Validation : Framework 704 succès / 3 skips avec Chromium et 6 tests ciblés
  d'injection ; Harness 157 succès. Le test de notifications utilise désormais
  un seul serveur/boucle pour ses deux sockets. Installation relancée : même
  navigateur et conversation, contrôles chat/voix, settings fichiers, catalogue
  et aperçu authentifié vérifiés.
- [ ] **Suite de la revue API.** Examiner AgentSpec / AgentTrigger / WorkerProfile,
  en distinguant déclaration, runtime et payloads. Les modèles de payloads restent
  hors refonte. La frontière Session / Context / Compaction est désormais livrée.

- [x] **Revue Session / Context / Compaction — 18 octobre.** Contrats et usages
  Framework/starter/Harness examinés ; détail dans le TODO Framework. Conserver
  Session canonique et ses mutations atomiques, Context comme préparation du modèle,
  projections UI/voix distinctes. Priorité proposée : déplacer la conversion Responses
  hors de Session vers Context, y réunir l'orchestration de compaction et retirer
  le contrôleur Compaction distinct ainsi que ses branches sans usage utile.
  Les recettes starter/Harness n'appellent pas ces objets directement ; leurs
  projections et commandes worker restent les points de vérification. Aucun nouveau
  manager, ni refonte de payload ou schéma proposée. 44 tests ciblés réussis ;
  revue seulement, aucun changement runtime ni redémarrage installé.

- [x] **Contexte et compaction unifiés — 18 octobre.** Context prépare l'entrée
  canonique et orchestre la compaction via agent.compact(), sans contrôleur distinct.
  Projection pure dans Context ; Session garde données et mutations atomiques.
  Schémas, événements, archive UI et projection voix inchangés. Providers réservés
  à la génération, jamais évalués pour la compaction. Recettes starter/Harness
  conservées sans ajout de câblage ; documentation alignée.
  Validation : Framework 708 succès / 3 skips avec Chromium, Harness 157 succès,
  51 tests ciblés finaux. Installation relancée : navigateur et conversation conservés,
  chat reconnecté, contrôles de voix disponibles, santé et 13 plugins vérifiés.
  Aucun appel payant au backend pour compacter la conversation réelle ni publication UI.

- [x] **Revue AgentSpec / AgentTrigger / WorkerProfile — 18 octobre.** Conserver
  déclaration, trigger et payload wire distincts. Priorité : corriger et centraliser
  la résolution du lancement ; un profil résolu peut actuellement être écrasé par
  les défauts AgentResources (reproduction isolée sans backend). Ensuite retirer
  les profils wire de la déclaration simple et constituer un catalogue final après
  chargement des extensions, en préservant la configuration dynamique de Jiminy.
  Simplifier les alias call/submit et publish/dispatch du registre sans prétendre
  que call attend un résultat. 89 tests ciblés réussis ; détail dans le TODO
  Framework. Revue seulement, aucun changement de runtime ou installation.
- [x] **Déclarations et lancement des spécialistes — 18 octobre.** Priorité de
  configuration corrigée : déclaration < ressources < profil résolu < session
  sauvegardée. Recette Python et payload wire distincts, factories et initializers
  préservés. Profils compilés sortis d'AgentSpec ; un catalogue final produit après
  chargement/configuration des extensions, y compris bindings désactivés et spécialistes
  explicites sans trigger. Alias call/publish retirés, submit/dispatch conservés.
  Documentation starter/Framework/Harness alignée. Payloads et protocoles inchangés.
  Validation : Framework 711 succès / 3 skips avec Chromium, Harness 157 succès,
  117 tests ciblés ; installation relancée, navigateur et conversation conservés,
  contrôles chat/voix disponibles et Jiminy conforme à la configuration mémoire.

- [x] **Revue transversale de l'API — 18 octobre.** Architecture et vocabulaire
  central désormais cohérents ; garder les frontières et propriétaires actuels.
  Priorités recommandées : défauts statiques du starter dans AgentSpec.configuration,
  projection chat standard portée par l'hôte (sans import Worker dans la recette),
  reset résolu sur HarnessSession sans répéter reset_handler à l'assemblage.
  Garder indisponible un reset sans politique explicite ; préserver transactions,
  voix, pagination et artefacts. La factory de ressources du Harness reste utile
  pour l'environnement, ses politiques distantes et sa santé restent applicatives.
  31 tests de composition/sessions/voix/bootstrap réussis. Détails dans TODO Framework.
  Revue seulement, aucun changement runtime ou redémarrage de l'installation.
- [x] **Finitions de la recette nominale.** Les réglages statiques du starter
  passent dans AgentSpec.configuration. SessionProjections fournit les vues
  standard full/display/remote, avec display par défaut pour le chat. Suppression
  du câblage des projections et de reset_handler dans le Harness : l'API appelle
  directement HarnessSession.reset_session. Sans politique applicative, reset
  indisponible (501), même avec une transaction bas niveau. Les choix sélectifs,
  hooks voix et formats de payload restent inchangés. Documentation alignée.
  Validation : Framework 712 succès / 3 skips avec Chromium, Harness 157 succès ;
  redémarrage réel sans changement de navigateur/fenêtre ni perte de conversation,
  chat/voix disponibles et Jiminy conforme au modèle mémoire enregistré.


- [x] **Contributions serveur et services partagés — 18 octobre.** Plugins
  déclarés par server_extensions ; configure(context) réservé aux contributions
  avant construction. Notifications : déclaration statique et configure séparés.
  API distante sur la vue activity, indépendante du type de client. Les services
  application sont empruntés sans reprise de leur cycle de vie par les sessions ;
  vues de lookup et santé restent cohérentes. CLI starter avec vérifications réelles
  Python/Chromium avant installation, et prepare explicite pour rafraîchir.
  Décorateurs de déclaration disponibles ensemble à la racine. Documentation et
  tests adaptés ; payloads, persistance et garanties texte/voix inchangés.

  Validation de cette tranche : Framework 719 succès / 3 skips et Harness 157 succès.
  Bootstrap neuf puis préparation sans réinstallation/rebuild, démarrage UI et arrêt
  réel vérifiés. Installation Harness relancée avec même navigateur et conversation,
  contrôles chat/voix disponibles, Jiminy conforme à la configuration mémoire.


- [x] **UI desktop conventionnelle — 18 octobre.** Le starter ne déclare plus de
  surface : ui/ voisin du module application suffit, avec main/npm build/dist et
  /ui. surfaces=() désactive explicitement l'UI. ClientSurface fournit les valeurs
  desktop usuelles ; le Harness conserve seulement ses paramètres spécifiques de
  build, artefact, route serveur et délai, sans répéter nom/routes/shell/rétention.
  Les surfaces mobiles/Quest explicites et les aperçus authentifiés sont conservés.

  Validation : Framework 722 succès / 3 skips et Harness 157 succès ; starter neuf
  sans déclaration de surface démarré jusqu'au navigateur connecté. Installation
  Harness relancée sans perte de navigateur ni conversation ; contrôles chat/voix
  disponibles et configuration canonique de Jiminy préservée.


- [x] **Catalogue d'agents et session par défaut — 18 octobre.** Application.agents
  remplace primary_agent ; le statut par défaut appartient à une session identifiée.
  Le worker reprend sa recette canonique et plusieurs sessions peuvent partager
  une même spec. Services et routes de conversation sont isolés pour toutes les
  sessions, y compris celle par défaut ; fermeture/reprise sans arrêter les
  services partagés ni les autres workers. La frontière HTTP reste globale.
  Starter et Harness adaptés ensemble, sans alias ni migration des payloads.

  Vérifications : Framework 724 succès / 3 skips et Harness 157 succès ;
  starter neuf préparé et lancé jusqu'au
  rendu Chromium connecté, puis arrêté proprement. Installation Harness relancée
  avec même navigateur/fenêtre, conversation conservée, chat/voix disponibles,
  13 plugins et configuration mémoire canonique vérifiés.


- [x] **Durée de vie portée par la session — 18 octobre.** La recette Pandora ne
  déclare plus session_mode. Le Framework construit une Session explicite avant
  d'appliquer AgentSpec ; stockage et conservation du contexte sont indépendants.
  Les triggers décident du mode de leur session spécialiste, avec le même format
  WorkerProfile à la frontière des processus. La conversation Harness reste
  durable par défaut ; aucun changement du JSON canonique ni migration.

  Validation : Harness 157 succès ; starter neuf préparé, navigateur connecté puis
  arrêté proprement. Framework 725 succès / 3 skips. Installation Harness relancée avec
  même navigateur/fenêtre, conversation canonique inchangée, contrôles chat/voix,
  13 plugins et configuration mémoire de Jiminy vérifiés.


- [x] **Politique de session explicite et persistée — 18 octobre.** retain_history
  est maintenant un champ canonique sauvegardé et restauré à la reprise. Le chemin
  reste runtime ; durable et retain_history remplacent les modes dans les triggers,
  profils worker, CLI, superviseur et assemblage. Les retries de spécialistes suivent
  la rétention effective annoncée par WorkerReady, même si leurs défauts ont changé.
  Aucune migration runtime ni alias de l'ancien vocabulaire.

  Validation : Framework 728 succès / 3 skips, puis 35 tests ciblés réussis incluant
  2 nouveaux cas de retries sur politique restaurée ; Harness 157 succès. Starter
  neuf préparé sans installations au second passage, rendu Chromium connecté et
  arrêt propre vérifiés. Installation relancée avec même navigateur/fenêtre,
  conversation conservée et champ retain_history=True sauvegardé ; contrôles
  texte/voix, 13 plugins et configuration mémoire de Jiminy vérifiés.


- [x] **Mise au propre pour publication expérimentale — 18 octobre.** Recettes
  d'agent séparées de l'orchestration ; politiques de Jiminy portées par son trigger.
  Factories de ressources avec répertoire explicite, chargement d'environnement
  et timing adaptés sans faux chemins de session. Frontière publique mémoire
  réduite aux primitives utiles. Assemblage/routes du Framework simplifiés sans
  nouvelle couche de managers ; intégration texte/voix via le build standard.
  Invocations privées explicites et triggers découverts partagent un catalogue ;
  requêtes nominatives indépendantes des abonnements aux événements ambiants.

  Validation finale : Framework 733 succès / 3 tests live optionnels ignorés ;
  Harness 157 succès. JS : 28 tests starter et 54 Harness, deux builds réussis.
  Sdist/wheel construits et installés hors checkout avec dépendances publiques ;
  starter préparé deux fois et lancé jusqu'à Chromium connecté, arrêt propre.
  Installation relancée avec même navigateur/fenêtre et conversation conservée ;
  contrôles texte/voix, 13 plugins et configuration mémoire Jiminy vérifiés.
  Aucun push ni publication.

## Marqueurs de contexte du mode vocal

- [x] Après la séparation de l’affichage voix/délégation, persister des messages
  developer marquant le début et la fin de chaque appel vocal. Les agents texte
  et vocal doivent recevoir ces transitions dans leur contexte canonique, y
  compris après reprise. Garder un propriétaire clair et des écritures idempotentes.
