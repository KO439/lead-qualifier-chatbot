
"""
Point d'entree de l'API. Orchestre 4 agents IA :
1. Agent conversationnel -> genere la reponse au visiteur (streaming)
2. Agent d'extraction -> extrait les infos structurees de la conversation
3. Agent de scoring -> calcule le score de qualification (regles, sans IA)
4. Agent d'analyse commerciale -> resume la conversation et recommande une
   action concrete au commercial

La recherche catalogue est declenchee uniquement lorsqu'une demande produit
est detectee.

Lancer avec :
    uvicorn main:app --reload

Puis tester sur :
    http://127.0.0.1:8000/docs
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


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Fichiers statiques
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory="static", html=True),
    name="static"
)


# ============================================================
# MODELES
# ============================================================

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


# ============================================================
# DETECTION DES DEMANDES CATALOGUE
# ============================================================

def _should_search_catalog(message: str) -> bool:
    """
    Determine si le message de l'utilisateur correspond a une
    demande de recherche dans le catalogue.

    Exemples qui doivent declencher une recherche :

        "Je veux voir les PC"
        "Vous avez des laptops ?"
        "Je cherche un Dell"
        "Je veux un PC a moins de 700 euros"
        "Je veux un MacBook"
        "Avez-vous un PC gamer ?"

    Les messages generaux comme "Bonjour", "Merci", etc.
    ne declenchent pas de recherche catalogue.
    """

    text = message.lower().strip()

    catalog_terms = [

        # ----------------------------------------------------
        # Consultation du catalogue
        # ----------------------------------------------------
        "voir les produits",
        "voir les pc",
        "voir les laptops",
        "voir les ordinateurs",
        "montre moi",
        "montrez moi",
        "montre-moi",
        "affiche",
        "afficher",
        "catalogue",
        "produits disponibles",
        "produits",

        # ----------------------------------------------------
        # Recherche
        # ----------------------------------------------------
        "je cherche",
        "je recherche",
        "je veux un",
        "je veux une",
        "je voudrais un",
        "je voudrais une",
        "avez-vous",
        "avez vous",
        "vous avez",
        "est-ce que vous avez",
        "est ce que vous avez",
        "disponible",
        "disponibles",

        # ----------------------------------------------------
        # Categories
        # ----------------------------------------------------
        "pc",
        "pcs",
        "ordinateur",
        "ordinateurs",
        "ordinateur portable",
        "ordinateurs portables",
        "pc portable",
        "pc portables",
        "laptop",
        "laptops",
        "notebook",
        "notebooks",

        # ----------------------------------------------------
        # Marques
        # ----------------------------------------------------
        "dell",
        "hp",
        "lenovo",
        "acer",
        "asus",
        "apple",
        "msi",
        "huawei",

        # ----------------------------------------------------
        # Produits / modeles
        # ----------------------------------------------------
        "macbook",
        "mac book",

        # ----------------------------------------------------
        # Prix
        # ----------------------------------------------------
        "moins de",
        "sous",
        "maximum",
        "max",
        "jusqu'a",
        "jusqu’à",
        "budget",
        "euros",
        "€",

        # ----------------------------------------------------
        # Gaming
        # ----------------------------------------------------
        "gamer",
        "gaming",
        "jeu",
        "jeux",
    ]

    return any(term in text for term in catalog_terms)


# ============================================================
# TRAITEMENT COMMUN APRES LA REPONSE DE LEA
# ============================================================

def _process_turn_after_reply(
    session,
    req,
    history,
    full_reply
):
    """
    Logique commune apres la generation de la reponse du bot.

    Effectue :
    - extraction
    - scoring
    - insight commercial
    - sauvegarde
    - alerte lead chaud
    """

    history.append({
        "role": "assistant",
        "content": full_reply
    })

    extracted = extract_info(history)

    scoring = compute_score(extracted)

    insight = generate_insight(
        history,
        extracted,
        scoring["score"],
        scoring["category"]
    )

    already_alerted = session.get("alerted", False)

    database.update_session(
        session_id=req.session_id,
        messages=history,
        extracted_info=extracted,
        score=scoring["score"],
        category=scoring["category"],
        justification=scoring["justification"],
        resume=insight.get("resume", ""),
        action_recommandee=insight.get(
            "action_recommandee",
            ""
        ),
        priorite=insight.get(
            "priorite",
            ""
        ),
    )

    if scoring["category"] == "chaud" and not already_alerted:

        send_hot_lead_alert(
            req.session_id,
            extracted,
            scoring["score"],
            scoring["justification"]
        )

        database.update_session(
            session_id=req.session_id,
            messages=history,
            alerted=True
        )

    return extracted, scoring, insight


# ============================================================
# ENDPOINT /chat
# ============================================================

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):

    # Recuperer ou creer la session
    session = database.get_or_create_session(
        req.session_id
    )

    # Recuperer l'historique
    history = json.loads(
        session["messages"]
    )

    # Ajouter le nouveau message utilisateur
    history.append({
        "role": "user",
        "content": req.message
    })

    # --------------------------------------------------------
    # RECHERCHE CATALOGUE
    # --------------------------------------------------------

    relevant_products = []

    if _should_search_catalog(req.message):

        relevant_products = search_products(
            req.message,
            n_results=3
        )

    # --------------------------------------------------------
    # REPONSE DE LEA
    # --------------------------------------------------------

    bot_reply = get_bot_reply(
        history,
        product_context=relevant_products
    )

    # --------------------------------------------------------
    # EXTRACTION + SCORING + INSIGHT
    # --------------------------------------------------------

    extracted, scoring, insight = _process_turn_after_reply(
        session,
        req,
        history,
        bot_reply
    )

    # --------------------------------------------------------
    # REPONSE API
    # --------------------------------------------------------

    return ChatResponse(
        reply=bot_reply,
        score=scoring["score"],
        category=scoring["category"],
        justification=scoring["justification"],
        extracted_info=extracted,
        resume=insight.get(
            "resume",
            ""
        ),
        action_recommandee=insight.get(
            "action_recommandee",
            ""
        ),
        priorite=insight.get(
            "priorite",
            ""
        ),
    )


# ============================================================
# ENDPOINT /chat/stream
# ============================================================

@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """
    Version streaming de /chat.

    La reponse de Lea est envoyee token par token via SSE.
    Une fois la reponse complete :
        extraction
        scoring
        insight commercial
    sont executes.
    """

    # Recuperer ou creer la session
    session = database.get_or_create_session(
        req.session_id
    )

    # Recuperer l'historique
    history = json.loads(
        session["messages"]
    )

    # Ajouter le message utilisateur
    history.append({
        "role": "user",
        "content": req.message
    })

    # --------------------------------------------------------
    # RECHERCHE CATALOGUE
    # --------------------------------------------------------

    relevant_products = []

    if _should_search_catalog(req.message):

        relevant_products = search_products(
            req.message,
            n_results=3
        )

    # --------------------------------------------------------
    # GENERATEUR SSE
    # --------------------------------------------------------

    def event_generator():

        full_reply = ""

        stream = get_bot_reply_stream(
            history,
            product_context=relevant_products
        )

        # ----------------------------------------------------
        # STREAMING DE LA REPONSE
        # ----------------------------------------------------

        for chunk in stream:

            delta = chunk.choices[0].delta.content

            if delta:

                full_reply += delta

                payload = json.dumps(
                    {
                        "type": "token",
                        "content": delta
                    },
                    ensure_ascii=False
                )

                yield f"data: {payload}\n\n"

        # ----------------------------------------------------
        # EXTRACTION + SCORING + INSIGHT
        # ----------------------------------------------------

        extracted, scoring, insight = _process_turn_after_reply(
            session,
            req,
            history,
            full_reply
        )

        # ----------------------------------------------------
        # EVENEMENT FINAL
        # ----------------------------------------------------

        final_payload = json.dumps(
            {
                "type": "done",
                "score": scoring["score"],
                "category": scoring["category"],
                "justification": scoring["justification"],
                "extracted_info": extracted,
                "resume": insight.get(
                    "resume",
                    ""
                ),
                "action_recommandee": insight.get(
                    "action_recommandee",
                    ""
                ),
                "priorite": insight.get(
                    "priorite",
                    ""
                ),
            },
            ensure_ascii=False
        )

        yield f"data: {final_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================================
# ENDPOINT /leads
# ============================================================

@app.get("/leads")
def get_leads(min_score: int = 0):
    """
    Retourne la liste des leads tries par score decroissant.
    """

    leads = database.list_leads(
        min_score=min_score
    )

    for lead in leads:

        lead["messages"] = json.loads(
            lead["messages"]
        )

        lead["extracted_info"] = json.loads(
            lead["extracted_info"]
        )

    return leads


# ============================================================
# STATISTIQUES
# ============================================================

@app.get("/leads/stats")
def get_leads_stats():
    """
    Retourne les statistiques agregees du dashboard.
    """

    leads = database.list_leads(
        min_score=0
    )

    total = len(leads)

    chaud = sum(
        1
        for l in leads
        if l["category"] == "chaud"
    )

    tiede = sum(
        1
        for l in leads
        if l["category"] == "tiede"
    )

    froid = sum(
        1
        for l in leads
        if l["category"] == "froid"
    )

    avg_score = (
        round(
            sum(l["score"] for l in leads) / total,
            1
        )
        if total
        else 0
    )

    produits_count = {}

    for lead in leads:

        info = json.loads(
            lead["extracted_info"]
        )

        produit = info.get(
            "produit_recherche"
        )

        if produit:

            produits_count[produit] = (
                produits_count.get(produit, 0) + 1
            )

    top_produits = sorted(
        produits_count.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    return {
        "total_leads": total,
        "chaud": chaud,
        "tiede": tiede,
        "froid": froid,
        "score_moyen": avg_score,
        "top_produits": [
            {
                "produit": produit,
                "mentions": count
            }
            for produit, count in top_produits
        ],
    }


# ============================================================
# PAGE PRINCIPALE
# ============================================================

@app.get("/")
def root():
    """
    Redirige vers l'interface du chatbot.
    """

     return RedirectResponse(url="/static/index.html")
