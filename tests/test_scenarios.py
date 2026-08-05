"""
Jeu de tests : verifie que le scoring reagit de facon coherente a des
scenarios de conversation types. Chaque scenario est une conversation deja
ecrite (pas besoin d'appeler l'IA conversationnelle), on teste seulement
les agents d'extraction et de scoring, qui sont le coeur du systeme.

Ces resultats sont a inclure dans la partie "evaluation" de votre rapport
de stage : ils prouvent la coherence du scoring avec des cas concrets.

Lancer avec : python tests/test_scenarios.py

Ce script est aussi utilise en CI (GitHub Actions, voir
.github/workflows/tests.yml) : il quitte avec un code d'erreur si le taux
de coherence descend sous SEUIL_MINIMUM, ce qui fait echouer le build.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from agents.extraction_agent import extract_info
from agents.scoring_agent import compute_score

SEUIL_MINIMUM = 70  # % de coherence minimum accepte avant de faire echouer la CI

# Chaque scenario : une conversation deja ecrite + la categorie attendue
# (definie a la main, en se basant sur le bon sens commercial).
SCENARIOS = [
    {
        "nom": "Client pressé avec budget clair",
        "attendu": "chaud",
        "conversation": [
            {"role": "user", "content": "Bonjour, je cherche un laptop pour le travail, budget max 700 euros"},
            {"role": "assistant", "content": "Bien sûr ! Pour quand en avez-vous besoin ?"},
            {"role": "user", "content": "Le plus vite possible, cette semaine si possible. Mon email est jean@test.com"},
        ],
    },
    {
        "nom": "Visiteur curieux sans intention claire",
        "attendu": "froid",
        "conversation": [
            {"role": "user", "content": "Salut, vous vendez quoi comme trucs ici ?"},
            {"role": "assistant", "content": "Nous vendons de l'électronique : laptops, smartphones, accessoires. Qu'est-ce qui vous intéresse ?"},
            {"role": "user", "content": "Ah ok, je regarde juste pour l'instant, merci"},
        ],
    },
    {
        "nom": "Intérêt réel mais sans urgence",
        "attendu": "tiede",
        "conversation": [
            {"role": "user", "content": "Je pense changer de téléphone dans les prochains mois"},
            {"role": "assistant", "content": "Avec plaisir ! Quel budget envisagez-vous ?"},
            {"role": "user", "content": "Autour de 400 euros je pense, pas encore décidé sur le modèle"},
        ],
    },
    {
        "nom": "Comparaison de prix (chasseur de bonnes affaires)",
        "attendu": "tiede",
        "conversation": [
            {"role": "user", "content": "Vous faites moins cher que Amazon sur le MacBook Air ?"},
            {"role": "assistant", "content": "Nos prix sont compétitifs. Vous cherchez le MacBook Air pour un usage particulier ?"},
            {"role": "user", "content": "Juste pour comparer les prix avant d'acheter ailleurs"},
        ],
    },
    {
        "nom": "Réclamation (pas un lead commercial)",
        "attendu": "froid",
        "conversation": [
            {"role": "user", "content": "Ma commande n'est jamais arrivée, ça fait 2 semaines"},
            {"role": "assistant", "content": "Je suis désolée pour ce désagrément, pouvez-vous me donner votre numéro de commande ?"},
            {"role": "user", "content": "Je n'ai plus le numéro, c'est inadmissible"},
        ],
    },
    {
        "nom": "Achat urgent tout critère rempli",
        "attendu": "chaud",
        "conversation": [
            {"role": "user", "content": "Je dois absolument acheter un écran PC aujourd'hui, budget 150 euros max"},
            {"role": "assistant", "content": "Nous avons l'écran ASUS 24 pouces à 129€, disponible immédiatement. Voulez-vous que je vous laisse un lien ?"},
            {"role": "user", "content": "Oui parfait, mon email : marie@test.com"},
        ],
    },
    {
        "nom": "Message hors sujet",
        "attendu": "froid",
        "conversation": [
            {"role": "user", "content": "Quelle heure est-il chez vous ?"},
            {"role": "assistant", "content": "Je suis là pour vous aider sur nos produits ! Cherchez-vous quelque chose en particulier ?"},
            {"role": "user", "content": "Non rien, juste une question comme ça"},
        ],
    },
    {
        "nom": "Étudiant avec budget serré, délai flou",
        "attendu": "tiede",
        "conversation": [
            {"role": "user", "content": "Je suis étudiant, je cherche un laptop pas cher pour la rentrée"},
            {"role": "assistant", "content": "L'Acer Aspire 3 à 349€ est parfait pour ça. La rentrée c'est dans combien de temps ?"},
            {"role": "user", "content": "Dans 2-3 mois normalement, je regarde à l'avance"},
        ],
    },
]


def run_tests():
    print("=" * 70)
    print("JEU DE TESTS — Cohérence du système de scoring")
    print("=" * 70)

    results = []

    for i, scenario in enumerate(SCENARIOS, 1):
        extracted = extract_info(scenario["conversation"])
        result = compute_score(extracted)

        actual = result["category"]
        expected = scenario["attendu"]
        match = "✅ OK" if actual == expected else "❌ ÉCART"

        results.append(match == "✅ OK")

        print(f"\n[{i}] {scenario['nom']}")
        print(f"    Attendu  : {expected}")
        print(f"    Obtenu   : {actual} (score {result['score']}/100)")
        print(f"    Résultat : {match}")
        print(f"    Détail   : {result['justification']}")

    print("\n" + "=" * 70)
    success_rate = sum(results) / len(results) * 100
    print(f"RÉSULTAT GLOBAL : {sum(results)}/{len(results)} scénarios corrects "
          f"({success_rate:.0f}% de cohérence)")
    print("=" * 70)
    print("\nÀ inclure dans le rapport : ce tableau prouve que le scoring")
    print("réagit de façon cohérente à des situations commerciales variées,")
    print("y compris les cas limites (réclamation, curiosité, comparaison).")

    if success_rate < SEUIL_MINIMUM:
        print(f"\n❌ Cohérence ({success_rate:.0f}%) sous le seuil minimum "
              f"({SEUIL_MINIMUM}%) — build en échec.")
        sys.exit(1)
    else:
        print(f"\n✅ Cohérence ({success_rate:.0f}%) au-dessus du seuil "
              f"minimum ({SEUIL_MINIMUM}%) — build réussi.")
        sys.exit(0)


if __name__ == "__main__":
    run_tests()
