import math
import sys
from pymongo import MongoClient
from neo4j import GraphDatabase

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "mamionmiam"
NEO4J_URI  = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "password")
RAYON_KM   = 4.0
BATCH_SIZE = 500

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

def run_batch(session, query, batch):
    session.run(query, items=batch)

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

with driver.session() as session:

    print("Nettoyage de Neo4J...")
    session.run("MATCH (n) DETACH DELETE n")
    print("[OK] Neo4J vidé.")

    print("Chargement des clients...")
    clients_raw = list(db.clients.find({}, {
        "_id": 0, "id": 1, "nom": 1, "prenom": 1,
        "genre": 1, "naissance": 1, "commune": 1, "coords": 1
    }))

    clients_data = []
    for c in clients_raw:
        coords = c.get("coords") or {}
        clients_data.append({
            "id":        c.get("id"),
            "nom":       c.get("nom", ""),
            "prenom":    c.get("prenom", ""),
            "genre":     c.get("genre", ""),
            "naissance": str(c.get("naissance", "")),
            "commune":   c.get("commune", ""),
            "lat":       coords.get("lat"),
            "lng":       coords.get("lng"),
        })

    q_client = """
    UNWIND $items AS c
    MERGE (n:Client {id: c.id})
    SET n.nom       = c.nom,
        n.prenom    = c.prenom,
        n.genre     = c.genre,
        n.naissance = c.naissance,
        n.commune   = c.commune,
        n.lat       = c.lat,
        n.lng       = c.lng
    """
    for i in range(0, len(clients_data), BATCH_SIZE):
        session.run(q_client, items=clients_data[i:i + BATCH_SIZE])
    print(f"[OK] {len(clients_data)} clients chargés.")

    session.run("CREATE INDEX client_id IF NOT EXISTS FOR (n:Client) ON (n.id)")

    print("Chargement des domaines d'activité...")
    entreprises_raw = list(db.entreprises.find({}, {"_id": 0}))
    domaines = {}
    for e in entreprises_raw:
        code  = e.get("domain_code", "")
        label = e.get("domain_label", "")
        if code:
            domaines[code] = label

    q_domain = """
    UNWIND $items AS d
    MERGE (n:DomainActivite {code: d.code})
    SET n.label = d.label
    """
    domain_list = [{"code": k, "label": v} for k, v in domaines.items()]
    session.run(q_domain, items=domain_list)
    print(f"[OK] {len(domain_list)} domaines chargés.")

    print("Chargement des entreprises...")
    ent_data = []
    for e in entreprises_raw:
        ent_data.append({
            "siret":      str(e.get("siret", "")),
            "nom":        e.get("nom", ""),
            "domainCode": e.get("domain_code", ""),
        })

    q_ent = """
    UNWIND $items AS e
    MERGE (n:Entreprise {siret: e.siret})
    SET n.nom = e.nom
    WITH n, e
    MATCH (d:DomainActivite {code: e.domainCode})
    MERGE (n)-[:IN_DOMAIN]->(d)
    """
    for i in range(0, len(ent_data), BATCH_SIZE):
        session.run(q_ent, items=ent_data[i:i + BATCH_SIZE])
    print(f"[OK] {len(ent_data)} entreprises chargées.")

    print("Création des relations WORKS_AT...")
    works_data = []
    for c in db.clients.find({"entreprise.siret": {"$exists": True, "$ne": None}},
                              {"_id": 0, "id": 1, "entreprise": 1}):
        ent = c.get("entreprise")
        if ent and ent.get("siret"):
            works_data.append({
                "clientId": c["id"],
                "siret":    str(ent["siret"])
            })

    q_works = """
    UNWIND $items AS w
    MATCH (c:Client {id: w.clientId})
    MATCH (e:Entreprise {siret: w.siret})
    MERGE (c)-[:WORKS_AT]->(e)
    """
    for i in range(0, len(works_data), BATCH_SIZE):
        session.run(q_works, items=works_data[i:i + BATCH_SIZE])
    print(f"[OK] {len(works_data)} relations WORKS_AT créées.")

    print("Création des relations PARRAINE...")
    parr_raw = list(db.parrainages.find({}, {"_id": 0}))
    parr_data = [
        {"idParrain": p["idParrain"], "idFilleul": p["idFilleul"],
         "date": str(p.get("dateParrainage", ""))}
        for p in parr_raw
    ]

    q_parr = """
    UNWIND $items AS p
    MATCH (a:Client {id: p.idParrain})
    MATCH (b:Client {id: p.idFilleul})
    MERGE (a)-[r:PARRAINE]->(b)
    SET r.date = p.date
    """
    for i in range(0, len(parr_data), BATCH_SIZE):
        session.run(q_parr, items=parr_data[i:i + BATCH_SIZE])
    print(f"[OK] {len(parr_data)} relations PARRAINE créées.")

    print("Chargement des magasins...")
    shops_raw = list(db.shops.find({}, {"_id": 0}))
    shop_data = [
        {
            "id":      s.get("id", ""),
            "nom":     s.get("name", ""),
            "adresse": s.get("adresse", ""),
            "lat":     s.get("lat"),
            "lng":     s.get("lng"),
        }
        for s in shops_raw
    ]

    q_shop = """
    UNWIND $items AS s
    MERGE (n:Shop {id: s.id})
    SET n.nom     = s.nom,
        n.adresse = s.adresse,
        n.lat     = s.lat,
        n.lng     = s.lng
    """
    session.run(q_shop, items=shop_data)
    print(f"[OK] {len(shop_data)} magasins chargés.")

    print(f"Calcul des abonnés dans {RAYON_KM} km de chaque magasin...")
    sponsor_data = []
    for shop in shops_raw:
        slat = shop.get("lat")
        slng = shop.get("lng")
        if slat is None or slng is None:
            continue
        for c in clients_data:
            clat = c.get("lat")
            clng = c.get("lng")
            if clat is None or clng is None:
                continue
            dist = haversine_km(slat, slng, clat, clng)
            if dist <= RAYON_KM:
                sponsor_data.append({
                    "shopId":   shop.get("id", ""),
                    "clientId": c["id"],
                    "dist_km":  round(dist, 3)
                })

    q_sponsor = """
    UNWIND $items AS s
    MATCH (sh:Shop {id: s.shopId})
    MATCH (c:Client {id: s.clientId})
    MERGE (sh)-[r:SPONSOR]->(c)
    SET r.dist_km = s.dist_km
    """
    for i in range(0, len(sponsor_data), BATCH_SIZE):
        session.run(q_sponsor, items=sponsor_data[i:i + BATCH_SIZE])
    print(f"[OK] {len(sponsor_data)} relations SPONSOR créées.")

driver.close()
mongo_client.close()
print("\n✓ Graphe Neo4J chargé avec succès!")
