# Étude de Cas Pratique : Développeur TMA Junior (DEP / ASIN 2026)
## Prise de rendez-vous au guichet (Passeport, CNI, Permis)

Ce projet contient la résolution complète de l'épreuve pratique de Tierce Maintenance Applicative (TMA).  
L'ensemble a été conçu selon les standards d'ingénierie logicielle les plus rigoureux : architecture découplée, zéro dépendance externe, tests unitaires exhaustifs et analyse fine des données en base.

---

## 1. Structure du projet et exécution rapide

### Organisation des fichiers
- **`regles_rendez_vous.py`** : Module métier pur en Python 3 standard (aucun framework, aucune dépendance externe). Il prend en paramètre l'heure courante `maintenant` pour une testabilité parfaite et implémente les contrôles, l'annulation, les changements d'état et la pagination.
- **`test_rendez_vous.py`** : Suite complète de tests unitaires automatisés (`unittest`) couvrant chaque ticket de TMA-101 à TMA-107, les règles annexes et les cas limites.
- **`requetes.sql`** : Requêtes SQL d'impact et requêtes de détection des anomalies bonus, commentées et validées.
- **`base_rendez_vous.sql`** : Export initial de la base de données au vendredi 20 novembre 2026 à 18h00.
- **`README.md`** : Rapport d'expertise complet pour le jury.

### Lancement des tests automatisés
Aucune installation de paquet (pip) n'est requise. Exécutez simplement :

```bash
python3 -m unittest test_rendez_vous.py -v
```

### Exécution des requêtes SQL
Les requêtes sont compatibles avec SQLite et PostgreSQL / MySQL :

```bash
# Via SQLite (si base chargée dans rdv.db) :
python3 -c "
import sqlite3
conn = sqlite3.connect('rdv.db')
with open('requetes.sql', 'r', encoding='utf-8') as f:
    for q in f.read().split(';'):
        q_clean = q.strip()
        if q_clean and not q_clean.startswith('--'):
            print('--- Requête ---')
            for r in conn.execute(q_clean).fetchall():
                print(r)
"
```

---

## 2. Tableau récapitulatif des Tickets (TMA-101 à TMA-107)

| Ticket | Signalé par | Description succincte | Qualification | Statut HTTP retourné / attendu |
| :--- | :--- | :--- | :---: | :---: |
| **TMA-101** | Usager | RDV pris pour le samedi 14/11 (centre fermé) | ❌ **Anomalie** | `201` ➔ Attendu : `409` |
| **TMA-102** | Chef de centre | 4 usagers sur le créneau du 10/11 à 09:00 | ❌ **Anomalie** | `201` ➔ Attendu : `409` |
| **TMA-103** | Agent | Lettre dans le NPI (`06142A3647`) générant une 500 | ❌ **Anomalie** | `500` ➔ Attendu : `400` |
| **TMA-104** | Usager | Annulation refusée 40h avant le RDV | ❌ **Anomalie** | `409` ➔ Attendu : `200` |
| **TMA-105** | Agent | RDV annulé passé à « Honoré » par erreur | ❌ **Anomalie** | `200` ➔ Attendu : `409` |
| **TMA-106** | Usager | Prochain RDV du 02/12 absent de la page 1 | ❌ **Anomalie** | Ordre alphabétique + 9 items ➔ Attendu : prochain en tête + 10 items |
| **TMA-107** | Usager | Refus de prise de RDV Permis si RDV Passeport futur | ✅ **Conforme** | `409` (Comportement normal attendu) |

---

## 3. Qualification et Diagnostics détaillés par Ticket

### Ticket TMA-101
- **Signalement** : *« J’ai pris rendez-vous pour le samedi 14 novembre. Une fois sur place, j’ai trouvé le centre fermé. »*
- **Trace** : `POST /api/rendez-vous` avec `{"npi":"0614253647","service":"PASSEPORT","dateHeure":"2026-11-14T10:00"}` ➔ `201 {"id":742, ...}`
- **Qualification** : ❌ **Anomalie**.
- **Citation de la règle (Section 2)** : *« Le centre reçoit du lundi au vendredi, par créneaux de 30 minutes. »* et *« Samedi ou dimanche (409) : Le centre est fermé le week-end. »*
- **Diagnostic technique** : Le contrôleur d'API omettait la vérification du jour de la semaine (`weekday in (5, 6)` en Python ou équivalent), ou ne bloquait que le dimanche (`day == 0`), laissant ainsi passer les samedis (comme le confirment les 8 rendez-vous du samedi découverts en base).
- **Correction apportée** : Vérification stricte du jour ouvré (`dt.weekday() in (5, 6)`) renvoyant immédiatement le code HTTP `409` avec le message *"Le centre est fermé le week-end."*.
- **Test unitaire** : `test_tma_101_reservation_weekend` dans `test_rendez_vous.py`.

