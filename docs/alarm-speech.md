# Messages vocaux d’alarme — Android 0.1.7

## Contrat

Une alarme native peut choisir un fichier vocal à la place de la sonnerie système.
Le fichier est synthétisé **sur le serveur avec Piper**, sans lecture immédiate,
publié dans le bucket authentifié, puis téléchargé dans le stockage privé Android
avant l’échéance. La lecture ne dépend ni de la WebView ni du réseau à cette échéance.
Aucun fournisseur push, moteur vocal Android, permission ou service permanent supplémentaire.

1. `tts.prepare_alarm_audio(text)` prend les mots exacts à dire et renvoie `audio_src`.
   Cet outil ne présente pas de lecteur, ne joue rien et ne programme rien.
2. Passer cette référence à `scheduler.create_wake(delivery="alarm", audio_src=...)`,
   ponctuel ou récurrent, ou à `create_wait` dans `alert.audio_src` avec `kind="alarm"`.
3. Le téléphone doit avoir les alertes activées, les autorisations natives nécessaires
   et synchroniser avant l’heure prévue. Pour une attente avec acquittement, les reçus
   `audio_ready` / `audio_unavailable` indiquent respectivement la mise en cache et son
   échec. Ce ne sont jamais des preuves d’écoute ni un acquittement humain.
4. `update_wake(audio_src="")` restaure la sonnerie ; `null` laisse le choix inchangé.
   Une référence vocale avec une livraison silencieuse `message` est refusée.

Le message se répète comme la sonnerie existante, jusqu’à arrêt/acquittement ou au
plafond de trois minutes. Les volumes système d’alarme et les restrictions Android
restent applicables ; le curseur TTS de la WebView ne contrôle pas une alarme native.
Une voix manquante ou illisible laisse jouer la **sonnerie de secours**, avec reçu
`audio_unavailable` pour les attentes natives. Deux alarmes ne superposent pas leurs
voix : la plus récente prend la main ; l’autre reprend si elle n’est ni arrêtée ni expirée.
L’expiration ne prolonge jamais le plafond de l’autre occurrence.

Les fichiers ne peuvent venir que du bucket du serveur associé, avec son bearer natif
et sans redirection. Aucun secret dans l’URL, aucune URL externe arbitraire. Limites :
8 Mio et trois minutes par fichier, 64 Mio de cache privé. Les références du bucket
sont immuables : créer un nouveau fichier pour changer les mots. Le cache est élagué
selon le calendrier ; désactiver les alertes le vide. Les fichiers du bucket suivent
le stockage normal des ressources de conversation, pas le nettoyage du cache mobile.
L’armement et les annulations précèdent le préchargement. Chaque synchronisation
limite celui-ci à quatre téléchargements et un budget de vingt secondes (une
lecture réseau déjà bloquée peut encore durer six secondes). Le reste attend
une synchronisation ultérieure ; une référence non prête utilise la sonnerie.

## Message immédiat, téléphone endormi

**Pas de nouvelle garantie de lecture immédiate en veille profonde.** Notre connexion
privée persistante reste du meilleur effort et n’est pas un push système. Il ne faut
pas transformer un message ordinaire ou une reconnexion tardive en alarme sonore.
Le TTS direct existant reste destiné au client actif ; cette option native concerne
les alarmes connues et préchargées. Une alarme créée trop tard peut ne pas être
synchronisée à temps. Aucun contournement Doze, dérogation batterie automatique,
relais externe ou wake lock permanent n’est ajouté.

Références officielles Android à consulter pour les limites de plateforme :
- https://developer.android.com/training/monitoring-device-state/doze-standby
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- https://developer.android.com/develop/background-work/services/fgs/service-types#media

## Validation et activation

Voir le compte rendu de livraison dans `mobile-alerts.md`. Les tests instrumentés
sont réservés à un émulateur lancé avec `-no-audio`. Une compilation ne prouve ni
l’installation sur le téléphone, ni le fonctionnement sur un Samsung endormi.
L’APK et le backend doivent tous deux être actualisés ; aucun test sonore du téléphone
ni installation réelle ne doit être déduit des vérifications de laboratoire.
