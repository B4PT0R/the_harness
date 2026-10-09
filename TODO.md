# The Harness — backlog de la base neutre

Relevé du 10 octobre 2026. Le but est une application canonique de The Framework,
avec une identité configurable, des outils utiles et une composition lisible.
Privilégier les propriétaires clairs et la suppression de code à des adaptateurs.

## Livré dans cette passe

- [x] Ancienne application désinstallée et dépôt archivé dans `~/dev/the_succubus`.
- [x] Données anciennes préservées ; nouveaux chemins `~/.the_harness_assistant`
  et `~/TheHarnessAssistant`, sans import de sessions, mémoire, médias ou secrets.
- [x] Prompts neutres ; suppression des états de personnage, haptique, studios de
  génération spécialisés, webcam, application mobile/VR et bundles associés.
- [x] Interface neutre basée sur le starter, chat/pièces jointes/voix du framework.
- [x] Instructions de mémoire/voix conservées comme politique application, sans
  reconstruction du transport ni contrôleur de plaisir.
- [x] Installation locale sans publication automatique par Tailscale.

## Priorité : frontières et sécurité

- [ ] **Authentification en double — duplication observée.**
  `the_harness/security.py`, `http_boundary.py`, `runtime_composition.py`.
  Politique d'endpoint, middleware et handshake vérifient les credentials par
  des chemins différents. Comparer à la politique Host/Origin stricte du starter,
  définir un propriétaire et éliminer les divergences. Tester les requêtes
  cross-origin, accès par cookie, bearer et transports distants avant extraction.
- [ ] **Secret dans les logs — défaut observé.**
  `the_harness/server_process.py` imprime le descripteur contenant le token local.
  Garder le descripteur privé sur disque, mais ne jamais imprimer son secret dans
  le journal. Test : aucun token ni contenu sensible dans la sortie de démarrage.
- [ ] **Exposition à l'agent versus runtime installé — à examiner.**
  `application.py`, `agent_definition.py`, réglages de plugins.
  Vérifier les outils réellement activés au premier démarrage, leurs prérequis,
  la désactivation pendant une voix et l'isolation des mémoires. Un plugin chargé
  n'est pas une capacité prête ni une autorisation générale d'agir.

## Priorité : simplifier l'application canonique

- [ ] **Bootstrap et chemins — ambiguïté observée.**
  `runtime_paths.py`, `environment.py`, `server_process.py`, `browser_process.py`.
  `THE_HARNESS_MACHINE_ROOT` sélectionne actuellement le dotenv mais n'est pas le
  propriétaire unique de tous les chemins bootstrap. Clarifier l'injection de
  l'instance entière et tester deux instances simultanées, sans accès croisé.
- [ ] **Cycle de vie desktop — assemblage à harmoniser.**
  `server_process.py`, `browser_process.py`, `control.py`, `tray_process.py`,
  `packaging/systemd/`, `scripts/install-services.sh`.
  Comparer à `the_framework/starter/desktop.py`. Séparer supervision serveur,
  navigateur durable et intégration Ubuntu ; ne pas recréer le même cycle de vie
  dans plusieurs scripts. Tester lancement à froid, fermeture, restart, UI prête
  tardivement et changement majeur du Python système.
- [ ] **Client distant restant — simplification possible.**
  `plugins/client_remote/{api,composition,policy,service}.py`, `client_mode.py`.
  Beaucoup de code reste côté app alors que le transport est générique. Cartographier
  ce qui relève de la lib, de l'autorisation produit et du client. La base livrée
  fournit les APIs de pairing ; elle n'inclut pas l'ancienne UI mobile/distante.
  Décider explicitement quelles surfaces distantes sont souhaitées avant refonte.
- [ ] **Notifications et présence UI — point à vérifier.**
  `plugins/desktop_notifications/service.py`, interface et application bridge.
  La nouvelle UI utilise le flux d'événements, alors que la suppression de notices
  se base sur `application.connected`. Vérifier la présence réelle de l'interface
  avant d'adapter la politique ; éviter de relier les notices au seul client distant.

## Interface et identité — ensuite, pas pendant l'audit

- [ ] **Identité visuelle commune — demande de Baptiste.** Créer une nouvelle
  icône neutre pour le tray, le lanceur/dash desktop et les applications mobile/Quest
  lorsqu'elles seront réintroduites. Prévoir une source commune et des déclinaisons
  adaptées aux plateformes : silhouette lisible à petite taille, variante symbolique
  pour le tray, fonds et marges adaptés aux icônes de lancement. Vérifier le rendu
  réel sur fond clair/sombre ; l'icône provisoire actuelle n'est pas l'identité finale.
- [ ] **Palette sobre — demande de Baptiste.** Réorienter les interfaces vers des
  gris anthracite et un accent bleu électrique, avec des tokens de couleur communs
  pour fonds, surfaces, texte, actions, focus et états. Réserver l'accent aux éléments
  utiles, vérifier contraste et lisibilité, et comparer les captures des principales
  vues dans les mêmes conditions. Cette identité appartient à l'application ; le
  framework doit permettre de la configurer sans imposer cette palette aux autres apps.
- [ ] Personnalité/instructions utilisateur configurables sans modifier le code,
  sans reconstituer un personnage imposé. Même politique en texte et en voix.
- [ ] Restaurer un rendu Markdown/code/math adapté au travail, avec liens sûrs et
  validation visuelle. L'interface de base affiche actuellement du texte brut.
- [ ] Harmoniser les derniers libellés des réglages, l'affichage des activités/outils
  et les erreurs. Vérifier desktop/mobile, densité, clavier et thèmes avant retouches.
- [ ] Ajouter une entrée réellement utilisable pour les surfaces/aperçus/rollback ;
  la logique existe dans le framework, mais doit être compréhensible côté app.
- [ ] Réévaluer `turn_timing.py` : mesure utile ou état durable supplémentaire sans
  utilisateur ? Garder uniquement si sa valeur justifie son coût.

## Vérifications et limites de la passe

- [ ] Test d'inférence et voix réels avec le backend choisi ; les tests isolés ne
  garantissent pas la disponibilité du modèle ou des credentials.
- [ ] Installation/autostart de la nouvelle version après revue ; seuls un serveur
  de test isolé et l'interface compilée sont utilisés pendant cette passe.
- [ ] Choisir une stratégie de versions framework/application et un dépôt distant
  pour la base neutre. Ne pas pousser vers l'ancien projet par défaut.