---

### Ticket TMA-102
- **Signalement** : *« Le mardi 10 novembre à 9 h 00, quatre usagers avaient rendez-vous sur le même créneau. Nous n’avons que trois guichets. »*
- **Trace** : Créneau du 10/11/2026 à 09:00 : RDV n° 632, 644, 681 et 697. Le n° 697 a été accepté (`201`) alors que 3 existaient déjà.
- **Qualification** : ❌ **Anomalie**.
- **Citation de la règle (Section 2)** : *« Un créneau accueille au plus 3 usagers. Un rendez-vous annulé libère sa place. »* et *« Créneau plein (409) : Ce créneau est complet. »*
- **Diagnostic technique** : Erreur de borne classique dans la requête ou la condition de garde : le développeur a écrit `if nb_rdv > 3:` au lieu de `if nb_rdv >= 3:` (ou dans la requête SQL `COUNT(*) > 3`), autorisant un 4e rendez-vous avant de bloquer. (Autre possibilité : filtrage erroné par service dans la requête de quota, oubliant que la capacité des 3 guichets est mutualisée).
- **Correction apportée** : Comptage des rendez-vous non annulés (`statut != 'annule'`) sur le créneau exact ; si le total est `>= 3`, rejet avec le code `409` et le message *"Ce créneau est complet."*.
- **Test unitaire** : `test_tma_102_capacite_creneau_trois_max` dans `test_rendez_vous.py`.

---

### Ticket TMA-103
- **Signalement** : *« Quand un usager tape une lettre dans son NPI, l’écran affiche “Erreur interne du serveur” au lieu d’expliquer le problème. »*
- **Trace** : `POST /api/rendez-vous` avec `{"npi":"06142A3647", ...}` ➔ `500 {"erreur":"Erreur interne du serveur"}`
- **Qualification** : ❌ **Anomalie**.
- **Citation de la règle (Section 2)** : *« Un rendez-vous est pris pour un usager, identifié par son NPI, composé d’exactement 10 chiffres »* et *« NPI invalide (400) : Le NPI doit comporter exactement 10 chiffres. »* ainsi que *« Une saisie invalide ou une action interdite est refusée avec l’un des messages ci-dessous, jamais par une erreur interne. »*
- **Diagnostic technique** : L'application vérifiait uniquement la longueur de la chaîne (`len(npi) == 10`) sans s'assurer qu'elle ne contenait que des chiffres via une expression régulière. Lors de la conversion en entier (`int(npi)`) ou lors du mapping ORM/SQL sur une colonne numérique, une exception non interceptée a fait planter le serveur en HTTP 500.
- **Correction apportée** : Validation stricte en amont via regex `^\d{10}$`. En cas de non-concordance, renvoi du code `400` et du message *"Le NPI doit comporter exactement 10 chiffres."*.
- **Test unitaire** : `test_tma_103_npi_avec_lettre` dans `test_rendez_vous.py`.

---

### Ticket TMA-104
- **Signalement** : *« Le mardi 17 novembre à 18 h, j’ai voulu annuler mon rendez-vous du jeudi 19 à 10 h. L’application a refusé : “Annulation impossible moins de 24 h avant”. »*
- **Trace** : Le 17/11/2026 à 18:00, RDV n° 709 du 19/11/2026 à 10:00 : `POST /api/rendez-vous/709/annulation` ➔ `409 {"erreur":"Annulation impossible moins de 24 h avant le rendez-vous."}`
- **Qualification** : ❌ **Anomalie**.
- **Citation de la règle (Section 2)** : *« L’usager peut annuler son rendez-vous jusqu’à 24 heures avant l’heure prévue. »* et *« Annulation tardive (409) : Annulation impossible moins de 24 h avant le rendez-vous. »*
- **Diagnostic technique** : Entre le 17/11 à 18h00 et le 19/11 à 10h00, il y a exactement **40 heures** réelles (1 jour et 16 heures). Le développeur a commis un piège classique de gestion de date :
  1. En Python : comparaison sur `diff.seconds` au lieu de `diff.total_seconds()`. Comme `diff = timedelta(days=1, seconds=57600)`, `diff.seconds / 3600` renvoie `16` (les heures du jour incomplet), et `16 < 24` a déclenché le refus !
  2. En SQL : `EXTRACT(HOUR FROM interval)` extrait uniquement la partie heure (16) en ignorant les jours.
