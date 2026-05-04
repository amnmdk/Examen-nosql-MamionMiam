import os
import sys
import json
import zipfile
import requests
from pymongo import MongoClient, GEOSPHERE, ASCENDING

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "mamionmiam"
DATA_URL  = "https://data.atontour.info/IABD/mamionmiam.zip"
DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
ZIP_PATH  = os.path.join(DATA_DIR, "mamionmiam.zip")

COLLECTIONS = {
    "shops":       "shops.json",
    "clients":     "clients.json",
    "parrainages": "parrainages.json",
    "entreprises": "entreprises.json",
    "achats":      "achats.json",
    "produits":    "produits.json",
}

def download_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(ZIP_PATH):
        print("[OK] Données déjà téléchargées.")
        return
    print(f"Téléchargement depuis {DATA_URL} ...")
    r = requests.get(DATA_URL, stream=True, timeout=60)
    r.raise_for_status()
    with open(ZIP_PATH, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print("[OK] Téléchargement terminé.")

def extract_data():
    for root, _, files in os.walk(DATA_DIR):
        if "shops.json" in files:
            print("[OK] Données déjà extraites.")
            return root
    print("Extraction du ZIP ...")
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(DATA_DIR)
    print("[OK] Extraction terminée.")
    for root, _, files in os.walk(DATA_DIR):
        if "shops.json" in files:
            return root
    return DATA_DIR

def to_geojson_point(lng, lat):
    return {"type": "Point", "coordinates": [float(lng), float(lat)]}

def transform_clients(docs):
    for d in docs:
        coords = d.get("coords")
        if isinstance(coords, dict) and "lat" in coords and "lng" in coords:
            d["location"] = to_geojson_point(coords["lng"], coords["lat"])
    return docs

def transform_shops(docs):
    for d in docs:
        if "lat" in d and "lng" in d:
            d["location"] = to_geojson_point(d["lng"], d["lat"])
    return docs

def transform_entreprises(docs):
    for d in docs:
        coords = d.get("coords")
        if isinstance(coords, dict) and "lat" in coords and "lng" in coords:
            d["location"] = to_geojson_point(coords["lng"], coords["lat"])
    return docs

TRANSFORMS = {
    "clients":     transform_clients,
    "shops":       transform_shops,
    "entreprises": transform_entreprises,
}

def load_into_mongo(data_path):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    for col_name, filename in COLLECTIONS.items():
        filepath = os.path.join(data_path, filename)
        if not os.path.exists(filepath):
            print(f"[WARN] {filepath} introuvable – ignoré.")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if col_name in TRANSFORMS:
            data = TRANSFORMS[col_name](data)

        db[col_name].drop()
        if data:
            db[col_name].insert_many(data)
        print(f"[OK] {col_name:15s} → {len(data):6d} documents insérés")

    print("\nCréation des index...")
    db.clients.create_index([("location", GEOSPHERE)])
    db.clients.create_index([("id", ASCENDING)])
    db.shops.create_index([("location", GEOSPHERE)])
    db.shops.create_index([("id", ASCENDING)])
    db.produits.create_index([("SKU", ASCENDING)])
    db.achats.create_index([("acheteur", ASCENDING)])
    db.achats.create_index([("ticket", ASCENDING)])
    db.parrainages.create_index([("idParrain", ASCENDING)])
    db.parrainages.create_index([("idFilleul", ASCENDING)])
    db.entreprises.create_index([("siret", ASCENDING)])
    print("[OK] Index créés.")

    print("\n=== Résumé des collections ===")
    for col_name in COLLECTIONS:
        n = db[col_name].count_documents({})
        print(f"  {col_name:15s}: {n} documents")

    client.close()
    print("\n✓ Chargement terminé avec succès!")

if __name__ == "__main__":
    try:
        download_data()
        data_path = extract_data()
        load_into_mongo(data_path)
    except requests.exceptions.ConnectionError:
        print("[ERREUR] Impossible de télécharger les données. Vérifiez votre connexion.")
        sys.exit(1)
    except Exception as e:
        print(f"[ERREUR] {e}")
        sys.exit(1)
