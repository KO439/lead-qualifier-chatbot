"""
Module RAG (Retrieval-Augmented Generation) : indexe le catalogue produits
dans une base vectorielle locale (ChromaDB, gratuit, pas de cle API) et
permet de retrouver les produits les plus pertinents par rapport a une
demande du visiteur.

ChromaDB utilise par defaut un modele d'embeddings local (all-MiniLM-L6-v2,
telecharge une seule fois), donc aucune cle API n'est necessaire pour le RAG.
"""
import chromadb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "products"


def get_collection():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def index_products(products: list):
    """
    Indexe (ou re-indexe) une liste de produits dans la base vectorielle.
    products : liste de dicts avec au moins id, nom, description, prix, categorie
    """
    collection = get_collection()

    ids = [p["id"] for p in products]
    documents = [
        f"{p['nom']}. {p['description']} Prix : {p['prix']} euros. "
        f"Catégorie : {p['categorie']}."
        for p in products
    ]
    metadatas = [
        {"nom": p["nom"], "prix": p["prix"], "categorie": p["categorie"]}
        for p in products
    ]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(products)


def search_products(query: str, n_results: int = 3) -> list:
    """
    Retourne les n produits les plus pertinents par rapport a une requete
    en langage naturel (ex: "un ordinateur pas cher pour les etudes").
    """
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, count),
    )

    products = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        products.append({
            "nom": meta.get("nom"),
            "prix": meta.get("prix"),
            "categorie": meta.get("categorie"),
            "description": doc,
        })
    return products