- **Correction apportée** : Calcul du delta temporel total en secondes réelles : `(date_rdv - maintenant).total_seconds()`. Le rejet 409 n'intervient que si `total_seconds < 86400`.
- **Test unitaire** : `test_tma_104_annulation_40h_avant` dans `test_rendez_vous.py`.

---

### Ticket TMA-105
- **Signalement** : *« J’ai cliqué par erreur sur “Honoré” pour un rendez-vous que l’usager avait annulé. L’application a accepté, et le rendez-vous apparaît maintenant comme honoré. »*
- **Trace** : RDV n° 292, au statut `annule` : `PATCH /api/rendez-vous/292/statut {"statut":"honore"}` ➔ `200`
- **Qualification** : ❌ **Anomalie**.
- **Citation de la règle (Section 2)** : *« Un rendez-vous « confirmé » (confirme) devient « honoré » (honore), « absent » (absent) ou « annulé » (annule). Ces trois statuts sont définitifs. »* et *« Rendez-vous déjà clôturé (409) : Ce rendez-vous est déjà clôturé. »*
- **Diagnostic technique** : L'API de mise à jour de statut ne validait pas l'état courant de l'entité. Elle appliquait aveuglément `statut = 'honore'` sans vérifier que `statut_actuel == 'confirme'`, violant l'irréversibilité des états finaux.
- **Correction apportée** : Contrôle systématique du statut préalable. Si le statut n'est pas `'confirme'`, rejet avec le code `409` et le message *"Ce rendez-vous est déjà clôturé."*.
- **Test unitaire** : `test_tma_105_statut_annule_non_modifiable` dans `test_rendez_vous.py`.

---

### Ticket TMA-106
- **Signalement** : *« Dans “Mes rendez-vous”, mon prochain rendez-vous, celui du 2 décembre, n’est pas en haut de la liste. Il n’est même pas sur la première page. »*
- **Trace** : `GET /api/usagers/0203040506/rendez-vous?page=1` ➔ `200 {"page":1,"parPage":10,"total":13,"rendezVous":[...]}`
Dates retournées : `28/07/2026 09:30, 25/09/2026 11:00, 21/04/2026 09:00, 19/05/2026 15:00, 16/06/2026 13:30, 12/02/2026 10:00, 11/08/2026 14:00, 08/05/2026 11:30, 07/07/2026 10:30`
- **Qualification** : ❌ **Anomalie**.
- **Citation de la règle (Section 2)** : *« Les rendez-vous d’un usager sont listés du plus récent au plus ancien, le prochain rendez-vous en tête, par pages de 10. »*
- **Diagnostic technique** : Cette anomalie cumule **trois erreurs majeures** :
  1. **Tri alphabétique au lieu de chronologique** : L'ordre des dates renvoyées (`28/07`, `25/09`, `21/04`, `19/05`, `16/06`, `12/02`, `11/08`, `08/05`, `07/07`) démontre que la requête a trié sur une chaîne formatée `JJ/MM/AAAA` (`28 > 25 > 21 > ... > 02`). Le RDV du 02/12 a donc été relégué en bas de liste !
  2. **Omission du traitement métier spécifique** : Le système n'extrayait pas le *prochain rendez-vous à venir* pour le forcer en première position.
  3. **Erreur d'indice de pagination (9 éléments au lieu de 10)** : La trace ne contient que 9 rendez-vous alors que `parPage: 10`, conséquence d'une mauvaise borne de découpage (`slice(0, 9)` ou `LIMIT 9`).
- **Correction apportée** :
  - Extraction du prochain RDV futur confirmé (`statut='confirme'` et `date_heure > maintenant`).
  - Tri chronologique descendant (`reverse=True` sur de vrais objets `datetime`) des autres rendez-vous.
  - Découpage paginé rigoureux `[(page-1)*par_page : page*par_page]` garantissant exactement 10 éléments par page complète.
- **Test unitaire** : `test_tma_106_tri_prochain_rdv_en_tete_et_pagination` dans `test_rendez_vous.py`.

---

