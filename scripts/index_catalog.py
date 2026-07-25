"""
Script a lancer une seule fois (ou a chaque mise a jour du catalogue) pour
indexer les produits dans la base vectorielle ChromaDB.

Lancer avec : python scripts/index_catalog.py
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from rag.catalog import index_products

CATALOG_PATH = Path(__file__).parent.parent / "data" / "products_catalog.json"


def main():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        products = json.load(f)

    count = index_products(products)
    print(f"{count} produits indexés avec succès dans la base vectorielle.")
    print("Vous pouvez maintenant tester avec : python test_conversation.py")


if __name__ == "__main__":
    main()
