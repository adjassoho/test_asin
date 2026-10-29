"""
Module indépendant des règles de gestion des rendez-vous au guichet.
Aucun couplage à un framework web ni à un moteur de base de données.
"""

from dataclasses import dataclass, replace
from datetime import datetime
import re
from typing import Dict, List, Optional, Tuple, Union, Any

SERVICES_AUTORISES = {"PASSEPORT", "CNI", "PERMIS"}
STATUTS_INITIAUX = {"confirme"}
STATUTS_CLOTURE_AGENT = {"honore", "absent"}
STATUTS_DEFINITIFS = {"honore", "absent", "annule"}

MSG_NPI_INVALIDE = "Le NPI doit comporter exactement 10 chiffres."
MSG_SERVICE_INCONNU = "Service inconnu : choisissez PASSEPORT, CNI ou PERMIS."
MSG_DATE_ILLISIBLE = "Date et heure invalides (format attendu : AAAA-MM-JJTHH:MM)."
MSG_DATE_PASSEE = "Impossible de prendre un rendez-vous dans le passé."
MSG_WEEKEND = "Le centre est fermé le week-end."
MSG_HEURE_HORS_GRILLE = "Créneau invalide : de 08:00 à 15:30, toutes les 30 minutes."
MSG_RDV_DEJA_A_VENIR = "Vous avez déjà un rendez-vous à venir."
MSG_CRENEAU_PLEIN = "Ce créneau est complet."
MSG_ANNULATION_NON_CONFIRME = "Ce rendez-vous ne peut plus être annulé."
MSG_ANNULATION_TARDIVE = "Annulation impossible moins de 24 h avant le rendez-vous."
MSG_STATUT_INCONNU = "Statut invalide : honore ou absent."
MSG_RDV_DEJA_CLOTURE = "Ce rendez-vous est déjà clôturé."

REGEX_NPI = re.compile(r"^\d{10}$")
REGEX_DATE_ISO_MINUTE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


def _convertir_date_interne(valeur: Union[str, datetime]) -> datetime:
    """Convertit une date interne (ISO, SQL ou JJ/MM/AAAA) en objet datetime."""
    if isinstance(valeur, datetime):
        return valeur
    if not isinstance(valeur, str):
        raise ValueError("Format de date interne non supporté")
    texte = valeur.strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(texte, fmt)
        except ValueError:
            continue
    raise ValueError(f"Date interne illisible : {valeur}")


