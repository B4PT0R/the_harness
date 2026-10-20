# Notifications et alarmes Android, téléphone en veille

Étude et preuve technique du 20 octobre 2026, pour The Harness.
**Statut actuel : réception privée directe implémentée dans les sources et l’APK
0.1.4, en complément du lot local 0.1.3. Backend de ce nouveau lot non rechargé ;
validation réelle Samsung/Tailscale en attente. Aucun fournisseur push externe.**
Aucun téléphone réel sollicité, aucune sonnerie, aucun compte externe créé,
aucune exposition réseau ni modification du serveur en service pour ce nouveau lot.

## Deuxième lot — réception privée par instance, 20 octobre 2026

Décision de Baptiste : chaque Harness reste autonome et privé, modulo Tailscale.
**Aucun relais commun, Firebase ou compte/service supplémentaire imposé.** Cette
décision remplace la préférence FCM formulée dans l’étude initiale conservée ci-dessous.

- Réutilisation de l’association et du bearer natif chiffré ; WebSocket
  `GET /remote/v1/notifications`, sous-protocole `harness-notifications-v1`,
  authentification dans le second sous-protocole (jamais dans l’URL ni le JS).
  Route limitée à l’accès privé et aux clients mobiles associés ; révocation
  et désactivation utilisent le registre de connexions existant.
- Framework : journal atomique privé `remote-notifications.json`, 256 signaux
  `message`/`alarm` sans texte de conversation, identité et curseur persistés.
  Reprise après redémarrage, déduplication et reset explicite hors fenêtre.
  Échec d’écriture : pas d’avancement du curseur visible. Le journal n’est pas
  une preuve d’affichage ni un acquittement humain.
- Android : service `specialUse` activé volontairement via **Réception privée**,
  notification permanente silencieuse avec état et bouton **Arrêter** ; maintien
  hors ligne, reconnexion avec recul exponentiel borné et retour réseau.
  Aucun VPN embarqué, aucun wake lock permanent, aucune permission batterie
  accordée automatiquement. Un refus d’accès arrête le récepteur.
- Curseur partagé entre réception et synchronisation HTTP ; rejeu silencieux sans
  doublon, indication générique si le journal est dépassé. Les signaux d’alarme
  ne font pas sonner un ancien événement reconnecté : le moteur local reste
  responsable des échéances connues. Les alertes locales existantes sont conservées.
- Arrêter la réception laisse les alertes locales actives. Désactiver les alertes
  ou déconnecter le téléphone arrête aussi la réception. Relance au démarrage/mise
  à jour tentée seulement si activée, sous réserve des restrictions Android.

### Validation de ce lot

- Harness : **246 tests réussis** sur l’état final (suite complète) ;
  58 tests ciblés d’accès distant, notifications et sécurité réussis également.
- Android : compilation debug/instrumentation, tests unitaires et lint réussis ;
  **neuf tests instrumentés réussis, zéro ignoré**, API 35, émulateur `-no-audio`.
  Activation, absence d’association, statut permanent, maintien hors réseau,
  arrêt par notification et reprise/déduplication du curseur sont couverts.
  Le test hors ligne coupe puis restaure Wi-Fi/data uniquement dans l’émulateur.
- Framework : **869 tests réussis, 4 ignorés** (suite general + agentic), dont
  persistance/reprise, permissions privées et échec disque. Le premier essai avait
  six échecs de navigateur dus au chemin Playwright du laboratoire ; relance
  complète réussie avec le cache Chromium installé, sans changement applicatif.
- **Non validé : chaîne complète via Tailscale réel, Samsung en veille, autonomie,
  reprise réelle après redémarrage, sonnerie.** Aucun téléphone installé, aucun
  backend redémarré, aucune configuration Tailscale modifiée pour ce lot.
- Signature APK 0.1.4 vérifiée identique à celle de 0.1.3 ; pas besoin de
  désinstaller pour mettre à jour. Panneau natif inspecté visuellement et émulateur
  fermé après les essais. Commits locaux seulement, aucun push.

Une connexion native persistante reste du meilleur effort : aucune promesse de
réception instantanée pendant Doze ou après arrêt forcé. Les essais historiques
ci-dessous ne prouvent pas la fiabilité du nouveau récepteur intégré.

## Historique : premier lot et étude initiale

