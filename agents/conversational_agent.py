"""
Agent conversationnel : gere le dialogue naturel avec le visiteur du site
e-commerce, dans le but de qualifier son besoin sans etre intrusif.

Supporte maintenant le streaming (get_bot_reply_stream) : les tokens sont
renvoyes au fur et a mesure qu'ils sont generes, pour un effet "machine a
ecrire" en temps reel cote interface, au lieu d'attendre la reponse complete.
"""
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """Tu es Léa, l'assistante virtuelle d'un site e-commerce.
Ton objectif est d'aider le visiteur ET de comprendre discrètement son besoin
pour évaluer s'il s'agit d'un client sérieux (lead qualifié).

Règles de conversation :
1. Sois chaleureuse, naturelle, jamais robotique ou trop insistante.
2. Pose UNE question à la fois, jamais un interrogatoire.
3. Cherche à connaître, au fil de la conversation et sans jamais le demander
   de façon abrupte : le produit recherché, le budget approximatif, le délai
   d'achat souhaité, et si possible un moyen de contact (email).
4. Si le visiteur est juste curieux ou hors sujet, réponds gentiment sans
   forcer la qualification.
5. Ne jamais inventer d'informations sur des produits que tu ne connais pas.
6. Réponses courtes (2-4 phrases maximum), ton commercial mais pas insistant.
"""


def _build_messages(conversation_history: list, product_context: list = None) -> list:
    system_prompt = SYSTEM_PROMPT

    if product_context:
        produits_texte = "\n".join(
            f"- {p['nom']} ({p['prix']}€) : {p['description']}"
            for p in product_context
        )
        system_prompt += f"""

Voici des produits du catalogue qui pourraient correspondre à la demande
actuelle du visiteur. Utilise-les UNIQUEMENT s'ils sont pertinents par
rapport à ce qu'il cherche, sans les citer tous d'un coup — glisse une ou
deux suggestions naturellement dans la conversation, avec leur prix :

{produits_texte}

Si aucun de ces produits ne correspond vraiment à la demande, n'en parle pas
et continue simplement la conversation normalement."""

    return [{"role": "system", "content": system_prompt}] + conversation_history


def get_bot_reply(conversation_history: list, product_context: list = None) -> str:
    """Version non-streaming : attend la reponse complete avant de la renvoyer."""
    messages = _build_messages(conversation_history, product_context)
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=300,
    )
    return response.choices[0].message.content


def get_bot_reply_stream(conversation_history: list, product_context: list = None):
    """
    Version streaming : retourne un iterateur de chunks Groq. Chaque chunk
    contient un morceau de texte (chunk.choices[0].delta.content), a
    consommer au fur et a mesure cote appelant.
    """
    messages = _build_messages(conversation_history, product_context)
    return client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=300,
        stream=True,
    )
