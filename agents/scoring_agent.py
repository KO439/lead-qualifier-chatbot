"""
Agent de scoring : calcule un score de qualification (0-100) a partir des
informations extraites, selon une logique de type BANT
(Budget, Authority, Need, Timeline), et genere une justification explicable.

v2 (recalibree apres tests/test_scenarios.py) :
- Le delai n'est plus compte de facon binaire (present/absent), il est
  pondere par le niveau d'urgence reel, sinon "cette semaine" et "dans 3
  mois" comptaient pareil, ce qui faussait le score.
- L'intention "comparaison_prix" est mieux valorisee : un visiteur qui
  compare des prix avec un produit precis en tete est un signal commercial
  reel, pas un simple curieux.
"""

WEIGHTS = {
    "produit_recherche": 20,
    "budget_estime": 25,       # uniquement si un montant concret est extrait
    "contact": 15,
}

# Le delai ne vaut son maximum que si l'urgence est reellement haute.
DELAI_POINTS_BY_URGENCY = {
    "haute": 25,
    "moyenne": 12,
    "basse": 5,
    "inconnue": 0,
}

INTENTION_POINTS = {
    "achat_probable": 15,
    "comparaison_prix": 10,
    "simple_curiosite": 0,
    "reclamation": 0,
    "indetermine": 0,
}


def compute_score(extracted_info: dict) -> dict:
    score = 0
    details = []

    if extracted_info.get("produit_recherche"):
        score += WEIGHTS["produit_recherche"]
        details.append(f"+{WEIGHTS['produit_recherche']} pts : produit identifié "
                        f"({extracted_info['produit_recherche']})")

    if extracted_info.get("budget_estime"):
        score += WEIGHTS["budget_estime"]
        details.append(f"+{WEIGHTS['budget_estime']} pts : budget concret mentionné "
                        f"({extracted_info['budget_estime']})")

    urgence = extracted_info.get("niveau_urgence", "inconnue")
    if extracted_info.get("delai_achat"):
        delai_pts = DELAI_POINTS_BY_URGENCY.get(urgence, 0)
        if delai_pts > 0:
            score += delai_pts
            details.append(f"+{delai_pts} pts : délai d'achat exprimé "
                            f"({extracted_info['delai_achat']}, urgence {urgence})")

    if extracted_info.get("email_ou_contact"):
        score += WEIGHTS["contact"]
        details.append(f"+{WEIGHTS['contact']} pts : contact récupéré")

    intention = extracted_info.get("intention", "indetermine")
    intention_pts = INTENTION_POINTS.get(intention, 0)
    if intention_pts > 0:
        score += intention_pts
        label = "intention d'achat probable" if intention == "achat_probable" else "en phase de comparaison de prix"
        details.append(f"+{intention_pts} pts : {label}")

    score = min(score, 100)

    if score >= 65:
        category = "chaud"
    elif score >= 35:
        category = "tiede"
    else:
        category = "froid"

    return {
        "score": score,
        "category": category,
        "justification": " | ".join(details) if details else "Pas assez d'informations recueillies pour l'instant.",
    }
