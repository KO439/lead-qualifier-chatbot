"""
Agent d'extraction : analyse la conversation et en extrait des informations
structurees (JSON) utiles a la qualification du lead.
"""
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

EXTRACTION_PROMPT = """Tu es un moteur d'extraction d'informations. Analyse la
conversation ci-dessous entre un assistant e-commerce et un visiteur.

Réponds UNIQUEMENT avec un objet JSON valide (rien d'autre, pas de texte,
pas de markdown), avec exactement ces champs :

{
  "produit_recherche": "string ou null",
  "budget_estime": "string ou null (ex: '500-800 euros')",
  "delai_achat": "string ou null (ex: 'cette semaine', 'dans 3 mois')",
  "email_ou_contact": "string ou null",
  "intention": "achat_probable | simple_curiosite | comparaison_prix | reclamation | indetermine",
  "niveau_urgence": "haute | moyenne | basse | inconnue"
}

Règles strictes :
- "budget_estime" : uniquement si un MONTANT CONCRET est donné (un chiffre
  ou une fourchette, ex: "500 euros", "entre 300 et 500"). Si le visiteur
  dit seulement "pas cher", "abordable", "un bon prix" SANS aucun chiffre,
  mets null — ce n'est pas un budget exploitable.
- "niveau_urgence" : "haute" seulement si un délai court et précis est donné
  (aujourd'hui, cette semaine, dans les jours qui viennent). "moyenne" pour
  un délai de quelques semaines à quelques mois. "basse" si le délai est
  vague ou lointain ("un jour", "peut-être plus tard"). "inconnue" si rien
  n'est mentionné sur le timing.
- Si une information n'est pas mentionnée dans la conversation, mets null.
  Ne devine jamais, base-toi uniquement sur ce qui est explicitement dit.
"""


def extract_info(conversation_history: list) -> dict:
    conversation_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in conversation_history
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": f"Conversation :\n{conversation_text}"},
        ],
        temperature=0,
        max_tokens=300,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return {
            "produit_recherche": None,
            "budget_estime": None,
            "delai_achat": None,
            "email_ou_contact": None,
            "intention": "indetermine",
            "niveau_urgence": "inconnue",
        }
