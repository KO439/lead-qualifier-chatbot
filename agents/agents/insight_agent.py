"""
Agent d'analyse commerciale (4eme agent IA du pipeline) : apres chaque
echange, analyse l'ensemble de la conversation et du profil extrait pour
generer un resume synthetique et une action commerciale concrete a mener.

Contrairement au scoring (regles fixes, volontairement sans IA pour rester
explicable), cet agent utilise le LLM pour du raisonnement de haut niveau :
il ne se contente pas de classer, il conseille. Il est totalement generique
et fonctionne quel que soit le secteur (le catalogue de demo est
electronique, mais rien dans cet agent n'est specifique a ce domaine).
"""
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

INSIGHT_PROMPT = """Tu es un analyste commercial senior. Analyse la
conversation entre un assistant e-commerce et un visiteur, ainsi que son
score de qualification, puis produis une analyse actionnable pour l'équipe
commerciale — quel que soit le secteur d'activité ou le type de produit
concerné.

Réponds UNIQUEMENT avec un objet JSON valide (rien d'autre) :

{
  "resume": "resume factuel en 1-2 phrases : qui est ce visiteur et que cherche-t-il",
  "action_recommandee": "action concrete et specifique a mener par le commercial (delai, canal, argument a utiliser)",
  "priorite": "haute | moyenne | basse"
}

Règles :
- Base-toi UNIQUEMENT sur les faits explicites de la conversation, ne jamais
  inventer un contact, un produit ou une information non mentionnée.
- L'action recommandée doit être concrète et actionnable, pas générique
  (éviter "recontacter le client", préférer "rappeler avant demain 18h et
  proposer une remise de bienvenue vu son hésitation sur le prix").
- La priorité doit refléter à la fois le score et l'urgence exprimée par
  le visiteur.
"""


def generate_insight(conversation_history: list, extracted_info: dict,
                      score: int, category: str) -> dict:
    conversation_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in conversation_history
    )

    context = f"""Conversation :
{conversation_text}

Score de qualification : {score}/100 ({category})
Informations extraites : {json.dumps(extracted_info, ensure_ascii=False)}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": INSIGHT_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[insight_agent] Erreur génération insight : {e}")
        return {
            "resume": "",
            "action_recommandee": "",
            "priorite": "moyenne",
        }