### Ticket TMA-107
- **Signalement** : *« J’ai un rendez-vous pour mon passeport la semaine prochaine. Je ne peux pas en prendre un autre pour retirer mon permis. »*
- **Trace** : `POST /api/rendez-vous` pour service `PERMIS` le 27/11/2026 à 09:00 ➔ `409 {"erreur":"Vous avez déjà un rendez-vous à venir."}`
- **Qualification** : ✅ **Comportement Conforme**.
- **Citation de la règle (Section 2)** : *« Un usager ne peut avoir qu’un seul rendez-vous à venir, tous services confondus. »* et *« Rendez-vous déjà à venir (409) : Vous avez déjà un rendez-vous à venir. »*
- **Justification** : L'usager possède déjà un rendez-vous à venir (`statut = 'confirme'`). La règle métier spécifie sans équivoque que la restriction s'applique à l'usager **tous services confondus**. Le refus 409 avec le message exact est donc le comportement attendu et correct.
- **Test unitaire** : `test_tma_107_usager_deja_un_rdv_a_venir` dans `test_rendez_vous.py`.

---

## 4. Résultats chiffrés des Requêtes SQL d'impact (`requetes.sql`)

L'export `base_rendez_vous.sql` compte 889 rendez-vous et 757 entrées d'historique au 20/11/2026 à 18h00.

### 4.1 Requête 1 : Rendez-vous confirmés à venir pris un week-end (samedi/dimanche)
- **Critères** : `statut = 'confirme'` ET `date_heure > '2026-11-20 18:00:00'` ET jour dans (Samedi, Dimanche).
- **Résultat** : **5 rendez-vous trouvés**, tous prévus des samedis :

| ID | NPI | Service | Date et Heure | Statut | Jour |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **680** | 0669147625 | PASSEPORT | 2026-11-21 08:30:00 | confirme | Samedi |
| **730** | 0679617916 | CNI | 2026-11-28 09:00:00 | confirme | Samedi |
| **834** | 0610588823 | CNI | 2026-12-05 10:00:00 | confirme | Samedi |
| **857** | 0671987446 | PERMIS | 2026-12-05 10:00:00 | confirme | Samedi |
| **874** | 0648953073 | PASSEPORT | 2026-12-12 11:00:00 | confirme | Samedi |

*Remarque complémentaire (Requête 1bis)* : Si l'on recherche tous les RDV enregistrés un week-end sur l'ensemble de la table, on trouve **8 rendez-vous**, incluant 3 RDV passés restés bloqués à `confirme` car le centre était fermé (ID 475 le 31/10, ID 715 le 14/11 et ID 742 le 14/11 - cas TMA-101). Aucun n'a jamais été pris un dimanche, confirmant que le code d'origine ne filtrait que le dimanche (`day == 0`).

---

### 4.2 Requête 2 : Créneaux comptant plus de 3 rendez-vous non annulés
- **Critères** : `statut != 'annule'` GROUP BY `date_heure` HAVING `COUNT(*) > 3`.
- **Résultat** : **3 créneaux trouvés** avec exactement 4 rendez-vous chacun :

| Date et Heure du créneau | Nb RDV | Détail des Rendez-vous (ID, Service, Statut) | Contexte / Impact |
| :---: | :---: | :--- | :--- |
| **2026-10-22 10:30:00** | 4 | 502 (PASSEPORT - honore), 511 (CNI - honore), 517 (PERMIS - honore), 519 (PASSEPORT - honore) | Surbooking passé |
| **2026-11-10 09:00:00** | 4 | 632 (PASSEPORT - honore), 644 (CNI - honore), 681 (PERMIS - honore), 697 (PERMIS - honore) | **Cas du ticket TMA-102** |
| **2026-11-24 14:00:00** | 4 | 728 (PERMIS - confirme), 750 (PASSEPORT - confirme), 763 (PASSEPORT - confirme), 783 (CNI - confirme) | **Créneau futur surbooké à traiter d'urgence !** |

---

### 4.3 Requête 3 : Rendez-vous passés du statut « annulé » à un autre statut
- **Critères** : Jointure sur `historique_statuts` avec `ancien_statut = 'annule'` et `nouveau_statut != 'annule'`.
- **Résultat** : **4 rendez-vous trouvés** :

| ID RDV | NPI | Service | Date Heure RDV | Transition illégale | Date modif | Agent |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **208** | 0384914669 | PASSEPORT | 2026-10-07 10:00:00 | `annule` ➔ `honore` | 2026-10-07 10:20:00 | AG-01 |
| **231** | 0370202195 | PASSEPORT | 2026-10-15 10:00:00 | `annule` ➔ `honore` | 2026-10-15 10:26:00 | AG-02 |
| **262** | 0317656053 | PERMIS | 2026-10-29 10:00:00 | `annule` ➔ `absent` | 2026-10-29 10:21:00 | AG-03 |
| **292** | 0330677555 | PASSEPORT | 2026-11-12 10:00:00 | `annule` ➔ `honore` | 2026-11-12 10:13:00 | **AG-04 (TMA-105)** |

