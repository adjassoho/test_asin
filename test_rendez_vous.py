"""
Suite de tests automatisés rejouant chaque ticket (TMA-101 à TMA-107)
ainsi que les cas limites et les anomalies bonus détectées dans l'export SQL.
"""

import unittest
from regles_rendez_vous import (
    prendre_rendez_vous,
    annuler_rendez_vous,
    changer_statut_rendez_vous,
    lister_rendez_vous_usager,
    MSG_WEEKEND,
    MSG_CRENEAU_PLEIN,
    MSG_NPI_INVALIDE,
    MSG_ANNULATION_TARDIVE,
    MSG_RDV_DEJA_CLOTURE,
    MSG_RDV_DEJA_A_VENIR,
    MSG_HEURE_HORS_GRILLE,
    MSG_DATE_PASSEE,
    MSG_DATE_ILLISIBLE,
    MSG_SERVICE_INCONNU,
    MSG_STATUT_INCONNU,
    MSG_ANNULATION_NON_CONFIRME,
)


class TestTicketsTMA(unittest.TestCase):

    def test_TMA_101_refus_rendez_vous_samedi(self):
        """
        TMA-101 : L'usager 0614253647 tente de prendre RDV pour le samedi 14/11/2026 à 10:00.
        Le module doit refuser avec 409 'Le centre est fermé le week-end.'
        """
        code, rep = prendre_rendez_vous(
            npi="0614253647",
            service="PASSEPORT",
            date_heure="2026-11-14T10:00",
            rendez_vous_existants=[],
            maintenant="2026-11-09 23:59:11",
        )
        self.assertEqual(code, 409)
        self.assertEqual(rep["erreur"], MSG_WEEKEND)

    def test_TMA_102_refus_quatrieme_rendez_vous_meme_creneau(self):
        """
        TMA-102 : Les RDV 632, 644 et 681 existent déjà sur le créneau du mardi 10/11/2026 à 09:00.
        La tentative d'ajout du 4e RDV (n° 697) doit être refusée avec 409 'Ce créneau est complet.'
        """
        existants = [
            {"id": 632, "npi": "0638958971", "service": "PASSEPORT", "date_heure": "2026-11-10 09:00:00", "statut": "confirme"},
            {"id": 644, "npi": "0671968463", "service": "CNI", "date_heure": "2026-11-10 09:00:00", "statut": "confirme"},
            {"id": 681, "npi": "0609394161", "service": "PERMIS", "date_heure": "2026-11-10 09:00:00", "statut": "confirme"},
        ]
        code, rep = prendre_rendez_vous(
            npi="0620214467",
            service="CNI",
            date_heure="2026-11-10T09:00",
            rendez_vous_existants=existants,
            maintenant="2026-11-04 23:43:37",
        )
        self.assertEqual(code, 409)
        self.assertEqual(rep["erreur"], MSG_CRENEAU_PLEIN)

    def test_TMA_102_creneau_avec_annulation_libere_place(self):
        """Un rendez-vous annulé sur le créneau libère sa place pour un nouvel usager."""
        existants = [
            {"id": 1, "npi": "0638958971", "service": "PASSEPORT", "date_heure": "2026-11-10 09:00:00", "statut": "confirme"},
            {"id": 2, "npi": "0671968463", "service": "CNI", "date_heure": "2026-11-10 09:00:00", "statut": "annule"},
            {"id": 3, "npi": "0609394161", "service": "PERMIS", "date_heure": "2026-11-10 09:00:00", "statut": "confirme"},
        ]
        code, rep = prendre_rendez_vous(
            npi="0620214467",
            service="CNI",
            date_heure="2026-11-10T09:00",
            rendez_vous_existants=existants,
            maintenant="2026-11-04 23:43:37",
        )
        self.assertEqual(code, 201)
        self.assertEqual(rep["statut"], "confirme")

    def test_TMA_103_npi_contenant_une_lettre_retourne_400_et_non_500(self):
        """
        TMA-103 : Le NPI '06142A3647' contient une lettre.
        L'application doit renvoyer 400 avec le message dédié, jamais une erreur 500.
        """
        code, rep = prendre_rendez_vous(
            npi="06142A3647",
            service="CNI",
            date_heure="2026-11-23T09:00",
            rendez_vous_existants=[],
            maintenant="2026-11-20 18:00:00",
        )
        self.assertEqual(code, 400)
        self.assertEqual(rep["erreur"], MSG_NPI_INVALIDE)

    def test_TMA_104_annulation_40h_avant_autorisee(self):
        """
        TMA-104 : Le mardi 17/11/2026 à 18:00, l'usager annule son RDV n° 709 du jeudi 19/11/2026 à 10:00.
        Il reste exactement 40 heures (>= 24 h), l'annulation doit donc être acceptée (200).
        """
        rdv_709 = {
            "id": 709,
            "npi": "0339205992",
            "service": "PERMIS",
            "date_heure": "2026-11-19 10:00:00",
            "statut": "confirme",
        }
        code, rep = annuler_rendez_vous(rdv_709, maintenant="2026-11-17 18:00:00")
        self.assertEqual(code, 200)
        self.assertEqual(rep["statut"], "annule")

    def test_TMA_104_annulation_moins_de_24h_refusee(self):
        """Vérifie qu'une annulation à 16h d'écart (le 18/11 à 18:00 pour le 19/11 à 10:00) est bien refusée."""
        rdv_709 = {
            "id": 709,
            "npi": "0339205992",
            "service": "PERMIS",
            "date_heure": "2026-11-19 10:00:00",
            "statut": "confirme",
        }
        code, rep = annuler_rendez_vous(rdv_709, maintenant="2026-11-18 18:00:00")
        self.assertEqual(code, 409)
        self.assertEqual(rep["erreur"], MSG_ANNULATION_TARDIVE)

    def test_TMA_105_refus_passage_annule_vers_honore(self):
        """
        TMA-105 : Le RDV n° 292 est au statut 'annule' (statut définitif).
        Un agent qui tente de le passer à 'honore' reçoit 409 'Ce rendez-vous est déjà clôturé.'
        """
        rdv_292 = {
            "id": 292,
            "npi": "0330677555",
            "service": "PASSEPORT",
            "date_heure": "2026-11-12 10:00:00",
            "statut": "annule",
        }
        code, rep = changer_statut_rendez_vous(rdv_292, nouveau_statut="honore")
        self.assertEqual(code, 409)
        self.assertEqual(rep["erreur"], MSG_RDV_DEJA_CLOTURE)

    def test_TMA_106_tri_chronologique_et_pagination_10_elements(self):
        """
        TMA-106 : Pour l'usager 0203040506 (13 rendez-vous dont celui du 02/12/2026),
        la page 1 doit placer le prochain RDV (02/12/2026) en tête, trier du plus récent
        au plus ancien, et contenir exactement 10 rendez-vous (et non 9).
        """
        rdvs_0203040506 = [
            {"id": 1, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-01-05 08:30:00", "statut": "honore"},
            {"id": 2, "npi": "0203040506", "service": "CNI", "date_heure": "2026-02-12 10:00:00", "statut": "honore"},
            {"id": 3, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-03-03 14:30:00", "statut": "absent"},
            {"id": 4, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-04-21 09:00:00", "statut": "honore"},
            {"id": 5, "npi": "0203040506", "service": "CNI", "date_heure": "2026-05-08 11:30:00", "statut": "honore"},
            {"id": 6, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-05-19 15:00:00", "statut": "absent"},
            {"id": 7, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-06-02 08:00:00", "statut": "honore"},
            {"id": 8, "npi": "0203040506", "service": "CNI", "date_heure": "2026-06-16 13:30:00", "statut": "honore"},
            {"id": 9, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-07-07 10:30:00", "statut": "honore"},
            {"id": 10, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-07-28 09:30:00", "statut": "absent"},
            {"id": 11, "npi": "0203040506", "service": "CNI", "date_heure": "2026-08-11 14:00:00", "statut": "honore"},
            {"id": 259, "npi": "0203040506", "service": "PERMIS", "date_heure": "2026-09-25 11:00:00", "statut": "honore"},
            {"id": 826, "npi": "0203040506", "service": "PASSEPORT", "date_heure": "2026-12-02 08:30:00", "statut": "confirme"},
        ]
        code, rep = lister_rendez_vous_usager(
            npi="0203040506",
            rendez_vous_existants=rdvs_0203040506,
            maintenant="2026-11-20 18:00:00",
            page=1,
            par_page=10,
        )
        self.assertEqual(code, 200)
        self.assertEqual(rep["total"], 13)
        self.assertEqual(len(rep["rendezVous"]), 10)
        # Le prochain rendez-vous du 2 décembre (id 826) est bien en tête
        ids_page_1 = [r["id"] for r in rep["rendezVous"]]
        self.assertEqual(ids_page_1, [826, 259, 11, 10, 9, 8, 7, 6, 5, 4])

    def test_TMA_107_comportement_conforme_un_seul_rdv_a_venir_tous_services(self):
        """
        TMA-107 (Ticket conforme) : L'usager 0102030405 a déjà le RDV n° 800 confirmé
        pour son PASSEPORT le 26/11/2026 à 10:00. Sa demande pour un PERMIS le 27/11/2026
        doit être refusée avec 409 'Vous avez déjà un rendez-vous à venir.'
        """
        existants = [
            {"id": 800, "npi": "0102030405", "service": "PASSEPORT", "date_heure": "2026-11-26 10:00:00", "statut": "confirme"}
        ]
        code, rep = prendre_rendez_vous(
            npi="0102030405",
            service="PERMIS",
            date_heure="2026-11-27T09:00",
            rendez_vous_existants=existants,
            maintenant="2026-11-20 18:00:00",
        )
        self.assertEqual(code, 409)
        self.assertEqual(rep["erreur"], MSG_RDV_DEJA_A_VENIR)

    def test_bonus_npi_11_ou_12_chiffres_refuse(self):
        """Bonus : Les NPI de 11 ou 12 chiffres trouvés en base (IDs 459, 642) sont refusés."""
        code, rep = prendre_rendez_vous(
            npi="01234567890",
            service="PERMIS",
            date_heure="2026-11-25T09:30",
            rendez_vous_existants=[],
            maintenant="2026-11-20 18:00:00",
        )
        self.assertEqual(code, 400)
        self.assertEqual(rep["erreur"], MSG_NPI_INVALIDE)

    def test_bonus_creneau_16h00_et_16h30_refuse(self):
        """Bonus : Les créneaux à 16:00 et 16:30 trouvés en base (IDs 490, 698, 842) sont refusés."""
        for heure in ("2026-12-08T16:00", "2026-12-08T16:30", "2026-12-08T07:30", "2026-12-08T10:15"):
            code, rep = prendre_rendez_vous(
                npi="0387129160",
                service="PASSEPORT",
                date_heure=heure,
                rendez_vous_existants=[],
                maintenant="2026-11-20 18:00:00",
            )
            self.assertEqual(code, 409)
            self.assertEqual(rep["erreur"], MSG_HEURE_HORS_GRILLE)

    def test_autres_regles_validation(self):
        """Vérifie les autres cas refusés du tableau de la section 2."""
        # Service inconnu
        c1, r1 = prendre_rendez_vous("0102030405", "VISA", "2026-11-25T09:00", [], "2026-11-20 18:00:00")
        self.assertEqual((c1, r1["erreur"]), (400, MSG_SERVICE_INCONNU))

        # Date illisible
        c2, r2 = prendre_rendez_vous("0102030405", "CNI", "25/11/2026 09:00", [], "2026-11-20 18:00:00")
        self.assertEqual((c2, r2["erreur"]), (400, MSG_DATE_ILLISIBLE))

        # Date passée
        c3, r3 = prendre_rendez_vous("0102030405", "CNI", "2026-11-19T09:00", [], "2026-11-20 18:00:00")
        self.assertEqual((c3, r3["erreur"]), (409, MSG_DATE_PASSEE))

        # Annulation d'un RDV non confirmé
        c4, r4 = annuler_rendez_vous({"id": 1, "statut": "honore", "date_heure": "2026-11-25 09:00:00"}, "2026-11-20 18:00:00")
        self.assertEqual((c4, r4["erreur"]), (409, MSG_ANNULATION_NON_CONFIRME))

        # Statut demandé inconnu
        c5, r5 = changer_statut_rendez_vous({"id": 1, "statut": "confirme"}, "reporte")
        self.assertEqual((c5, r5["erreur"]), (400, MSG_STATUT_INCONNU))


if __name__ == "__main__":
    unittest.main()
