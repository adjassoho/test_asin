# Rapport d'Évaluation : Étude de Cas Pratique TMA Junior (DEP / ASIN 2026)
## Prise de rendez-vous au guichet (Passeport, CNI, Permis)

Ce projet contient la résolution complète de l'épreuve technique de Tierce Maintenance Applicative (TMA).
L'ensemble a été conçu selon les standards d'ingénierie logicielle les plus rigoureux : architecture découplée, zéro dépendance externe, tests unitaires automatisés exhaustifs et analyse fine des données en base.

---

## 1. Instructions d'exécution rapide

### A. Lancement des tests automatisés
Aucune installation de paquet (`pip`) n'est requise. Le module utilise exclusivement la bibliothèque standard de Python 3 (`datetime`, `re`, `unittest`) pour garantir une exécution instantanée :

```bash
python3 -m unittest discover -v
```

### B. Exécution des requêtes SQL
Toutes les requêtes d'impact et d'audit se trouvent dans le fichier `requetes.sql` (compatible SQLite, PostgreSQL et MySQL) :

```bash
# Exemple d'exécution avec Python et SQLite :
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

## 2. Qualification, Diagnostic et Correction des Tickets (TMA-101 à TMA-107)

### Tableau synthétique

| Ticket | Qualification | Règle de référence (Section 2) | Code HTTP attendu |
| :--- | :---: | :--- | :---: |
| **TMA-101** | **Anomalie** | Le centre reçoit du lundi au vendredi (fermé le week-end) | `409` |
| **TMA-102** | **Anomalie** | Un créneau accueille au plus 3 usagers | `409` |
| **TMA-103** | **Anomalie** | NPI composé d'exactement 10 chiffres, jamais d'erreur 500 | `400` |
| **TMA-104** | **Anomalie** | Annulation possible jusqu'à 24 heures avant l'heure prévue | `200` |
| **TMA-105** | **Anomalie** | Les statuts honore, absent et annule sont définitifs | `409` |
| **TMA-106** | **Anomalie** | Tri du plus récent au plus ancien, prochain RDV en tête, par pages de 10 | `200` |
| **TMA-107** | **Conforme** | Un seul rendez-vous à venir autorisé, tous services confondus | `409` |

---

### Détail par ticket

#### TMA-101 — Rendez-vous pris un samedi (Anomalie)
- **Règle** : Le centre reçoit uniquement du lundi au vendredi. Tout rendez-vous demandé un samedi ou un dimanche doit être refusé avec `409` : *"Le centre est fermé le week-end."*.
- **Diagnostic** : En inspectant `base_rendez_vous.sql`, on trouve 8 rendez-vous pris un samedi (IDs 475, 680, 715, 730, 742, 834, 857, 874) et aucun le dimanche. Le code en production ne teste que le dimanche (par exemple `day == 0` ou `weekday() == 6`) en oubliant le samedi (`weekday() == 5` ou `day == 6`).
- **Correction & Test** : Vérification `dt_rdv.weekday() in (5, 6)` dans `prendre_rendez_vous`. Testé par `test_TMA_101_refus_rendez_vous_samedi`.

#### TMA-102 — Quatre usagers sur le même créneau (Anomalie)
- **Règle** : Un créneau accueille au plus 3 usagers (les rendez-vous annulés libérant leur place). Au-delà, refus `409` : *"Ce créneau est complet."*.
- **Diagnostic** : Dans `base_rendez_vous.sql`, aucun créneau ne dépasse 4 rendez-vous actifs (ex: `2026-11-10 09:00:00` avec les IDs 632, 644, 681, 697). Le développeur a commis une erreur de borne en écrivant `if count > 3` au lieu de `if count >= 3` avant l'insertion (ou a compté le quota par service au lieu de tous services confondus).
- **Correction & Test** : Comptage des rendez-vous avec `statut != 'annule'` sur le créneau et blocage dès `occupation_creneau >= 3`. Testé par `test_TMA_102_refus_quatrieme_rendez_vous_meme_creneau` et `test_TMA_102_creneau_avec_annulation_libere_place`.

#### TMA-103 — Erreur interne 500 sur un NPI contenant une lettre (Anomalie)
- **Règle** : Le NPI comporte exactement 10 chiffres. Une saisie invalide ne doit jamais provoquer une erreur 500 mais retourner `400` : *"Le NPI doit comporter exactement 10 chiffres."*.
- **Diagnostic** : Le code vérifie uniquement la longueur de la chaîne (`len(npi) >= 10`, ce que `"06142A3647"` respecte), puis tente une conversion numérique non protégée qui lève une exception non interceptée (HTTP 500).
- **Correction & Test** : Validation par expression régulière stricte `^\d{10}$`. Testé par `test_TMA_103_npi_contenant_une_lettre_retourne_400_et_non_500`.

#### TMA-104 — Refus d'annulation 40 heures avant l'échéance (Anomalie)
- **Règle** : L'usager peut annuler son rendez-vous jusqu'à 24 heures avant l'heure prévue.
- **Diagnostic** : Entre le mardi 17/11/2026 à 18:00 et le jeudi 19/11/2026 à 10:00, il y a 40 heures (soit 1 jour et 16 heures). Le code en production calcule uniquement la composante heures de l'écart (16 heures < 24 heures) en ignorant le jour complet (erreur classique d'utilisation de `timedelta.seconds / 3600` qui vaut 16 au lieu de `timedelta.total_seconds() / 3600` qui vaut 40, ou soustraction directe des heures 10 - 18).
- **Correction & Test** : Utilisation de `(dt_rdv - dt_maintenant).total_seconds() < 24 * 3600`. Testé par `test_TMA_104_annulation_40h_avant_autorisee` et `test_TMA_104_annulation_moins_de_24h_refusee`.

#### TMA-105 — Rendez-vous annulé passé au statut « honoré » (Anomalie)
- **Règle** : Les statuts honore, absent et annule sont définitifs. Toute tentative de modification doit renvoyer `409` : *"Ce rendez-vous est déjà clôturé."*.
- **Diagnostic** : L'endpoint `PATCH /api/rendez-vous/:id/statut` vérifie la validité du nouveau statut demandé (honore ou absent), mais omet de vérifier que `ancien_statut == 'confirme'`.
- **Correction & Test** : Vérification stricte `statut_actuel != 'confirme'` dans `changer_statut_rendez_vous`. Testé par `test_TMA_105_refus_passage_annule_vers_honore`.

#### TMA-106 — Mauvais tri et mauvais découpage de pagination (Anomalie)
- **Règle** : Les rendez-vous d'un usager sont listés du plus récent au plus ancien, le prochain rendez-vous en tête, par pages de 10.
- **Diagnostic** : La trace révèle deux bugs distincts :
  1. **Tri alphabétique au lieu de chronologique** : Les dates retournées (`28/07`, `25/09`, `21/04`, `19/05`, `16/06`, `12/02`, `11/08`, `08/05`, `07/07`) sont triées par ordre décroissant du numéro du jour `JJ` dans la chaîne formatée `JJ/MM/AAAA HH:MM` (28 > 25 > 21...). Le rendez-vous du 2 décembre (02/12/2026, ID 826) commence par `"02"` et se retrouve donc relégué en fin de liste sur la page 2.
  2. **Erreur de borne sur la pagination** : Bien que `parPage = 10` et `total = 13`, la page 1 ne retourne que 9 éléments au lieu de 10 (`slice(0, 9)` au lieu de `slice(0, 10)`).
- **Correction & Test** : Placement du prochain rendez-vous confirmé en tête, tri sur de vrais objets `datetime`, et découpage exact `liste[debut : debut + par_page]`. Testé par `test_TMA_106_tri_chronologique_et_pagination_10_elements`.

#### TMA-107 — Refus d'un second rendez-vous à venir (Comportement conforme)
- **Règle** : *« Un usager ne peut avoir qu'un seul rendez-vous à venir, tous services confondus. »*
- **Justification** : Dans `base_rendez_vous.sql`, l'usager `0102030405` possède déjà le rendez-vous ID 800 (PASSEPORT) prévu le 2026-11-26 10:00:00 au statut `confirme`. Sa tentative de réserver un second créneau pour PERMIS le 2026-11-27 est donc légitimement refusée avec `409` : *"Vous avez déjà un rendez-vous à venir."*.
- **Test unitaire** : Testé par `test_TMA_107_comportement_conforme_un_seul_rdv_a_venir_tous_services`.

---

## 3. Résultats des requêtes SQL d'impact (`requetes.sql`)

### 1. Rendez-vous confirmés à venir pris un samedi ou un dimanche (après le 20/11/2026 à 18:00)
**5 rendez-vous à venir sont impactés (tous des samedis) :**

| id | npi | service | date_heure | statut | cree_le |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **680** | 0669147625 | PASSEPORT | 2026-11-21 08:30:00 | confirme | 2026-11-02 18:45:57 |
| **730** | 0679617916 | CNI | 2026-11-28 09:00:00 | confirme | 2026-11-08 13:45:37 |
| **834** | 0610588823 | CNI | 2026-12-05 10:00:00 | confirme | 2026-11-19 07:16:21 |
| **857** | 0671987446 | PERMIS | 2026-12-05 10:00:00 | confirme | 2026-11-20 12:38:16 |
| **874** | 0648953073 | PASSEPORT | 2026-12-12 11:00:00 | confirme | 2026-11-20 16:39:37 |

*(Note : 3 autres rendez-vous pris un samedi dans le passé sont restés bloqués au statut `confirme` : IDs 475, 715 et 742).*

### 2. Créneaux comptant plus de 3 rendez-vous non annulés
**3 créneaux dépassent la capacité maximale de 3 guichets (4 rendez-vous chacun) :**

| date_heure | nb_rendez_vous_actifs | liste_ids |
| :---: | :---: | :--- |
| **2026-10-22 10:30:00** | 4 | 502, 511, 517, 519 |
| **2026-11-10 09:00:00** | 4 | 632, 644, 681, 697 |
| **2026-11-24 14:00:00** | 4 (à venir !) | 728, 750, 763, 783 |

### 3. Rendez-vous passés du statut « annulé » à un autre statut
**4 rendez-vous ont été modifiés à tort après leur annulation :**

| rendez_vous_id | npi | service | date_heure | ancien_statut | nouveau_statut | modifie_le | modifie_par |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **208** | 0384914669 | PASSEPORT | 2026-10-07 10:00:00 | annule | honore | 2026-10-07 10:20:00 | AG-01 |
| **231** | 0370202195 | PASSEPORT | 2026-10-15 10:00:00 | annule | honore | 2026-10-15 10:26:00 | AG-02 |
| **262** | 0317656053 | PERMIS | 2026-10-29 10:00:00 | annule | absent | 2026-10-29 10:21:00 | AG-03 |
| **292** | 0330677555 | PASSEPORT | 2026-11-12 10:00:00 | annule | honore | 2026-11-12 10:13:00 | AG-04 |

---

## 4. Section BONUS — Anomalies supplémentaires découvertes dans l'export et les traces

1. **NPI de 11 et 12 chiffres enregistrés en base :**
   - **ID 459** (`npi = '01234567890'`, 11 chiffres) et **ID 642** (`npi = '061425364711'`, 12 chiffres).
   - *Cause* : La colonne SQL est définie en `VARCHAR(20)` et l'application vérifiait `len(npi) >= 10` au lieu d'une égalité stricte à 10 chiffres.

2. **Rendez-vous pris hors horaires d'ouverture (après 15 h 30) :**
   - **ID 490** (2026-10-27 16:00:00), **ID 698** (2026-11-13 16:30:00) et **ID 842** (2026-12-08 16:00:00, toujours `confirme` à venir).
   - *Cause* : Le contrôle horaire vérifiait `8 <= heure <= 16` sur l'heure entière sans restreindre le dernier créneau à 15:30.

3. **Usagers ayant réservé plusieurs rendez-vous à venir simultanément :**
   - *Exemple 1* : L'usager `0902861159` a créé le RDV ID 751 le 11/11/2026 pour le 2026-12-01, puis a pu créer un second RDV ID 816 le 17/11/2026 pour le 2026-11-20 alors que le RDV 751 était déjà confirmé et à venir.
   - *Exemple 2* : Le NPI `0536455681` avec les IDs 43 et 99 sur le même créneau du 2026-09-01 09:30:00 ! Cela prouve que l'application contrôlait par service au lieu de tous services confondus.

4. **Pagination tronquée à 9 éléments dans la trace TMA-106 :**
   - La page 1 renvoie 9 rendez-vous au lieu de 10 pour un total de 13 (`slice(0, 9)` ou `LIMIT 9`).

5. **Incohérence du format de date renvoyé par l'API (Trace TMA-101) :**
   - Requête envoyée en format ISO `"2026-11-14T10:00"`, mais réponse renvoyée au format texte français `"14/11/2026 10:00"`.