Les sections suivantes décrivent les étapes et options étudiées avant la décision
privée ci-dessus ; leurs recommandations de fournisseur ne sont plus le plan actuel.

## Premier lot intégré — 20 octobre 2026

- Le plugin scheduler du Framework persiste les attentes de réponse ou
  d’acquittement, leurs échéances et reçus. Une expiration ou un ACK reprend la
  conversation canonique avec le contexte et la criticité ; aucune escalade
  automatique, aucun acquittement assimilé à une tâche terminée.
- Les routes natives authentifiées `GET /remote/v1/alerts` et
  `POST /remote/v1/alerts/receipt` projettent les prochaines occurrences et
  enregistrent les reçus sous l’identité de l’appareil associé, jamais celle du
  corps de la requête. Le contexte privé de décision n’est pas envoyé au mobile.
- Android : activation volontaire via le menu **Alertes locales et alarmes**,
  autorisation notifications et accès spécial aux alarmes exactes. Cache local,
  AlarmManager, receiver de redémarrage/changement d’heure, notifications natives
  silencieuses pour les rappels ; canal sonore uniquement pour les alarmes
  explicitement demandées. Pas de plein écran, ni d’ouverture du microphone.
- Une alarme est présentée par une notification répétée et arrêtable, bornée à
  60 secondes, pas par un service audio permanent. Le réglage du canal appartient
  à Android/utilisateur. Le banc silencieux ne valide pas l’audio réel.
- Acquittement hors ligne mis en file ; heure de réception serveur conservée,
  sans prétendre prouver une lecture ou une réception à l’heure initiale.
- Chargement sur sept jours, prochaine occurrence seulement pour les séries.
  Une projection tronquée conserve l’ancien cache plutôt que d’annuler à tort.
  Les récurrences restent gérées par le serveur, pas recalculées sur le mobile.
- Synchronisation au premier plan et par JobScheduler (15 minutes au mieux,
  différable par Android). Les messages imprévus restent donc **sans garantie
  d’arrivée immédiate**. Hors ligne, les alarmes déjà chargées fonctionnent,
  mais une modification/annulation serveur ne peut pas encore les retirer.
- Le menu affiche autorisations, dernière synchronisation et reçus en attente.
  Déconnexion/désactivation annule le cache local. La révocation distante ne
  peut être constatée par un téléphone hors ligne qu’au prochain accès serveur.

Les tests et la compilation sont séparés de l’activation du serveur et de
l’installation volontaire de l’APK. Aucune sonnerie ni manipulation du téléphone
physique n’a été utilisée pour ce lot. Ne pas traiter ce prototype comme l’unique
réveil d’une situation critique.

## Validation du lot intégré

- Framework : 866 tests réussis, 4 ignorés (suite general + agentic).
- Harness : 244 tests réussis (suite complète).
- Android : compilation, tests unitaires et lint réussis ; cinq tests
  instrumentés API 35 réussis, zéro ignoré, avec émulateur `-no-audio`.
  Affichage silencieux/déduplication, ACK hors ligne, absence de remise en file
  des reçus déjà transmis, désactivation et écran de diagnostic sont couverts.
  L’accès exact est accordé uniquement dans le laboratoire jetable ; une alarme
  du lendemain est armée puis annulée, jamais déclenchée. Aucun test audio/WebView
  microphone exécuté dans ce lot. Capture du panneau natif inspectée.
- APK 0.1.3 : même certificat SHA-256 que l’APK 0.1.2 précédemment livré ; la mise
  à jour ne demande pas de désinstallation. L’installation sur Samsung et le
  déclenchement sonore restent à valider avec accord explicite.

## Conclusion de l’étude initiale

Deux besoins demandent deux chemins complémentaires :

1. **Une échéance connue à l’avance doit être armée nativement sur le téléphone.**
   Le réveil ne doit pas dépendre d’un WebSocket, de Tailscale, du serveur ou
   d’une génération de texte au moment de sonner.
2. **Une interpellation imprévue du serveur demande un vrai transport push.**
   Pour un Samsung Android avec Google Play Services, FCM est mon premier choix
   pragmatique, sous réserve d’accord sur la dépendance Google. Il ne remplace
   jamais le chemin local pour un réveil à heure fixe.

L’application reste un hôte léger de notre interface partagée : ajouter une petite
couche Android pour la réception, les notifications et les alarmes ; ne pas réécrire
le chat et ne pas lancer un deuxième assistant sur le téléphone.

