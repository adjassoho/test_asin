"""
Suite de tests automatisés pour l'étude de cas pratique TMA Junior (DEP/ASIN 2026).
Couvre l'ensemble des tickets TMA-101 à TMA-107, les cas conformes,
les cas limites (edge cases) et les anomalies bonus.
"""

from datetime import datetime
import unittest

from regles_rendez_vous import (
    annuler_rendez_vous,
    changer_statut_agent,
    lister_rendez_vous_usager,
    prendre_rendez_vous,
)


class TestTMATickets(unittest.TestCase):
    """Tests spécifiques rejouant les tickets signalés par le support (TMA-101 à TMA-107)."""

    def test_tma_101_reservation_weekend(self):
        """
        TMA-101 : Tentative de prise de rendez-vous un samedi.
        L'usager a réservé pour le samedi 14/11/2026 à 10:00 (RDV n° 742).
        L'application avait répondu 201 (Anomalie).
        Comportement attendu : Rejet 409 'Le centre est fermé le week-end.'
        """
        maintenant = "2026-11-09T12:00"
        resultat = prendre_rendez_vous(
            npi="0614253647",
            service="PASSEPORT",
            date_heure_str="2026-11-14T10:00",  # Samedi
            rendez_vous_existants=[],
            maintenant_str=maintenant,
        )
        self.assertFalse(resultat["succes"])
        self.assertEqual(resultat["code_http"], 409)
        self.assertEqual(resultat["erreur"], "Le centre est fermé le week-end.")

    def test_tma_102_capacite_creneau_trois_max(self):
        """
        TMA-102 : Dépassement de la capacité de 3 usagers par créneau.
        Le mardi 10/11/2026 à 09:00, 3 RDV existaient déjà (632, 644, 681).
        Le n° 697 avait été accepté à tort avec un 201 (Anomalie).
        Comportement attendu : Rejet 409 'Ce créneau est complet.'
        """
        maintenant = "2026-11-04T12:00"
        rdv_existants = [
            {"id": 632, "npi": "0638958971", "service": "PASSEPORT", "date_heure": "2026-11-10T09:00", "statut": "confirme"},
            {"id": 644, "npi": "0671968463", "service": "CNI", "date_heure": "2026-11-10T09:00", "statut": "confirme"},
            {"id": 681, "npi": "0609394161", "service": "PERMIS", "date_heure": "2026-11-10T09:00", "statut": "confirme"},
        ]
        # Tentative pour un 4e rendez-vous (n° 697)
        resultat = prendre_rendez_vous(
            npi="0620214467",
            service="PERMIS",
            date_heure_str="2026-11-10T09:00",
            rendez_vous_existants=rdv_existants,
            maintenant_str=maintenant,
        )
        self.assertFalse(resultat["succes"])
        self.assertEqual(resultat["code_http"], 409)
        self.assertEqual(resultat["erreur"], "Ce créneau est complet.")

        # Vérification qu'un rendez-vous annulé libère bien sa place
        rdv_existants[0]["statut"] = "annule"
        resultat_apres_annulation = prendre_rendez_vous(
            npi="0620214467",
            service="PERMIS",
            date_heure_str="2026-11-10T09:00",
            rendez_vous_existants=rdv_existants,
            maintenant_str=maintenant,
        )
        self.assertTrue(resultat_apres_annulation["succes"])
        self.assertEqual(resultat_apres_annulation["code_http"], 201)

    def test_tma_103_npi_avec_lettre(self):
        """
        TMA-103 : NPI contenant une lettre '06142A3647'.
        L'application avait levé une erreur 500 interne non gérée (Anomalie).
        Comportement attendu : Rejet 400 'Le NPI doit comporter exactement 10 chiffres.'
        """
        maintenant = "2026-11-15T10:00"
        resultat = prendre_rendez_vous(
            npi="06142A3647",
            service="CNI",
            date_heure_str="2026-11-23T09:00",
            rendez_vous_existants=[],
            maintenant_str=maintenant,
        )
        self.assertFalse(resultat["succes"])
        self.assertEqual(resultat["code_http"], 400)
        self.assertEqual(resultat["erreur"], "Le NPI doit comporter exactement 10 chiffres.")

    def test_tma_104_annulation_40h_avant(self):
        """
        TMA-104 : Annulation le mardi 17/11 à 18h d'un RDV prévu le jeudi 19/11 à 10h.
        Délai réel = 40 heures (largement supérieur aux 24h requises).
        L'application avait refusé avec 409 'Annulation impossible moins de 24 h avant' (Anomalie).
        Comportement attendu : Annulation acceptée avec code 200 et statut='annule'.
        """
        rdv = {
            "id": 709,
            "npi": "0511223344",
            "service": "PASSEPORT",
            "date_heure": "2026-11-19T10:00",
            "statut": "confirme",
        }
        maintenant = "2026-11-17T18:00"  # 40 heures avant
        resultat = annuler_rendez_vous(rdv, maintenant)
        self.assertTrue(resultat["succes"])
        self.assertEqual(resultat["code_http"], 200)
        self.assertEqual(rdv["statut"], "annule")

        # Test de l'annulation tardive (< 24h, ex: le 18/11 à 12h = 22h avant)
        rdv_tardif = {
            "id": 710,
            "npi": "0511223344",
            "service": "PASSEPORT",
            "date_heure": "2026-11-19T10:00",
            "statut": "confirme",
        }
        resultat_tardif = annuler_rendez_vous(rdv_tardif, "2026-11-18T12:00")
        self.assertFalse(resultat_tardif["succes"])
        self.assertEqual(resultat_tardif["code_http"], 409)
        self.assertEqual(resultat_tardif["erreur"], "Annulation impossible moins de 24 h avant le rendez-vous.")

    def test_tma_105_statut_annule_non_modifiable(self):
        """
        TMA-105 : Tentative de marquer comme 'honore' un RDV déjà annulé (RDV n° 292).
        L'application avait accepté et renvoyé 200 (Anomalie).
        Comportement attendu : Rejet 409 'Ce rendez-vous est déjà clôturé.'
        """
        rdv_annule = {
            "id": 292,
            "npi": "0330677555",
            "service": "PASSEPORT",
            "date_heure": "2026-11-12T10:00",
            "statut": "annule",
        }
        resultat = changer_statut_agent(rdv_annule, "honore")
        self.assertFalse(resultat["succes"])
        self.assertEqual(resultat["code_http"], 409)
        self.assertEqual(resultat["erreur"], "Ce rendez-vous est déjà clôturé.")
        self.assertEqual(rdv_annule["statut"], "annule")

    def test_tma_106_tri_prochain_rdv_en_tete_et_pagination(self):
        """
        TMA-106 : Affichage 'Mes rendez-vous' pour l'usager NPI '0203040506'.
        L'usager a 13 rendez-vous au total, dont 1 seul à venir le 02/12/2026.
        Dans l'application en production :
        - Le RDV du 02/12 n'était pas en tête et n'était pas sur la page 1.
        - La page 1 ne contenait que 9 éléments au lieu de 10.
        Comportement attendu :
        1. Le RDV du 02/12/2026 est EN TÊTE de la liste (index 0 de la page 1).
        2. La page 1 contient EXACTEMENT 10 éléments.
        3. Les 9 éléments suivants sont triés par ordre chronologique décroissant.
        4. La page 2 contient les 3 rendez-vous restants.
        """
        maintenant = "2026-11-20T18:00"
        rdvs_usager = [
            {"id": 1, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-01-05T08:30", "statut": "honore"},
            {"id": 2, "npi": "0203040506", "service": "CNI", "date_heure": "2026-02-12T10:00", "statut": "honore"},
            {"id": 3, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-03-03T14:30", "statut": "absent"},
            {"id": 4, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-04-21T09:00", "statut": "honore"},
            {"id": 5, "npi": "0203040506", "service": "CNI", "date_heure": "2026-05-08T11:30", "statut": "honore"},
            {"id": 6, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-05-19T15:00", "statut": "absent"},
            {"id": 7, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-06-02T08:00", "statut": "honore"},
            {"id": 8, "npi": "0203040506", "service": "CNI", "date_heure": "2026-06-16T13:30", "statut": "honore"},
            {"id": 9, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-07-07T10:30", "statut": "honore"},
            {"id": 10, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-07-28T09:30", "statut": "absent"},
            {"id": 11, "npi": "0203040506", "service": "CNI", "date_heure": "2026-08-11T14:00", "statut": "honore"},
            {"id": 259, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-09-25T11:00", "statut": "honore"},
            {"id": 826, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-12-02T08:30", "statut": "confirme"},
        ]

        # Récupération de la page 1
        page1 = lister_rendez_vous_usager("0203040506", rdvs_usager, maintenant, page=1, par_page=10)
        self.assertEqual(page1["total"], 13)
        self.assertEqual(page1["page"], 1)
        self.assertEqual(page1["parPage"], 10)
        self.assertEqual(len(page1["rendezVous"]), 10, "La page 1 doit contenir exactement 10 éléments (et non 9).")

        # 1. Le premier élément DOIT être le prochain rendez-vous à venir (ID 826 du 02/12/2026)
        self.assertEqual(page1["rendezVous"][0]["id"], 826)
        self.assertEqual(page1["rendezVous"][0]["date_heure"], "2026-12-02T08:30")

        # 2. Les éléments suivants doivent être dans l'ordre chronologique décroissant
        dates_suivantes = [r["date_heure"] for r in page1["rendezVous"][1:]]
        dates_triees = sorted(dates_suivantes, reverse=True)
        self.assertEqual(dates_suivantes, dates_triees)
        self.assertEqual(dates_suivantes[0], "2026-09-25T11:00")  # Le plus récent des passés

        # 3. Récupération de la page 2
        page2 = lister_rendez_vous_usager("0203040506", rdvs_usager, maintenant, page=2, par_page=10)
        self.assertEqual(len(page2["rendezVous"]), 3)

    def test_tma_107_usager_deja_un_rdv_a_venir(self):
        """
        TMA-107 : L'usager a déjà un rendez-vous à venir pour son passeport et tente
        de prendre un rendez-vous pour son permis.
        L'application avait rejeté avec 409 'Vous avez déjà un rendez-vous à venir.'
        Comportement attendu : Rejet 409 CONFORME AUX RÈGLES.
        Règle : 'Un usager ne peut avoir qu'un seul rendez-vous à venir, tous services confondus.'
        """
        maintenant = "2026-11-20T18:00"
        rdv_existant = [
            {
                "id": 810,
                "npi": "0102030405",
                "service": "PASSEPORT",
                "date_heure": "2026-11-25T10:00",  # Dans le futur par rapport à 'maintenant'
                "statut": "confirme",
            }
        ]
        resultat = prendre_rendez_vous(
            npi="0102030405",
            service="PERMIS",
            date_heure_str="2026-11-27T09:00",
            rendez_vous_existants=rdv_existant,
            maintenant_str=maintenant,
        )
        self.assertFalse(resultat["succes"])
        self.assertEqual(resultat["code_http"], 409)
        self.assertEqual(resultat["erreur"], "Vous avez déjà un rendez-vous à venir.")


class TestReglesGestionComplementaires(unittest.TestCase):
    """Tests complémentaires pour valider tous les contrôles et les anomalies bonus."""

    def setUp(self):
        self.maintenant = "2026-11-20T18:00"

    def test_service_inconnu(self):
        """Vérifie le rejet d'un service non prévu."""
        resultat = prendre_rendez_vous(
            npi="0123456789",
            service="VISA",
            date_heure_str="2026-11-24T09:00",
            rendez_vous_existants=[],
            maintenant_str=self.maintenant,
        )
        self.assertFalse(resultat["succes"])
        self.assertEqual(resultat["code_http"], 400)
        self.assertEqual(resultat["erreur"], "Service inconnu : choisissez PASSEPORT, CNI ou PERMIS.")

    def test_format_date_invalide(self):
        """Vérifie le rejet de formats de date incorrects."""
        formats_invalides = [
            "24/11/2026 09:00",
            "2026-11-24 09:00",
            "2026-11-24T09:00:00",  # secondes interdites
            "invalide",
            "2026-02-30T09:00",     # date calendaire inexistante
        ]
        for f in formats_invalides:
            res = prendre_rendez_vous("0123456789", "CNI", f, [], self.maintenant)
            self.assertFalse(res["succes"])
            self.assertEqual(res["code_http"], 400)
            self.assertEqual(res["erreur"], "Date et heure invalides (format attendu : AAAA-MM-JJTHH:MM).")

    def test_date_passee(self):
        """Vérifie le rejet d'un créneau antérieur ou égal à 'maintenant'."""
        res = prendre_rendez_vous("0123456789", "CNI", "2026-11-19T10:00", [], self.maintenant)
        self.assertFalse(res["succes"])
        self.assertEqual(res["code_http"], 409)
        self.assertEqual(res["erreur"], "Impossible de prendre un rendez-vous dans le passé.")

    def test_horaires_hors_grille_anomalies_bonus(self):
        """
        Vérifie le rejet strict des horaires hors de la grille (08:00 à 15:30 par pas de 30m).
        Teste en particulier les anomalies trouvées en base : 16:00 (ID 490, 842) et 16:30 (ID 698).
        """
        creneaux_hors_grille = [
            "2026-11-24T16:00",  # Après 15:30 (Anomalie Bonus 2)
            "2026-11-24T16:30",  # Après 15:30 (Anomalie Bonus 2)
            "2026-11-24T07:30",  # Avant 08:00
            "2026-11-24T09:15",  # Pas de 30 min non respecté
            "2026-11-24T15:45",  # Pas de 30 min non respecté
        ]
        for c in creneaux_hors_grille:
            res = prendre_rendez_vous("0123456789", "PERMIS", c, [], self.maintenant)
            self.assertFalse(res["succes"], f"Le créneau {c} aurait dû être refusé.")
            self.assertEqual(res["code_http"], 409)
            self.assertEqual(res["erreur"], "Créneau invalide : de 08:00 à 15:30, toutes les 30 minutes.")

    def test_npi_longueur_hors_norme_anomalies_bonus(self):
        """
        Vérifie le rejet des NPI de longueur != 10 (ex: 11 chiffres ID 459, 12 chiffres ID 642).
        """
        npis_invalides = [
            "01234567890",   # 11 chiffres (ID 459 en base)
            "061425364711",  # 12 chiffres (ID 642 en base)
            "123456789",     # 9 chiffres
            "",
        ]
        for npi in npis_invalides:
            res = prendre_rendez_vous(npi, "PASSEPORT", "2026-11-24T10:00", [], self.maintenant)
            self.assertFalse(res["succes"])
            self.assertEqual(res["code_http"], 400)
            self.assertEqual(res["erreur"], "Le NPI doit comporter exactement 10 chiffres.")

    def test_changer_statut_invalide(self):
        """Vérifie le rejet d'un statut autre que 'honore' ou 'absent'."""
        rdv = {"id": 1, "statut": "confirme"}
        res = changer_statut_agent(rdv, "annule")
        self.assertFalse(res["succes"])
        self.assertEqual(res["code_http"], 400)
        self.assertEqual(res["erreur"], "Statut invalide : honore ou absent.")

    def test_changer_statut_deja_cloture(self):
        """Vérifie qu'un RDV déjà honoré ou absent ne peut plus être modifié."""
        for statut_clos in ("honore", "absent"):
            rdv = {"id": 1, "statut": statut_clos}
            res = changer_statut_agent(rdv, "honore")
            self.assertFalse(res["succes"])
            self.assertEqual(res["code_http"], 409)
            self.assertEqual(res["erreur"], "Ce rendez-vous est déjà clôturé.")

    def test_annuler_rdv_deja_clos(self):
        """Vérifie qu'un usager ne peut pas annuler un RDV déjà clôturé ou déjà annulé."""
        for statut in ("honore", "absent", "annule"):
            rdv = {"id": 1, "statut": statut, "date_heure": "2026-11-25T10:00"}
            res = annuler_rendez_vous(rdv, self.maintenant)
            self.assertFalse(res["succes"])
            self.assertEqual(res["code_http"], 409)
            self.assertEqual(res["erreur"], "Ce rendez-vous ne peut plus être annulé.")

    def test_bonus_3_usager_multiples_rdv_a_venir_bloque(self):
        """
        Vérifie le blocage de la tentative de réservation lorsqu'un RDV à venir existe déjà
        même si le nouveau RDV demandé est situé chronologiquement AVANT le RDV déjà pris
        (cas de l'anomalie Bonus 3 découverte sur le NPI '0902861159' : RDV 751 pris pour le 01/12,
        puis RDV 816 pris le 17/11 pour le 20/11 alors que le RDV 751 était toujours futur).
        """
        maintenant = "2026-11-17T19:29"
        rdv_existant_futur = [
            {
                "id": 751,
                "npi": "0902861159",
                "service": "PASSEPORT",
                "date_heure": "2026-12-01T08:00",  # Futur par rapport à maintenant
                "statut": "confirme",
            }
        ]
        # Tentative de prendre un RDV pour le 20/11/2026 à 11:30 (RDV 816)
        res = prendre_rendez_vous(
            npi="0902861159",
            service="PASSEPORT",
            date_heure_str="2026-11-20T11:30",
            rendez_vous_existants=rdv_existant_futur,
            maintenant_str=maintenant,
        )
        self.assertFalse(res["succes"])
        self.assertEqual(res["code_http"], 409)
        self.assertEqual(res["erreur"], "Vous avez déjà un rendez-vous à venir.")


if __name__ == "__main__":
    unittest.main()
