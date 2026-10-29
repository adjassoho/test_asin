-- ============================================================================
-- FICHIER : requetes.sql
-- Étude de cas TMA DEP/ASIN 2026
-- Date de référence de l'export : vendredi 20 novembre 2026 à 18:00:00
-- ============================================================================

-- 1. Rendez-vous confirmés à venir pris un samedi (6) ou un dimanche (0)
-- Résultat attendu : 5 rendez-vous à venir (IDs 680, 730, 834, 857, 874)
SELECT id, npi, service, date_heure, statut, cree_le
FROM rendez_vous
WHERE statut = 'confirme'
  AND date_heure > '2026-11-20 18:00:00'
  AND CAST(strftime('%w', date_heure) AS INTEGER) IN (0, 6)
ORDER BY date_heure ASC;

-- Note : Pour PostgreSQL, remplacer la condition du jour par :
-- AND EXTRACT(DOW FROM date_heure) IN (0, 6)

-- 1bis. Tous les rendez-vous pris un week-end (y compris ceux passés restés bloqués à 'confirme')
-- Résultat : 8 rendez-vous au total (IDs 475, 680, 715, 730, 742, 834, 857, 874)
SELECT id, npi, service, date_heure, statut, cree_le
FROM rendez_vous
WHERE CAST(strftime('%w', date_heure) AS INTEGER) IN (0, 6)
ORDER BY date_heure ASC;


-- 2. Créneaux qui comptent plus de 3 rendez-vous non annulés
-- Résultat attendu : 3 créneaux à 4 rendez-vous
-- (2026-10-22 10:30:00, 2026-11-10 09:00:00, 2026-11-24 14:00:00)
SELECT date_heure,
       COUNT(*) AS nb_rendez_vous_actifs,
       GROUP_CONCAT(id) AS liste_ids
FROM rendez_vous
WHERE statut != 'annule'
GROUP BY date_heure
HAVING COUNT(*) > 3
ORDER BY date_heure ASC;


-- 3. Rendez-vous passés du statut « annulé » à un autre statut
-- Résultat attendu : 4 rendez-vous (IDs 208, 231, 262, 292)
SELECT r.id AS rendez_vous_id,
       r.npi,
       r.service,
       r.date_heure,
       h.ancien_statut,
       h.nouveau_statut,
       h.modifie_le,
       h.modifie_par
FROM historique_statuts h
JOIN rendez_vous r ON r.id = h.rendez_vous_id
WHERE h.ancien_statut = 'annule'
  AND h.nouveau_statut != 'annule'
ORDER BY h.modifie_le ASC;


-- ============================================================================
-- REQUÊTES BONUS : Détection des anomalies cachées dans base_rendez_vous.sql
-- ============================================================================

-- BONUS A : NPI invalides ne comportant pas exactement 10 chiffres
-- Résultat : ID 459 (11 chiffres : '01234567890') et ID 642 (12 chiffres : '061425364711')
SELECT id, npi, LENGTH(npi) AS longueur, service, date_heure, statut
FROM rendez_vous
WHERE LENGTH(npi) != 10 OR npi GLOB '*[^0-9]*';

-- BONUS B : Rendez-vous pris hors grille horaire (après 15:30 ou avant 08:00)
-- Résultat : ID 490 (16:00), ID 698 (16:30), ID 842 (16:00, confirmé à venir)
SELECT id, npi, service, date_heure, statut, cree_le
FROM rendez_vous
WHERE strftime('%H:%M', date_heure) < '08:00'
   OR strftime('%H:%M', date_heure) > '15:30'
   OR strftime('%M', date_heure) NOT IN ('00', '30');

-- BONUS C : Usagers ayant eu plusieurs rendez-vous actifs simultanément
-- (un nouveau RDV créé alors qu'un autre RDV non annulé au moment de la création était encore dans le futur)
-- Exemple concret découvert : NPI '0902861159' qui a créé le RDV 751 (le 11/11 pour le 01/12),
-- puis le RDV 816 (le 17/11 pour le 20/11) alors que le RDV 751 était toujours à venir.
SELECT r1.npi,
       r1.id AS rdv1_id, r1.date_heure AS rdv1_date, r1.cree_le AS rdv1_cree_le,
       r2.id AS rdv2_id, r2.date_heure AS rdv2_date, r2.cree_le AS rdv2_cree_le
FROM rendez_vous r1
JOIN rendez_vous r2 ON r1.npi = r2.npi AND r1.id != r2.id
WHERE r2.cree_le > r1.cree_le
  AND r2.cree_le < r1.date_heure
  AND NOT EXISTS (
      SELECT 1 FROM historique_statuts h
      WHERE h.rendez_vous_id = r1.id
        AND h.nouveau_statut = 'annule'
        AND h.modifie_le <= r2.cree_le
  );
