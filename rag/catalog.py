```python
"""
Module RAG : recherche hybride dans le catalogue produits.

- ChromaDB : recherche sémantique
- Filtres structurés : marque, catégorie, prix
- Vérification des produits réellement présents dans le catalogue
"""

import chromadb
from pathlib import Path
import re

DB_PATH = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "products"


def get_collection():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def index_products(products: list):
    """
    Indexe ou ré-indexe une liste de produits.
    """
    collection = get_collection()

    ids = [str(p["id"]) for p in products]

    documents = [
        f"{p['nom']}. {p['description']} Prix : {p['prix']} euros. "
        f"Catégorie : {p['categorie']}."
        for p in products
    ]

    metadatas = [
        {
            "nom": p["nom"],
            "prix": p["prix"],
            "categorie": p["categorie"],
        }
        for p in products
    ]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    return len(products)


def _normalize(text: str) -> str:
    """
    Normalise un texte pour faciliter les recherches.
    """
    if not text:
        return ""

    text = text.lower().strip()

    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def _extract_price_limit(query: str):
    """
    Détecte des expressions comme :
    - moins de 700 euros
    - moins de 700 €
    - sous 700 €
    - max 700 €
    - jusqu'à 700 €
    """
    query_normalized = _normalize(query)

    patterns = [
        r"moins de\s+(\d+(?:[.,]\d+)?)",
        r"sous\s+(\d+(?:[.,]\d+)?)",
        r"max(?:imum)?\s+(?:de\s+)?(\d+(?:[.,]\d+)?)",
        r"jusqu['’]?\s*(?:a|à)?\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*(?:€|euros?)\s*(?:maximum|max|ou moins)",
    ]

    for pattern in patterns:
        match = re.search(pattern, query_normalized)

        if match:
            return float(match.group(1).replace(",", "."))

    return None


def _extract_category(query: str):
    """
    Détecte les catégories courantes du catalogue.
    """
    q = _normalize(query)

    if any(word in q for word in [
        "laptop",
        "laptops",
        "ordinateur portable",
        "pc portable",
        "notebook",
    ]):
        return "laptop"

    if any(word in q for word in [
        "pc gamer",
        "ordinateur gamer",
        "gaming pc",
        "gaming",
    ]):
        return "gamer"

    if any(word in q for word in [
        "pc",
        "ordinateur",
        "computeur",
        "computer",
    ]):
        return "pc"

    if "macbook" in q:
        return "macbook"

    return None


def _extract_brand(query: str):
    """
    Détecte les marques explicitement demandées.
    """
    q = _normalize(query)

    brands = [
        "dell",
        "hp",
        "lenovo",
        "acer",
        "asus",
        "apple",
        "msi",
        "huawei",
    ]

    for brand in brands:
        if re.search(rf"\b{re.escape(brand)}\b", q):
            return brand

    return None


def _metadata_matches(meta: dict, query: str) -> bool:
    """
    Vérifie les filtres explicites demandés par l'utilisateur.
    """

    q = _normalize(query)

    nom = _normalize(str(meta.get("nom", "")))
    categorie = _normalize(str(meta.get("categorie", "")))
    prix = float(meta.get("prix", 0))

    # Prix maximum
    max_price = _extract_price_limit(query)

    if max_price is not None and prix > max_price:
        return False

    # Marque
    brand = _extract_brand(query)

    if brand is not None and brand not in nom:
        return False

    # Catégorie
    category = _extract_category(query)

    if category == "laptop":
        if not any(word in nom or word in categorie for word in [
            "laptop",
            "ordinateur portable",
            "pc portable",
            "notebook",
        ]):
            return False

    elif category == "gamer":
        if not any(word in nom or word in categorie for word in [
            "gamer",
            "gaming",
        ]):
            return False

    elif category == "macbook":
        if "macbook" not in nom:
            return False

    elif category == "pc":
        if not any(word in nom or word in categorie for word in [
            "pc",
            "ordinateur",
            "laptop",
            "notebook",
        ]):
            return False

    return True


def search_products(query: str, n_results: int = 3) -> list:
    """
    Recherche hybride.

    Exemple :
        "Je cherche un Dell à moins de 700 euros"

    applique :
        marque = Dell
        prix <= 700

    avant de retourner les produits.
    """

    collection = get_collection()

    count = collection.count()

    if count == 0:
        return []

    # On récupère suffisamment de résultats pour pouvoir
    # appliquer les filtres correctement.
    results = collection.query(
        query_texts=[query],
        n_results=count,
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    products = []

    for doc, meta in zip(docs, metas):

        if not _metadata_matches(meta, query):
            continue

        products.append({
            "nom": meta.get("nom"),
            "prix": meta.get("prix"),
            "categorie": meta.get("categorie"),
            "description": doc,
        })

        if len(products) >= n_results:
            break

    return products
```
