"""
Point d'entree de l'API. Orchestre 4 agents IA :
1. Agent conversationnel -> genere la reponse au visiteur (streaming)
2. Agent d'extraction -> extrait les infos structurees de la conversation
3. Agent de scoring -> calcule le score de qualification (regles, sans IA,
   pour rester explicable)
4. Agent d'analyse commerciale -> resume la conversation et recommande une
   action concrete au commercial (raisonnement IA de haut niveau, generique
   a n'importe quel secteur)

Lancer avec : uvicorn main:app --reload
Puis tester sur : http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
import json

from agents.conversational_agent import get_bot_reply, get_bot_reply_stream
from agents.extraction_agent import extract_info
from agents.scoring_agent import compute_score
from agents.insight_agent import generate_insight
from rag.catalog import search_products
from notifications import send_hot_lead_alert
import database

app = FastAPI(title="Chatbot IA de qualification de leads")
database.init_db()

# CORS : autorise le widget web (servi depuis n'importe quelle origine en dev)
# a appeler cette API depuis le navigateur.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sert la page de demo e-commerce + le widget de chat sur http://127.0.0.1:8000/
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    score: int
    category: str
    justification: str
    extracted_info: dict
    resume: str = ""
    action_recommandee: str = ""
    priorite: str = ""


def _process_turn_after_reply(session, req, history, full_reply):
    """
    Logique commune apres la generation de la reponse du bot (streaming ou
    non) : extraction, scoring, insight commercial, sauvegarde, alerte.
    """
    history.append({"role": "assistant", "content": full_reply})

    extracted = extract_info(history)
    scoring = compute_score(extracted)
    insight = generate_insight(history, extracted, scoring["score"], scoring["category"])

    already_alerted = session.get("alerted", False)

    database.update_session(
        session_id=req.session_id,
        messages=history,
        extracted_info=extracted,
        score=scoring["score"],
        category=scoring["category"],
        justification=scoring["justification"],
        resume=insight.get("resume", ""),
        action_recommandee=insight.get("action_recommandee", ""),
        priorite=insight.get("priorite", ""),
    )

    if scoring["category"] == "chaud" and not already_alerted:
        send_hot_lead_alert(req.session_id, extracted, scoring["score"], scoring["justification"])
        database.update_session(session_id=req.session_id, messages=history, alerted=True)

    return extracted, scoring, insight


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session = database.get_or_create_session(req.session_id)
    history = json.loads(session["messages"])
    history.append({"role": "user", "content": req.message})

    relevant_products = search_products(req.message, n_results=3)
    bot_reply = get_bot_reply(history, product_context=relevant_products)

    extracted, scoring, insight = _process_turn_after_reply(session, req, history, bot_reply)

    return ChatResponse(
        reply=bot_reply,
        score=scoring["score"],
        category=scoring["category"],
        justification=scoring["justification"],
        extracted_info=extracted,
        resume=insight.get("resume", ""),
        action_recommandee=insight.get("action_recommandee", ""),
        priorite=insight.get("priorite", ""),
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """
    Version streaming de /chat : renvoie la reponse de Lea token par token
    au format Server-Sent Events (SSE). Une fois la reponse complete
    generee, extraction + scoring + insight commercial tournent, et le
    resultat final est envoye dans un dernier evenement "done".
    """
    session = database.get_or_create_session(req.session_id)
    history = json.loads(session["messages"])
    history.append({"role": "user", "content": req.message})

    relevant_products = search_products(req.message, n_results=3)

    def event_generator():
        full_reply = ""
        stream = get_bot_reply_stream(history, product_context=relevant_products)

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_reply += delta
                payload = json.dumps({"type": "token", "content": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

        extracted, scoring, insight = _process_turn_after_reply(session, req, history, full_reply)

        final_payload = json.dumps({
            "type": "done",
            "score": scoring["score"],
            "category": scoring["category"],
            "justification": scoring["justification"],
            "extracted_info": extracted,
            "resume": insight.get("resume", ""),
            "action_recommandee": insight.get("action_recommandee", ""),
            "priorite": insight.get("priorite", ""),
        }, ensure_ascii=False)
        yield f"data: {final_payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/leads")
def get_leads(min_score: int = 0):
    """Retourne la liste des leads, triee par score decroissant."""
    leads = database.list_leads(min_score=min_score)
    for lead in leads:
        lead["messages"] = json.loads(lead["messages"])
        lead["extracted_info"] = json.loads(lead["extracted_info"])
    return leads


@app.get("/leads/stats")
def get_leads_stats():
    """Retourne des statistiques agregees pour le dashboard analytique."""
    leads = database.list_leads(min_score=0)

    total = len(leads)
    chaud = sum(1 for l in leads if l["category"] == "chaud")
    tiede = sum(1 for l in leads if l["category"] == "tiede")
    froid = sum(1 for l in leads if l["category"] == "froid")
    avg_score = round(sum(l["score"] for l in leads) / total, 1) if total else 0

    produits_count = {}
    for l in leads:
        info = json.loads(l["extracted_info"])
        produit = info.get("produit_recherche")
        if produit:
            produits_count[produit] = produits_count.get(produit, 0) + 1

    top_produits = sorted(produits_count.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_leads": total,
        "chaud": chaud,
        "tiede": tiede,
        "froid": froid,
        "score_moyen": avg_score,
        "top_produits": [{"produit": p, "mentions": c} for p, c in top_produits],
    }


@app.get("/")
def root():
    """Redirige l'accès à la racine directement vers l'interface du chatbot."""
    return RedirectResponse(url="/static/index.html")
