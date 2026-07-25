"""
Point d'entree de l'API. Orchestre :
1. Agent conversationnel -> genere la reponse au visiteur
2. Agent d'extraction -> extrait les infos structurees de la conversation
3. Agent de scoring -> calcule le score de qualification

Lancer avec : uvicorn main:app --reload
Puis tester sur : http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import json

from agents.conversational_agent import get_bot_reply
from agents.extraction_agent import extract_info
from agents.scoring_agent import compute_score
from rag.catalog import search_products
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

# Sert la page de demo e-commerce + le widget de chat
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


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session = database.get_or_create_session(req.session_id)
    history = json.loads(session["messages"])

    # 1. Ajouter le message utilisateur a l'historique
    history.append({"role": "user", "content": req.message})

    # 2. RAG : chercher des produits pertinents par rapport au message du visiteur
    relevant_products = search_products(req.message, n_results=3)

    # 3. Agent conversationnel : generer la reponse (avec contexte produits)
    bot_reply = get_bot_reply(history, product_context=relevant_products)
    history.append({"role": "assistant", "content": bot_reply})

    # 4. Agent d'extraction : mettre a jour les infos connues sur ce lead
    extracted = extract_info(history)

    # 5. Agent de scoring : recalculer le score en continu
    scoring = compute_score(extracted)

    # 6. Sauvegarder en base
    database.update_session(
        session_id=req.session_id,
        messages=history,
        extracted_info=extracted,
        score=scoring["score"],
        category=scoring["category"],
        justification=scoring["justification"],
    )

    return ChatResponse(
        reply=bot_reply,
        score=scoring["score"],
        category=scoring["category"],
        justification=scoring["justification"],
        extracted_info=extracted,
    )


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