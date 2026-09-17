```python
"""
Recherche dans le catalogue produits.

La recherche combine :
- recherche sémantique avec ChromaDB ;
- filtres explicites : marque, catégorie, modèle et prix maximum.
"""

import chromadb
from pathlib import Path
import re
import unicodedata


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
    Normalise un texte :
    minuscules + suppression des accents.
    """
    text = str(text or "").lower().strip()

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    return text


def _extract_price_limit(query: str):
    """
    Exemples détectés :
    - moins de 700 €
    - moins de 700 euros
    - sous 700 €
    - maximum 700 €
    - max 700 €
    - jusqu'à 700 €
    """

    q = _normalize(query)

    patterns = [
        r"moins de\s+(\d+(?:[.,]\d+)?)",
        r"sous\s+(\d+(?:[.,]\d+)?)",
        r"(?:maximum|max)\s+(?:de\s+)?(\d+(?:[.,]\d+)?)",
        r"jusqu['’]?\s*(?:a\s*)?(\d+(?:[.,]\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)

        if match:
            return float(match.group(1).replace(",", "."))

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


def _extract_category(query: str):
    """
    Détecte la catégorie recherchée.
    """

    q = _normalize(query)

    if any(term in q for term in [
        "laptop",
        "laptops",
        "ordinateur portable",
        "pc portable",
        "notebook",
    ]):
        return "laptop"

    if any(term in q for term in [
        "pc gamer",
        "ordinateur gamer",
        "gaming pc",
        "gaming",
    ]):
        return "gamer"

    if "macbook" in q:
        return "macbook"

    if any(term in q for term in [
        "pc",
        "ordinateur",
        "computer",
    ]):
        return "pc"

    return None


def _matches_category(meta: dict, category: str) -> bool:
    """
    Vérifie qu'un produit appartient à la catégorie demandée.
    """

    nom = _normalize(meta.get("nom"))
    categorie = _normalize(meta.get("categorie"))

    if category == "laptop":
        return any(term in nom or term in categorie for term in [
            "laptop",
            "ordinateur portable",
            "pc portable",
            "notebook",
        ])

    if category == "gamer":
        return any(term in nom or term in categorie for term in [
            "gamer",
            "gaming",
        ])

    if category == "macbook":
        return "macbook" in nom

    if category == "pc":
        return any(term in nom or term in categorie for term in [
            "pc",
            "ordinateur",
            "laptop",
            "notebook",
        ])

    return True


def _matches_filters(meta: dict, query: str) -> bool:
    """
    Applique les filtres explicites présents dans la requête.
    """

    nom = _normalize(meta.get("nom"))
    prix = float(meta.get("prix", 0))

    # Marque
    brand = _extract_brand(query)

    if brand and brand not in nom:
        return False

    # Catégorie
    category = _extract_category(query)

    if category and not _matches_category(meta, category):
        return False

    # Prix maximum
    max_price = _extract_price_limit(query)

    if max_price is not None and prix > max_price:
        return False

    return True


def search_products(query: str, n_results: int = 3) -> list:
    """
    Recherche les produits correspondant à la demande.

    Si la demande contient des filtres explicites
    (marque, catégorie, prix), ils sont appliqués strictement.

    Sinon, ChromaDB utilise la recherche sémantique.
    """

    collection = get_collection()
    count = collection.count()

    if count == 0:
        return []

    brand = _extract_brand(query)
    category = _extract_category(query)
    max_price = _extract_price_limit(query)

    has_explicit_filter = (
        brand is not None
        or category is not None
        or max_price is not None
    )

    # ---------------------------------------------------------
    # CAS 1 : recherche avec filtre explicite
    # ---------------------------------------------------------

    if has_explicit_filter:

        results = collection.get(
            include=["documents", "metadatas"]
        )

        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        products = []

        for doc, meta in zip(docs, metas):

            if not _matches_filters(meta, query):
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

    # ---------------------------------------------------------
    # CAS 2 : recherche sémantique classique
    # ---------------------------------------------------------

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, count),
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    products = []

    for doc, meta in zip(docs, metas):
        products.append({
            "nom": meta.get("nom"),
            "prix": meta.get("prix"),
            "categorie": meta.get("categorie"),
            "description": doc,
        })

    return products
```
