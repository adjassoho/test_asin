"""
Module de règles de gestion : Prise de rendez-vous au guichet (DEP/ASIN 2026).
Ce module applique strictement les règles de gestion de la section 2,
indépendamment de toute base de données ou framework.
"""

from datetime import datetime, time
import re
from typing import Any, Dict, List, Optional, Tuple, Union

SERVICES_VALIDES = {"PASSEPORT", "CNI", "PERMIS"}
STATUTS_AGENT_VALIDES = {"honore", "absent"}
HEURE_OUVERTURE = time(8, 0)
HEURE_DERNIER_CRENEAU = time(15, 30)
CAPACITE_MAX_CRENEAU = 3
DELAI_ANNULATION_SECONDES = 24 * 3600  # 24 heures = 86400 secondes


def parse_datetime(dt_val: Union[str, datetime]) -> datetime:
    """Parse une date/heure sous différents formats usuels."""
    if isinstance(dt_val, datetime):
        return dt_val
    if not isinstance(dt_val, str):
        raise ValueError(f"Type non supporté : {type(dt_val)}")
    
    dt_str = dt_val.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Format de date non reconnu : {dt_val}")


def valider_format_date_iso(date_str: Any) -> Tuple[bool, Optional[datetime]]:
    """
    Vérifie que la date respecte STRICTEMENT le format ISO AAAA-MM-JJTHH:MM
    (sans secondes, 16 caractères).
    """
    if not isinstance(date_str, str):
        return False, None
    if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", date_str):
        return False, None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
        return True, dt
    except ValueError:
        return False, None


def prendre_rendez_vous(
    npi: Any,
    service: Any,
    date_heure_str: Any,
    rendez_vous_existants: List[Dict[str, Any]],
    maintenant_str: Union[str, datetime],
) -> Dict[str, Any]:
    """
    Contrôle et effectue une prise de rendez-vous selon les règles officielles.
    """
    # 1. Validation du NPI (exactement 10 chiffres numériques)
    if not isinstance(npi, str) or not re.match(r"^\d{10}$", npi):
        return {
            "succes": False,
            "code_http": 400,
            "erreur": "Le NPI doit comporter exactement 10 chiffres.",
        }

    # 2. Validation du service
    if not isinstance(service, str) or service not in SERVICES_VALIDES:
        return {
            "succes": False,
            "code_http": 400,
            "erreur": "Service inconnu : choisissez PASSEPORT, CNI ou PERMIS.",
        }

    # 3. Format de date et heure (AAAA-MM-JJTHH:MM)
    valide, dt_rdv = valider_format_date_iso(date_heure_str)
    if not valide or dt_rdv is None:
        return {
            "succes": False,
            "code_http": 400,
            "erreur": "Date et heure invalides (format attendu : AAAA-MM-JJTHH:MM).",
        }

    dt_maintenant = parse_datetime(maintenant_str)

    # 4. Date passée
    if dt_rdv <= dt_maintenant:
        return {
            "succes": False,
            "code_http": 409,
            "erreur": "Impossible de prendre un rendez-vous dans le passé.",
        }

    # 5. Jour d'ouverture (Lundi=0 à Vendredi=4 ; Samedi=5, Dimanche=6)
    if dt_rdv.weekday() in (5, 6):
        return {
            "succes": False,
            "code_http": 409,
            "erreur": "Le centre est fermé le week-end.",
        }

    # 6. Grille horaire : de 08:00 à 15:30 toutes les 30 minutes
    heure_rdv = dt_rdv.time()
    if (
        heure_rdv < HEURE_OUVERTURE
        or heure_rdv > HEURE_DERNIER_CRENEAU
        or dt_rdv.minute not in (0, 30)
        or dt_rdv.second != 0
    ):
        return {
            "succes": False,
            "code_http": 409,
            "erreur": "Créneau invalide : de 08:00 à 15:30, toutes les 30 minutes.",
        }

    # 7. Unicité du rendez-vous à venir pour l'usager (tous services confondus)
    for rdv in rendez_vous_existants:
        if rdv.get("npi") == npi and rdv.get("statut") == "confirme":
            try:
                date_existante = parse_datetime(rdv.get("date_heure"))
                if date_existante > dt_maintenant:
                    return {
                        "succes": False,
                        "code_http": 409,
                        "erreur": "Vous avez déjà un rendez-vous à venir.",
                    }
            except Exception:
                continue

    # 8. Capacité du créneau (au plus 3 usagers, les annulés libèrent leur place)
    nb_actifs_sur_creneau = 0
    for rdv in rendez_vous_existants:
        if rdv.get("statut") != "annule":
            try:
                date_existante = parse_datetime(rdv.get("date_heure"))
                if date_existante == dt_rdv:
                    nb_actifs_sur_creneau += 1
            except Exception:
                continue

    if nb_actifs_sur_creneau >= CAPACITE_MAX_CRENEAU:
        return {
            "succes": False,
            "code_http": 409,
            "erreur": "Ce créneau est complet.",
        }

    # Création réussie
    nouveau_rdv = {
        "npi": npi,
        "service": service,
        "date_heure": dt_rdv.strftime("%Y-%m-%dT%H:%M"),
        "statut": "confirme",
    }
    return {
        "succes": True,
        "code_http": 201,
        "donnees": nouveau_rdv,
    }