Le premier lot recommandé, désormais implémenté, est **local, sans Google ni nouveau service** : armer,
afficher, arrêter et annuler une alarme native, avec statut explicite du téléphone.
Le transport push vient ensuite, après décision sur sa confidentialité et son coût
opérationnel. Les rappels existants restent des messages : cette étude n’autorise
pas leur transformation en alarmes sonores.

## État initial étudié (avant l’implémentation, APK 0.1.2)

- Android : API minimale 26, compilation/cible 34, Java 17, APK 0.1.2.
- `android/app/src/main/java/app/theharness/mobile/MainActivity.java` : WebView,
  association privée, fichiers, microphone ; canal `harnessScreen` limité à
  l’origine associée et à la fenêtre principale, seulement pour garder l’écran
  éveillé pendant une conversation vocale au premier plan.
- `AndroidManifest.xml` ne déclare ni notifications, ni alarmes exactes, ni
  réception au démarrage. Aucun receiver/service natif d’alerte n’existe.
- `CredentialStore.java` garde le bearer chiffré avec Android Keystore, hors JS.
- `the_harness/plugins/client_remote/api.py` expose déjà
  `GET /remote/v1/notifications/wait`, authentifié par appareil associé.
- Le Framework, `server/clients/remote.py`, distingue `message` et `alarm` :
  l’alarme vient de `CommandAccepted` pour un `scheduled_alarm`, sans attendre la
  réponse finale ; le message suit la réponse. Ces signaux ne contiennent pas
  le texte privé. Journal et déduplication sont bornés et en mémoire, pas une
  boîte de réception durable avec accusé de réception par appareil.
- Le scheduler persiste les intentions côté serveur et gère déjà les horaires
  locaux/DST. Il déclenche un tour d’agent ; ce n’est pas un réveil Android.

**Un signal serveur existant n’est donc pas une notification affichée, encore
moins une sonnerie entendue sur un téléphone en veille.**

## Pourquoi une connexion permanente ne suffit pas

Doze suspend l’accès réseau et diffère les travaux ordinaires. Garder la WebView
active, lancer un minuteur JS, utiliser WorkManager à l’heure précise ou garder
un long-poll ne fournit pas le contrat recherché. Un service au premier plan et
une exemption batterie ne sont pas, à eux seuls, une garantie de réseau disponible.
Le téléphone, le VPN et le réseau ont aussi leur propre cycle de vie. [1]

Réserver les alarmes exactes aux horaires réellement importants pour l’utilisateur.
`setExactAndAllowWhileIdle()` convient à un rappel local précis pendant la veille,
mais est soumis à des restrictions de fréquence ; `setAlarmClock()` correspond au
vrai réveil visible du système, qui peut sortir du mode basse consommation. [1, 2]
`setAlarmClock()` programme un déclenchement : **il ne joue pas une sonnerie à lui
seul**. Le receiver doit déclencher notre présentation et, pour une vraie alarme,
un service audio borné et arrêtable.

## Preuve silencieuse exécutée

Laboratoire jetable indépendant : `app.theharness.alarmlab`, sans permission réseau,
sans WebView, sans son. Émulateur `harness_api35` (Android API 35), cible APK 34.

L’accès aux alarmes exactes a été accordé par `adb appops` : le parcours de
consentement utilisateur n’a pas été testé. Pour chaque essai : programmer à
+20 secondes, terminer l’activité, tuer le processus par `am kill` (pas
`force-stop`), simuler batterie débranchée, éteindre
l’écran, demander Doze, puis lire la trace persistée par un receiver explicite.
Le receiver n’effectue qu’une écriture des timestamps et du PID.

| API testée | État observé | Résultat avant la sortie forcée de Doze |
| --- | --- | --- |
| `setExact(RTC_WAKEUP)` | `IDLE` confirmé | Pas de déclenchement pendant la fenêtre observée, contrôle négatif |
| `setExactAndAllowWhileIdle(RTC_WAKEUP)` | `IDLE` confirmé | Receiver recréé, retard mesuré **122 ms** |
| `setAlarmClock()` | Doze profond refusé à l’approche du réveil (`INACTIVE`/`ACTIVE`) | Receiver recréé, retard mesuré **92 ms** |

