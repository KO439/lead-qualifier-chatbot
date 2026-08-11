"""
Importe un catalogue de produits reel depuis un fichier CSV (potentiellement
des milliers de lignes) et les indexe automatiquement dans le RAG.

Aucun produit n'est ecrit a la main : ce script lit un export CSV standard
(le genre de fichier que n'importe quelle plateforme e-commerce sait
generer : Shopify, WooCommerce, Excel...) et alimente automatiquement la
base vectorielle ChromaDB.

Format CSV attendu (en-tetes de colonnes, ordre libre) :
    id,nom,description,prix,categorie

Exemple minimal :
    id,nom,description,prix,categorie
    1,Laptop Acer Aspire 3,"Ordinateur portable leger, 8Go RAM",349,ordinateur

Utilisation :
    python scripts/import_products_csv.py chemin/vers/mon_catalogue.csv

Si le fichier a des noms de colonnes differents (ex: "product_name" au lieu
de "nom"), utilisez --map pour faire correspondre :
    python scripts/import_products_csv.py fichier.csv \
        --map nom=product_name --map prix=price --map description=desc
"""
import csv
import sys
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from rag.catalog import index_products

REQUIRED_FIELDS = ["nom", "description", "prix", "categorie"]


def parse_args():
    parser = argparse.ArgumentParser(description="Importe un catalogue CSV dans le RAG")
    parser.add_argument("csv_path", help="Chemin vers le fichier CSV a importer")
    parser.add_argument(
        "--map", action="append", default=[],
        help="Mappage colonne_attendue=colonne_reelle, ex: --map nom=product_name"
    )
    parser.add_argument(
        "--delimiter", default=",",
        help="Separateur du CSV (par defaut ','). Utilisez ';' pour les exports Excel FR."
    )
    return parser.parse_args()


def build_column_mapping(map_args: list) -> dict:
    mapping = {field: field for field in REQUIRED_FIELDS}
    mapping["id"] = "id"
    for entry in map_args:
        if "=" not in entry:
            continue
        expected, actual = entry.split("=", 1)
        mapping[expected.strip()] = actual.strip()
    return mapping


def import_csv(csv_path: str, column_mapping: dict, delimiter: str):
    products = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        missing_cols = [
            column_mapping[field] for field in REQUIRED_FIELDS
            if column_mapping[field] not in reader.fieldnames
        ]
        if missing_cols:
            print(f"❌ Colonnes manquantes dans le CSV : {missing_cols}")
            print(f"   Colonnes trouvées : {reader.fieldnames}")
            print("   Utilisez --map pour faire correspondre vos colonnes, ex :")
            print("   --map nom=Product_Name --map prix=Price")
            sys.exit(1)

        for i, row in enumerate(reader, 1):
            try:
                product_id = row.get(column_mapping.get("id", "id"), "") or f"csv-{i}"
                prix_raw = row[column_mapping["prix"]].replace(",", ".").replace("€", "").replace("DT", "").strip()

                products.append({
                    "id": str(product_id),
                    "nom": row[column_mapping["nom"]].strip(),
                    "description": row[column_mapping["description"]].strip(),
                    "prix": float(prix_raw) if prix_raw else 0,
                    "categorie": row[column_mapping["categorie"]].strip(),
                })
            except (KeyError, ValueError) as e:
                print(f"⚠️  Ligne {i} ignorée (erreur : {e})")
                continue

    if not products:
        print("❌ Aucun produit valide trouvé dans le fichier.")
        sys.exit(1)

    print(f"📦 {len(products)} produits lus depuis {csv_path}")
    print("🔄 Indexation dans la base vectorielle (peut prendre un moment pour de gros volumes)...")

    count = index_products(products)

    print(f"✅ {count} produits indexés avec succès dans le RAG.")
    print("   Le chatbot peut maintenant les recommander.")


if __name__ == "__main__":
    args = parse_args()
    mapping = build_column_mapping(args.map)
    import_csv(args.csv_path, mapping, args.delimiter)