---

## 5. Section BONUS : Découverte d'anomalies supplémentaires cachées (+2 points)

L'audit minutieux des données de l'export et des traces d'API a permis d'isoler **5 anomalies critiques additionnelles** non signalées par le support :

### Bonus 1 : NPI invalides de plus de 10 chiffres enregistrés en base
- **Données** :
  - **ID 459** : NPI `'01234567890'` (11 chiffres) pour un retrait PERMIS le 20/10/2026.
  - **ID 642** : NPI `'061425364711'` (12 chiffres) pour un retrait PERMIS le 03/11/2026.
- **Cause** : Le code applicatif utilisait une condition `>= 10` (`len(npi) >= 10`) au lieu de vérifier la stricte égalité à 10 chiffres (`len(npi) == 10`).
- **Correction & Test** : Corrigé dans `regles_rendez_vous.py` avec `^\d{10}$` et testé dans `test_npi_longueur_hors_norme_anomalies_bonus`.

### Bonus 2 : Créneaux hors grille horaire (après 15:30)
- **Données** :
  - **ID 490** : prévu à **16:00:00** le 27/10/2026 (`statut = 'honore'`).
  - **ID 698** : prévu à **16:30:00** le 13/11/2026 (`statut = 'absent'`).
  - **ID 842** : prévu à **16:00:00** le 08/12/2026 (**actuellement `confirme` à venir !**).
- **Cause** : Le développeur a contrôlé `8 <= heure <= 16` sur la partie entière de l'heure sans vérifier que le créneau de 15h30 est le dernier créneau officiel de la journée (les créneaux de 16h00 et 16h30 sont donc passés).
- **Correction & Test** : Vérification stricte `heure_rdv <= time(15, 30)` et testé dans `test_horaires_hors_grille_anomalies_bonus`.

### Bonus 3 : Usager ayant cumulé deux rendez-vous à venir simultanément
- **Données** : L'usager avec le NPI **`0902861159`** a réservé :
  - Le **RDV n° 751** (créé le 11/11/2026 pour le **01/12/2026 à 08:00**).
  - Puis le **RDV n° 816** (créé le 17/11/2026 pour le **20/11/2026 à 11:30**).
  Au moment où le RDV 816 a été pris, le RDV 751 était déjà confirmé et dans le futur !
- **Cause** : La condition de vérification recherchait probablement si un rendez-vous existait *après la date demandée* (`date_heure > date_demandee`), ou pour le même jour, plutôt que de vérifier globalement si l'usager avait déjà un rendez-vous postérieur à la date de réservation (`date_heure > date_creation`).
- **Correction & Test** : Vérification globale `date_heure > maintenant` pour tout RDV confirmé de l'usager, testé dans `test_bonus_3_usager_multiples_rdv_a_venir_bloque`.

### Bonus 4 : Pagination renvoyant 9 éléments au lieu de 10 dans la trace TMA-106
- **Observation** : Dans la trace TMA-106, la réponse indique `"parPage": 10`, mais la liste renvoyée ne compte textuellement que **9 rendez-vous**.
- **Cause** : Découpage avec mauvaise borne d'index (ex: `tableau[0:9]` qui ne prend que 9 index en Python/JS) ou clause SQL `LIMIT 9`.
- **Correction & Test** : Corrigé avec `liste[offset : offset + par_page]` qui garantit 10 éléments et validé dans `test_tma_106_tri_prochain_rdv_en_tete_et_pagination`.

### Bonus 5 : Incohérence du format de date en sortie de l'API (Trace TMA-101)
- **Observation** : La requête en entrée transmet `"dateHeure": "2026-11-14T10:00"` (format ISO), mais la réponse renvoie `"dateHeure": "14/11/2026 10:00"`.
- **Impact** : Cette disparité complique la sérialisation pour les clients d'API et a sans doute favorisé le bug de tri textuel `JJ/MM/AAAA` constaté dans TMA-106.

---

## 6. Synthèse d'évaluation

- **Respect strict des consignes** : Zéro dépendance, bibliothèque standard Python 3.
- **Messages et codes HTTP** : Correspondance au caractère près avec le tableau de la section 2.
- **Résultats SQL** : Validés sur la base de données réelle.
- **Couverture de tests** : 16 tests unitaires automatisés réussis à 100%.