Dans les trois cas le processus avait effectivement disparu avant le déclenchement.
L’absence de permission réseau rend ces essais indépendants d’Internet. Le cas
`setAlarmClock()` n’est **pas** un essai dans un état `IDLE` maintenu : sa prévention
de la veille profonde près du réveil fait précisément partie du comportement observé.

Limites : un échantillon par mode, fenêtre courte, émulateur seulement ; ce ne sont
ni des garanties de latence, ni un test d’une nuit entière, ni une validation
Samsung. Aucun service audio, plein écran ou transport push testé. Le contrôle
négatif ne prouve pas à lui seul le délai exact de livraison après sortie de veille.

Les sources du laboratoire, le pilote et le JSON brut sont archivés séparément
avec cette étude ; aucun de ces composants expérimentaux n’entre dans l’APK.

## Architecture proposée

### A. Notification ordinaire

Canal Android distinct, son bref/vibration selon les réglages de Baptiste,
confidentialité sur l’écran verrouillé, toucher pour ouvrir le chat associé.
Pas de microphone, pas de voix automatique, pas de lecture répétée ni de
plein écran simplement pour capter l’attention.

Les paramètres effectifs du canal restent sous contrôle de l’utilisateur ; l’app
ne doit pas les réinitialiser en recréant des canaux. [3]

### B. Réveil / alarme explicite

Pour un vrai réveil : `AlarmManager.setAlarmClock()` avec `PendingIntent`
immuable et explicite vers un receiver non exporté. Pour les rappels précis non
assimilables à un réveil : choisir `setExactAndAllowWhileIdle()` seulement si
justifié, sinon une planification moins stricte.

À l’échéance : charger la fiche locale, vérifier identité/version/annulation,
publier une notification de catégorie alarme et démarrer la sonnerie native.
Service au premier plan de type `mediaPlayback` pendant la sonnerie seulement,
audio avec usage alarme, contrôle de focus audio, arrêt temporisé, bouton
**Arrêter**, éventuellement **Reporter** après accord sur sa durée.
Ne pas exiger une connexion serveur pour arrêter une sonnerie.

Un plein écran est une capacité séparée : vérifier
`NotificationManager.canUseFullScreenIntent()` à partir d’API 34 et offrir les
réglages appropriés. S’il est refusé, afficher honnêtement le mode disponible,
pas promettre d’allumer l’écran de la même façon. [4]
Le démarrage d’un service depuis l’arrière-plan est encadré ; l’alarme exacte
répondant à une action demandée est une exemption documentée, pas une permission
pour maintenir un service de polling permanent. [5, 6]

Ne pas monter le volume système, contourner silencieusement « Ne pas déranger »,
ouvrir la caméra ou démarrer un appel. Vérifier volume d’alarme et réglages DND
avec Baptiste lors du test réel. Un téléphone éteint, une application arrêtée de
force ou des permissions retirées sont hors garantie.

### C. Synchronisation, sans deuxième source de vérité

Le scheduler demeure propriétaire des engagements. Ajouter une **projection
explicite d’alertes pour l’appareil**, distincte des instructions libres pour l’agent.
Un prompt comme « vérifier si déjà fait et rappeler gentiment » n’est pas une
commande native exécutable hors ligne.

Contrat minimal envisagé, à valider lors de l’implémentation :

```text
alert_id, revision, occurrence_at (offset UTC), kind (message|alarm),
title public, expires_at (limite de livraison tardive), cancelled
```

- Occurrence logique stable indépendante des tentatives de livraison serveur ;
  ne pas utiliser un identifiant incluant le compteur de retry comme seule clé.
- Le téléphone conserve les occurrences effectivement armées et leur version,
  annule/remplace les anciennes, et accuse réception de l’armement.
- Ne pas prendre « accepté par le serveur », « armé sur le téléphone », « déclenché »,
  « arrêté » et « vu par Baptiste » pour le même événement.
- Une notification livrée ou arrêtée ne termine jamais automatiquement une tâche.
- Une photo des prochaines occurrences suffit pour le premier lot ; horizon
  fini et visible, par exemple sept jours, plutôt qu’un second moteur de récurrence.
  Après cet horizon sans synchro, aucune nouvelle garantie. Le fuseau du rappel
  reste celui choisi, pas implicitement celui du téléphone en déplacement.