def parser_date_saisie(date_heure_str: Any) -> Optional[datetime]:
    """Valide strictement le format d'entrée AAAA-MM-JJTHH:MM."""
    if not isinstance(date_heure_str, str):
        return None
    if not REGEX_DATE_ISO_MINUTE.match(date_heure_str):
        return None
    try:
        return datetime.strptime(date_heure_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _extraire_champ(rdv: Any, champ: str) -> Any:
    """Permet de manipuler aussi bien des dictionnaires que des objets."""
    if isinstance(rdv, dict):
        if champ == "date_heure" and "dateHeure" in rdv and "date_heure" not in rdv:
            return rdv["dateHeure"]
        return rdv.get(champ)
    return getattr(rdv, champ)


def valider_npi(npi: Any) -> bool:
    """Vérifie que le NPI est une chaîne composée d'exactement 10 chiffres."""
    return isinstance(npi, str) and bool(REGEX_NPI.match(npi))


def valider_service(service: Any) -> bool:
    """Vérifie que le service demandé fait partie des 3 services autorisés."""
    return isinstance(service, str) and service in SERVICES_AUTORISES


def est_Dans_grille_horaire(dt: datetime) -> bool:
    """
    Vérifie que l'heure correspond à un créneau de 30 minutes
    dont le premier débute à 08:00 et le dernier à 15:30.
    """
    if dt.minute not in (0, 30) or dt.second != 0:
        return False
    minutes_depuis_minuit = dt.hour * 60 + dt.minute
    debut_premier_creneau = 8 * 60        # 08:00 -> 480
    debut_dernier_creneau = 15 * 60 + 30  # 15:30 -> 930
    return debut_premier_creneau <= minutes_depuis_minuit <= debut_dernier_creneau


def prendre_rendez_vous(
    npi: Any,
    service: Any,
    date_heure: Any,
    rendez_vous_existants: List[Dict[str, Any]],
    maintenant: Union[str, datetime],
    nouvel_id: Optional[int] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Contrôle et enregistre une demande de prise de rendez-vous.
    Retourne un tuple (code_http, dictionnaire_reponse).
    """
    if not valider_npi(npi):
        return 400, {"erreur": MSG_NPI_INVALIDE}

    if not valider_service(service):
        return 400, {"erreur": MSG_SERVICE_INCONNU}

    dt_rdv = parser_date_saisie(date_heure)
    if dt_rdv is None:
        return 400, {"erreur": MSG_DATE_ILLISIBLE}

    dt_maintenant = _convertir_date_interne(maintenant)

    if dt_rdv <= dt_maintenant:
        return 409, {"erreur": MSG_DATE_PASSEE}

    # weekday() en Python : 0 = lundi ... 4 = vendredi, 5 = samedi, 6 = dimanche
    if dt_rdv.weekday() in (5, 6):
        return 409, {"erreur": MSG_WEEKEND}

    if not est_Dans_grille_horaire(dt_rdv):
        return 409, {"erreur": MSG_HEURE_HORS_GRILLE}

    # Un usager ne peut avoir qu'un seul rendez-vous à venir, tous services confondus
    for rdv in rendez_vous_existants:
        if _extraire_champ(rdv, "npi") == npi and _extraire_champ(rdv, "statut") == "confirme":
            dt_existant = _convertir_date_interne(_extraire_champ(rdv, "date_heure"))
            if dt_existant > dt_maintenant:
                return 409, {"erreur": MSG_RDV_DEJA_A_VENIR}

    # Un créneau accueille au plus 3 usagers. Un rendez-vous annulé libère sa place.
    occupation_creneau = 0
    for rdv in rendez_vous_existants:
        if _extraire_champ(rdv, "statut") != "annule":
            dt_existant = _convertir_date_interne(_extraire_champ(rdv, "date_heure"))
            if dt_existant == dt_rdv:
                occupation_creneau += 1

    if occupation_creneau >= 3:
        return 409, {"erreur": MSG_CRENEAU_PLEIN}

    if nouvel_id is None:
        ids = [_extraire_champ(r, "id") or 0 for r in rendez_vous_existants]
        nouvel_id = (max(ids) + 1) if ids else 1

    nouveau_rdv = {
        "id": nouvel_id,
        "npi": npi,
        "service": service,
        "dateHeure": dt_rdv.strftime("%Y-%m-%dT%H:%M"),
        "date_heure": dt_rdv.strftime("%Y-%m-%d %H:%M:%S"),
        "statut": "confirme",
        "cree_le": dt_maintenant.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return 201, nouveau_rdv


def annuler_rendez_vous(
    rendez_vous: Dict[str, Any],
    maintenant: Union[str, datetime],
) -> Tuple[int, Dict[str, Any]]:
    """
    Contrôle l'annulation d'un rendez-vous par l'usager.
    L'usager peut annuler un rendez-vous confirmé jusqu'à 24 heures avant l'heure prévue.
    """
    statut_actuel = _extraire_champ(rendez_vous, "statut")
    if statut_actuel != "confirme":
        return 409, {"erreur": MSG_ANNULATION_NON_CONFIRME}

    dt_rdv = _convertir_date_interne(_extraire_champ(rendez_vous, "date_heure"))
    dt_maintenant = _convertir_date_interne(maintenant)

    # Calcul sur la durée totale en secondes (évite le piège de timedelta.seconds qui ignore .days)
    delai_secondes = (dt_rdv - dt_maintenant).total_seconds()
    if delai_secondes < 24 * 3600:
        return 409, {"erreur": MSG_ANNULATION_TARDIVE}

    rdv_mis_a_jour = dict(rendez_vous)
    rdv_mis_a_jour["statut"] = "annule"
    return 200, rdv_mis_a_jour


def changer_statut_rendez_vous(
    rendez_vous: Dict[str, Any],
    nouveau_statut: Any,
) -> Tuple[int, Dict[str, Any]]:
    """
    Contrôle le changement de statut effectué par un agent au guichet.
    Seul un rendez-vous au statut 'confirme' peut passer à 'honore' ou 'absent'.
    """
    if not isinstance(nouveau_statut, str) or nouveau_statut not in STATUTS_CLOTURE_AGENT:
        return 400, {"erreur": MSG_STATUT_INCONNU}

    statut_actuel = _extraire_champ(rendez_vous, "statut")
    if statut_actuel != "confirme":
        return 409, {"erreur": MSG_RDV_DEJA_CLOTURE}

    rdv_mis_a_jour = dict(rendez_vous)
    rdv_mis_a_jour["statut"] = nouveau_statut
    return 200, rdv_mis_a_jour


def lister_rendez_vous_usager(
    npi: str,
    rendez_vous_existants: List[Dict[str, Any]],
    maintenant: Union[str, datetime],
    page: int = 1,
    par_page: int = 10,
) -> Tuple[int, Dict[str, Any]]:
    """
    Liste les rendez-vous d'un usager du plus récent au plus ancien,
    le prochain rendez-vous à venir en tête, par pages de 10.
    """
    if not valider_npi(npi):
        return 400, {"erreur": MSG_NPI_INVALIDE}

    if page < 1:
        page = 1
    if par_page < 1:
        par_page = 10

    dt_maintenant = _convertir_date_interne(maintenant)
    rdvs_usager = [dict(r) for r in rendez_vous_existants if _extraire_champ(r, "npi") == npi]

    # Identification du prochain rendez-vous à venir (confirmé et futur, le plus proche)
    futurs_confirmes = [
        r for r in rdvs_usager
        if _extraire_champ(r, "statut") == "confirme"
        and _convertir_date_interne(_extraire_champ(r, "date_heure")) > dt_maintenant
    ]
    futurs_confirmes.sort(key=lambda r: _convertir_date_interne(_extraire_champ(r, "date_heure")))

    prochain_rdv = futurs_confirmes[0] if futurs_confirmes else None
    id_prochain = _extraire_champ(prochain_rdv, "id") if prochain_rdv else None

    autres_rdvs = [
        r for r in rdvs_usager
        if id_prochain is None or _extraire_champ(r, "id") != id_prochain
    ]
    # Tri chronologique réel du plus récent au plus ancien (et non alphabétique JJ/MM/AAAA)
    autres_rdvs.sort(
        key=lambda r: _convertir_date_interne(_extraire_champ(r, "date_heure")),
        reverse=True,
    )

    liste_ordonnee = ([prochain_rdv] if prochain_rdv else []) + autres_rdvs

    debut = (page - 1) * par_page
    fin = debut + par_page
    page_courante = liste_ordonnee[debut:fin]

    return 200, {
        "page": page,
        "parPage": par_page,
        "total": len(liste_ordonnee),
        "rendezVous": page_courante,
    }
