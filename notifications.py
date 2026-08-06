"""
Envoie une alerte email a l'equipe commerciale des qu'un lead devient
"chaud" (score >= 65). Utilise Resend (gratuit, 100 emails/jour), avec
leur adresse d'envoi par defaut qui ne necessite aucune configuration
de domaine.

Si RESEND_API_KEY ou SALES_EMAIL ne sont pas configures, la fonction ne
fait rien silencieusement (pas d'erreur bloquante pour le reste du chat).
"""
import os
import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")
SALES_EMAIL = os.getenv("SALES_EMAIL")


def send_hot_lead_alert(session_id: str, extracted_info: dict, score: int, justification: str):
    if not resend.api_key or not SALES_EMAIL:
        return  # notifications non configurees, on ignore silencieusement

    produit = extracted_info.get("produit_recherche") or "Non précisé"
    budget = extracted_info.get("budget_estime") or "Non précisé"
    delai = extracted_info.get("delai_achat") or "Non précisé"
    contact = extracted_info.get("email_ou_contact") or "Non fourni"

    html = f"""
    <div style="font-family: sans-serif; max-width: 500px;">
      <h2 style="color:#D9502A;">🔥 Nouveau lead chaud — {score}/100</h2>
      <table style="width:100%; border-collapse: collapse;">
        <tr><td style="padding:6px 0;"><b>Produit recherché</b></td><td>{produit}</td></tr>
        <tr><td style="padding:6px 0;"><b>Budget</b></td><td>{budget}</td></tr>
        <tr><td style="padding:6px 0;"><b>Délai d'achat</b></td><td>{delai}</td></tr>
        <tr><td style="padding:6px 0;"><b>Contact</b></td><td>{contact}</td></tr>
      </table>
      <p style="color:#555; margin-top:16px;"><i>{justification}</i></p>
      <p style="color:#999; font-size:12px;">Session : {session_id}</p>
    </div>
    """

    try:
        resend.Emails.send({
            "from": "Lead Qualifier <othmanikhouloud0@gmail.com>",
            "to": [SALES_EMAIL],
            "subject": f"🔥 Nouveau lead chaud — {score}/100 — {produit}",
            "html": html,
        })
    except Exception as e:
        # On ne bloque jamais la conversation a cause d'un souci d'email
        print(f"[notifications] Erreur envoi email alerte : {e}")