- Une annulation faite ailleurs pendant que le téléphone est hors ligne ne peut
  pas être instantanément connue de celui-ci. Afficher les annulations non
  synchronisées ; ne jamais prétendre le contraire.
- Révocation serveur et effacement à distance d’alarmes locales hors ligne sont
  également distincts. La déconnexion locale efface nos alarmes natives.

Côté code : couche native Android pour l’exécution ; projection et route authentifiée
avec la politique `client_remote` ; mécanisme de notification réutilisable dans le
Framework seulement là où son contrat partagé manque. Ne pas détourner le callback
unique de notifications actuellement utilisé par le bureau, ni ajouter un second
flux de chat. Le chargement historique élimine déjà un ancien champ
`notification_registration` : ne pas réintroduire ce nom sans revoir ce chemin.

### D. Réception distante imprévue : choix du transport

| Option | Intérêt | Coût / limite | Décision proposée |
| --- | --- | --- | --- |
| **FCM** | Canal Android prévu pour réveiller un appareil en veille ; pas de socket permanente dans notre app | Google Play Services, configuration Firebase et identifiants serveur ; livraison non garantie à heure fixe | Premier choix pour le Samsung si Google accepté |
| **UnifiedPush** | Alternative ouverte, chiffrement Web Push documenté, distributeur mutualisable | App distributeur et service de push supplémentaires ; comportement veille dépend du distributeur/terminal | Alternative réelle si refus de Google, à tester sur deux distributeurs comme conseillé par le projet |
| **ntfy auto-hébergé** | Possibilité de preuve rapide avec app existante ; maintenance serveur séparée | Son mode « instant » repose sur un service permanent ; son Firebase Android concerne ntfy.sh, pas arbitrairement notre serveur privé | Pas une garantie gratuite ajoutée à Tailscale ; ne pas déployer par défaut |
| **Notre long-poll / WebSocket seul** | Réutilise le transport privé existant | Aucun mécanisme de réveil réseau robuste à lui seul en Doze | Utile quand connecté, pas le socle d’un réveil |
| **App Horloge Android** | `ACTION_SET_ALARM` délègue le réveil au composant déjà installé | UI/action système, identité et synchronisation/annulation ne correspondent pas à notre scheduler | Bon raccourci si besoin immédiat d’un simple réveil ; pas le moteur général des rappels |

Sources : Android/FCM [1, 7], projets UnifiedPush/ntfy [8, 9], intents Horloge [10].
Les choix de ce tableau sont une appréciation d’architecture, pas un benchmark
comparatif de fiabilité des fournisseurs.

Pour FCM : priorité haute réservée aux événements visibles urgents ; afficher une
notification locale générique immédiatement, sans devoir charger une page via
Tailscale avant de montrer quoi que ce soit. Les messages haute priorité peuvent
être rétrogradés s’ils ne donnent pas lieu à du contenu visible ; temps de traitement
et accès réseau sont limités. [7]

Le corps de conversation et le bearer d’association ne doivent pas transiter par
le fournisseur. Transporter un identifiant opaque et une catégorie suffit pour
une notification générique ; obtenir le contenu dans le canal privé ensuite.
Pour un futur déclenchement sonore distant, prévoir validation d’authenticité,
anti-rejeu, déduplication et expiration courte : un vieux push reconnecté des
heures plus tard ne doit pas déclencher une sonnerie. Aucun fournisseur ni clé
externe n’a été configuré pour cette étude.

## Permissions et état observable

Les demander au moment d’activer la fonction, avec une explication, pas toutes
au premier lancement. Ne jamais qualifier une alarme de prête sur la seule base
d’un retour HTTP.

- `POST_NOTIFICATIONS`, runtime API 33+, et vérification du canal. [11]
- `SCHEDULE_EXACT_ALARM`, accès spécial API 31+ : préférer ce consentement explicite
  à `USE_EXACT_ALARM` pour cet assistant polyvalent ; vérifier
  `canScheduleExactAlarms()`. Recontrôler au retour des réglages. [2]
- `USE_FULL_SCREEN_INTENT` seulement pour la vraie fonction alarme et avec état
  effectif vérifié. Le refus du plein écran n’est pas un refus du son. [4]
- `FOREGROUND_SERVICE` et, selon cible/API, `FOREGROUND_SERVICE_MEDIA_PLAYBACK`,
  uniquement pour la phase de sonnerie. [5]
