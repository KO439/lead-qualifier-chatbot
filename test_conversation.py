"""
Script de test en ligne de commande : permet de discuter avec le chatbot
directement dans le terminal, sans passer par l'API/le widget web.
Utile pour valider rapidement la logique des agents.

Lancer avec : python test_conversation.py
"""
from agents.conversational_agent import get_bot_reply
from agents.extraction_agent import extract_info
from agents.scoring_agent import compute_score
from rag.catalog import search_products

def main():
    print("=== Test du chatbot de qualification de leads ===")
    print("(tapez 'quit' pour arreter et voir le score final)\n")

    history = []

    while True:
        user_input = input("Vous : ")
        if user_input.lower() in ("quit", "exit"):
            break

        history.append({"role": "user", "content": user_input})
        relevant_products = search_products(user_input, n_results=3)
        reply = get_bot_reply(history, product_context=relevant_products)
        history.append({"role": "assistant", "content": reply})
        print(f"Léa  : {reply}\n")

    print("\n--- Analyse de la conversation ---")
    info = extract_info(history)
    print("Informations extraites :", info)

    result = compute_score(info)
    print(f"\nScore final : {result['score']}/100")
    print(f"Catégorie   : {result['category']}")
    print(f"Détail      : {result['justification']}")


if __name__ == "__main__":
    main()