def annuler_rendez_vous(
    rendez_vous: Dict[str, Any],
    maintenant_str: Union[str, datetime],
) -> Dict[str, Any]:
    """
    Contrôle et effectue l'annulation d'un rendez-vous par un usager.
    """
    statut_actuel = rendez_vous.get("statut")
    if statut_actuel != "confirme":
        return {
            "succes": False,
            "code_http": 409,
            "erreur": "Ce rendez-vous ne peut plus être annulé.",
        }

    dt_rdv = parse_datetime(rendez_vous.get("date_heure"))
    dt_maintenant = parse_datetime(maintenant_str)

    delta_secondes = (dt_rdv - dt_maintenant).total_seconds()
    if delta_secondes < DELAI_ANNULATION_SECONDES:
        return {
            "succes": False,
            "code_http": 409,
            "erreur": "Annulation impossible moins de 24 h avant le rendez-vous.",
        }

    rendez_vous["statut"] = "annule"
    return {
        "succes": True,
        "code_http": 200,
        "donnees": rendez_vous,
    }


def changer_statut_agent(
    rendez_vous: Dict[str, Any],
    nouveau_statut: Any,
) -> Dict[str, Any]:
    """
    Permet à un agent de marquer un rendez-vous comme 'honore' ou 'absent'.
    """
    if nouveau_statut not in STATUTS_AGENT_VALIDES:
        return {
            "succes": False,
            "code_http": 400,
            "erreur": "Statut invalide : honore ou absent.",
        }

    statut_actuel = rendez_vous.get("statut")
    if statut_actuel != "confirme":
        return {
            "succes": False,
            "code_http": 409,
            "erreur": "Ce rendez-vous est déjà clôturé.",
        }

    rendez_vous["statut"] = nouveau_statut
    return {
        "succes": True,
        "code_http": 200,
        "donnees": rendez_vous,
    }


def lister_rendez_vous_usager(
    npi: str,
    tous_les_rendez_vous: List[Dict[str, Any]],
    maintenant_str: Union[str, datetime],
    page: int = 1,
    par_page: int = 10,
) -> Dict[str, Any]:
    """
    Liste les rendez-vous d'un usager :
    - Le prochain rendez-vous à venir (statut='confirme' et date_heure > maintenant) EN TÊTE
    - Les autres rendez-vous triés du plus récent au plus ancien (ordre antéchronologique)
    - Découpage par pages d'exactement `par_page` (défaut: 10)
    """
    dt_maintenant = parse_datetime(maintenant_str)
    
    # 1. Filtrer les rendez-vous de l'usager
    rdvs_usager = [r for r in tous_les_rendez_vous if r.get("npi") == npi]

    # 2. Identifier le prochain rendez-vous à venir
    prochain_rdv = None
    autres_rdvs = []

    rdvs_futurs_confirmes = []
    for r in rdvs_usager:
        dt_r = parse_datetime(r.get("date_heure"))
        if r.get("statut") == "confirme" and dt_r > dt_maintenant:
            rdvs_futurs_confirmes.append((dt_r, r))
        else:
            autres_rdvs.append((dt_r, r))

    if rdvs_futurs_confirmes:
        # Le prochain est le plus proche dans le futur
        rdvs_futurs_confirmes.sort(key=lambda x: x[0])
        prochain_rdv = rdvs_futurs_confirmes[0][1]
        # S'il y avait d'autres RDV futurs (anomalie de données), ils vont dans les autres
        for dt_r, r in rdvs_futurs_confirmes[1:]:
            autres_rdvs.append((dt_r, r))

    # 3. Trier les autres rendez-vous du plus récent au plus ancien
    autres_rdvs.sort(key=lambda x: x[0], reverse=True)
    liste_ordonnee = []
    if prochain_rdv is not None:
        liste_ordonnee.append(prochain_rdv)
    liste_ordonnee.extend([r for _, r in autres_rdvs])

    # 4. Pagination exacte
    total = len(liste_ordonnee)
    if page < 1:
        page = 1
    if par_page < 1:
        par_page = 10

    offset = (page - 1) * par_page
    rendez_vous_page = liste_ordonnee[offset : offset + par_page]

    return {
        "page": page,
        "parPage": par_page,
        "total": total,
        "rendezVous": rendez_vous_page,
    }