- `RECEIVE_BOOT_COMPLETED` pour reconstruire les alarmes depuis le stockage local.
  Pour fonctionner après reboot **avant le premier déverrouillage**, il faut
  aussi Direct Boot : receiver adapté et minimum de données en stockage
  device-protected. Ne pas déplacer notre bearer dans ce stockage. [2, 12]
- Exemption batterie/Samsung seulement si les tests révèlent un besoin, accompagnée
  d’explications ; ni désactivation globale ni garantie automatique.

Diagnostic lisible : notifications autorisées, canal disponible, alarmes exactes
permises, plein écran permis, prochaine alarme armée, horizon local, dernière
synchro. Toute panne doit apparaître comme « non armé » ou « mode dégradé ».

## Plan d’intégration et critères de réception

1. **Moteur local** : stockage des fiches, notification, receiver, sonnerie bornée,
   arrêt local, permissions et diagnostic ; aucun compte externe requis.
2. **Projection scheduler → appareil** : version, accusé d’armement, annulation,
   déduplication, reprise ; aucune conversion implicite des messages en alarmes.
3. **Transport distant** : choisir FCM ou UnifiedPush, puis intégrer et éprouver.
4. **Validation réelle Samsung** : essai sonore très court avec Baptiste éveillé,
   puis essai de longue veille avant d’employer la fonction comme réveil principal.

Matrice minimale :

- écran allumé / verrouillé / éteint ; veille courte puis plusieurs heures ;
- Doze forcé et naturel, batterie économisée, Wi-Fi et réseau mobile ;
- processus tué normalement vs arrêt forcé explicite (cas hors garantie) ;
- serveur et Tailscale indisponibles au moment d’une échéance déjà armée ;
- refus puis révocation de chaque permission ; canal et volume à zéro ; DND ;
- reboot avant/après déverrouillage, mise à jour APK, changement d’heure/fuseau ;
- modification/annulation, occurrence répétée, retry serveur et push en double ;
- reconnexion tardive : conserver le rappel utile, ne pas rejouer une vieille alarme ;
- arrêter/reporter sans réseau, déconnexion locale, révocation de l’appareil ;
- vérifier une seule alerte si l’occurrence arrive à la fois par miroir local et push.

### Vérifications exécutées sur l’existant

- Harness : 21 tests d’accès distant et notifications bureau réussis.
- Framework : 51 tests scheduler réussis.
- Android : tâches Gradle `testDebugUnitTest` et `lintDebug` réussies
  (résultats majoritairement à jour depuis le dernier build).
- Laboratoire : compilation réussie et trois essais API 35 décrits plus haut.

Ce sont des vérifications de l’étude et de l’état existant, **pas des tests
end-to-end d’une fonction déjà livrée**. Aucun APK de production modifié ou
installé, aucun build d’interface publié, aucun redémarrage serveur effectué.

## Sources primaires consultées le 20 octobre 2026

1. Android — Doze/App Standby : https://developer.android.com/training/monitoring-device-state/doze-standby
2. Android — Alarmes : https://developer.android.com/develop/background-work/services/alarms
3. Android — Canaux de notifications : https://developer.android.com/develop/ui/views/notifications/channels
4. AOSP — Limites des full-screen intents : https://source.android.com/docs/core/permissions/fsi-limits
5. Android — Types de foreground services : https://developer.android.com/develop/background-work/services/fgs/service-types
6. Android — Démarrage des FGS en arrière-plan : https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
7. Firebase — Priorités et traitement Android : https://firebase.google.com/docs/cloud-messaging/android/message-priority
8. UnifiedPush — Architecture, intégration et chiffrement : https://unifiedpush.org/developers/intro/
9. ntfy — App mobile et instant delivery : https://docs.ntfy.sh/subscribe/phone/
10. Android — Intents courants, Horloge : https://developer.android.com/guide/components/intents-common
11. Android — Permission de notification : https://developer.android.com/develop/ui/views/notifications/notification-permission
12. Android — Direct Boot : https://developer.android.com/privacy-and-security/direct-boot

Documentation Samsung envisagée mais accès HTTP refusé (403) : aucune affirmation
spécifique au modèle/à One UI n’en est déduite. Le modèle exact et sa version
Android devront être relevés lors de la validation avec Baptiste.
