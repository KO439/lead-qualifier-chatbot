"""
Recherche dans le catalogue produits.

La recherche combine :
- recherche exacte / filtrée pour les marques, catégories et prix ;
- recherche sémantique ChromaDB pour les demandes plus générales.
"""

import re
import unicodedata
from pathlib import Path

import chromadb


DB_PATH = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "products"


def get_collection():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def _normalize(text: str) -> str:
    """Normalise un texte pour faciliter les comparaisons."""
    text = str(text).lower().strip()

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    return text


def index_products(products: list):
    """
    Indexe ou ré-indexe les produits dans ChromaDB.
    """

    collection = get_collection()

    ids = [p["id"] for p in products]

    documents = [
        (
            f"{p['nom']}. "
            f"{p['description']} "
            f"Prix : {p['prix']} euros. "
            f"Catégorie : {p['categorie']}."
        )
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


def _extract_price_limit(query: str):
    """
    Détecte les demandes du type :
    - moins de 700 €
    - sous 700 euros
    - maximum 700 €
    - jusqu'à 700 €
    """

    text = _normalize(query)

    patterns = [
        r"(?:moins de|sous|maximum|max|jusqu'a|jusqu a|au maximum|pas plus de)\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*(?:euros?|€)\s*(?:maximum|max|ou moins)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except ValueError:
                pass

    return None


def _extract_brand(query: str):
    """
    Détecte les marques présentes dans le catalogue.
    """

    text = _normalize(query)

    brands = {
        "acer": "acer",
        "dell": "dell",
        "apple": "apple",
        "macbook": "apple",
        "samsung": "samsung",
        "iphone": "apple",
        "jbl": "jbl",
        "sony": "sony",
        "logitech": "logitech",
        "asus": "asus",
    }

    for keyword, brand in brands.items():
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            return brand

    return None


def _extract_category(query: str):
    """
    Détecte la catégorie demandée.
    """

    text = _normalize(query)

    # Ordinateurs portables
    if any(
        term in text
        for term in [
            "pc",
            "pcs",
            "ordinateur portable",
            "ordinateurs portables",
            "pc portable",
            "pc portables",
            "laptop",
            "laptops",
            "notebook",
            "notebooks",
            "macbook",
        ]
    ):
        return "ordinateur portable"

    # Smartphones
    if any(
        term in text
        for term in [
            "smartphone",
            "smartphones",
            "telephone",
            "telephones",
            "iphone",
        ]
    ):
        return "smartphone"

    # Tablettes
    if any(
        term in text
        for term in [
            "tablette",
            "tablettes",
        ]
    ):
        return "tablette"

    # Audio
    if any(
        term in text
        for term in [
            "ecouteur",
            "ecouteurs",
            "casque",
            "casques",
            "audio",
        ]
    ):
        return "accessoire audio"

    # Accessoires informatiques
    if any(
        term in text
        for term in [
            "souris",
            "ecran",
            "écran",
            "webcam",
            "accessoire informatique",
            "accessoires informatiques",
        ]
    ):
        return "accessoire informatique"

    return None


def _matches_category(product: dict, category: str) -> bool:
    return _normalize(product.get("categorie", "")) == _normalize(category)


def _matches_brand(product: dict, brand: str) -> bool:
    """
    Vérifie la marque dans le nom du produit.
    """

    name = _normalize(product.get("nom", ""))

    if brand == "apple":
        return (
            "apple" in name
            or "macbook" in name
            or "iphone" in name
        )

    return brand in name


def _product_to_dict(product_id, metadata, document):
    return {
        "id": product_id,
        "nom": metadata.get("nom"),
        "prix": metadata.get("prix"),
        "categorie": metadata.get("categorie"),
        "description": document,
    }


def _get_all_products(collection):
    """
    Récupère tous les produits actuellement indexés.
    """

    data = collection.get(
        include=["documents", "metadatas"]
    )

    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])

    products = []

    for product_id, document, metadata in zip(
        ids,
        documents,
        metadatas,
    ):
        products.append(
            _product_to_dict(
                product_id,
                metadata,
                document,
            )
        )

    return products


def search_products(query: str, n_results: int = 3) -> list:
    """
    Recherche des produits selon la demande utilisateur.

    Exemples :

    "Je veux voir les PC"
        -> tous les ordinateurs portables

    "Je cherche un Dell"
        -> produits Dell

    "Je veux un PC à moins de 700 €"
        -> laptops <= 700 €

    "Je veux un MacBook"
        -> MacBook

    "Avez-vous un smartphone ?"
        -> smartphones

    Si aucun filtre explicite n'est détecté,
    une recherche sémantique ChromaDB est utilisée.
    """

    collection = get_collection()

    if collection.count() == 0:
        return []

    price_limit = _extract_price_limit(query)
    brand = _extract_brand(query)
    category = _extract_category(query)

    # ---------------------------------------------------------
    # CAS 1 : recherche avec filtre explicite
    # ---------------------------------------------------------

    if price_limit is not None or brand is not None or category is not None:

        all_products = _get_all_products(collection)

        filtered_products = []

        for product in all_products:

            # Filtre catégorie
            if category is not None:
                if not _matches_category(product, category):
                    continue

            # Filtre marque
            if brand is not None:
                if not _matches_brand(product, brand):
                    continue

            # Filtre prix
            if price_limit is not None:
                try:
                    product_price = float(product.get("prix", 0))
                except (TypeError, ValueError):
                    continue

                if product_price > price_limit:
                    continue

            filtered_products.append(product)

        # Tri par prix croissant
        filtered_products.sort(
            key=lambda p: float(p.get("prix", 0))
        )

        return filtered_products

    # ---------------------------------------------------------
    # CAS 2 : recherche sémantique
    # ---------------------------------------------------------

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
    )

    products = []

    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    for product_id, doc, meta in zip(
        ids,
        docs,
        metas,
    ):
        products.append(
            _product_to_dict(
                product_id,
                meta,
                doc,
            )
        )

    return products
