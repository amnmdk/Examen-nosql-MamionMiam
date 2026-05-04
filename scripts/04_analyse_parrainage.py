import os
from datetime import datetime, date

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tabulate import tabulate
from pymongo import MongoClient
from neo4j import GraphDatabase

MONGO_URI  = "mongodb://localhost:27017/"
DB_NAME    = "mamionmiam"
NEO4J_URI  = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "password")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

mongo_client = MongoClient(MONGO_URI)
db    = mongo_client[DB_NAME]
driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

def titre(texte):
    print("\n" + "=" * 60)
    print(f"  {texte}")
    print("=" * 60)

def afficher(rows, headers):
    print(tabulate(rows, headers=headers, tablefmt="pipe"))

def sauver_fig(nom):
    path = os.path.join(OUTPUT_DIR, nom)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"[PNG] → {path}")

def cypher(query, **params):
    with driver.session() as s:
        return list(s.run(query, **params))

def age_depuis_naissance(naissance_str):
    try:
        if isinstance(naissance_str, str):
            naissance = datetime.strptime(naissance_str[:10], "%Y-%m-%d").date()
        elif isinstance(naissance_str, date):
            naissance = naissance_str
        else:
            return None
        today = date.today()
        return (today - naissance).days // 365
    except Exception:
        return None

def tranche_age(age):
    if age is None:
        return "Inconnu"
    if age <= 27:
        return "18-27"
    elif age <= 37:
        return "28-37"
    elif age <= 47:
        return "38-47"
    elif age <= 57:
        return "48-57"
    elif age <= 67:
        return "58-67"
    else:
        return "68+"

titre("Q1 – Personne ayant parrainé le plus de personnes")

res_q1 = cypher("""
MATCH (p:Client)-[:PARRAINE]->(f:Client)
WITH p, count(f) AS nb_filleuls
ORDER BY nb_filleuls DESC
LIMIT 1
MATCH (p)-[:PARRAINE]->(filleul:Client)
RETURN p.prenom + ' ' + p.nom AS parrain,
       nb_filleuls,
       collect(filleul.prenom + ' ' + filleul.nom) AS filleuls
""")
if res_q1:
    r = res_q1[0]
    print(f"Parrain     : {r['parrain']}")
    print(f"Nb filleuls : {r['nb_filleuls']}")
    print(f"Filleuls    : {', '.join(r['filleuls'][:10])}{'...' if len(r['filleuls'])>10 else ''}")

titre("Q2 – H/F ayant parrainé / été parrainés")

res_parrains_genre = cypher("""
MATCH (p:Client)-[:PARRAINE]->(:Client)
WITH DISTINCT p
RETURN p.genre AS genre, count(*) AS nb_parrains
ORDER BY genre
""")
res_filleuls_genre = cypher("""
MATCH (:Client)-[:PARRAINE]->(f:Client)
WITH DISTINCT f
RETURN f.genre AS genre, count(*) AS nb_filleuls
ORDER BY genre
""")
print("Parrains par genre :")
afficher([(r["genre"], r["nb_parrains"]) for r in res_parrains_genre],
         headers=["Genre", "Nb parrains"])
print("Filleuls par genre :")
afficher([(r["genre"], r["nb_filleuls"]) for r in res_filleuls_genre],
         headers=["Genre", "Nb filleuls"])

titre("Q3 – Répartition H/F des parrains")

genres3  = [r["genre"] for r in res_parrains_genre]
vals3    = [r["nb_parrains"] for r in res_parrains_genre]
colors3  = ["#4C72B0", "#DD8452", "#cccccc"][:len(genres3)]

fig, ax = plt.subplots(figsize=(5, 5))
ax.pie(vals3, labels=genres3, autopct="%1.1f%%", colors=colors3, startangle=90)
ax.set_title("Répartition H/F des parrains")
sauver_fig("q3_repartition_parrains.png")

titre("Q4 – Répartition H/F des filleuls")

genres4 = [r["genre"] for r in res_filleuls_genre]
vals4   = [r["nb_filleuls"] for r in res_filleuls_genre]

fig, ax = plt.subplots(figsize=(5, 5))
ax.pie(vals4, labels=genres4, autopct="%1.1f%%", colors=colors3, startangle=90)
ax.set_title("Répartition H/F des filleuls")
sauver_fig("q4_repartition_filleuls.png")

titre("Q5 – Répartition des parrains par tranche d'âge")

parrains_ids = {r["id_parrain"] for r in cypher("""
    MATCH (p:Client)-[:PARRAINE]->(:Client)
    WITH DISTINCT p
    RETURN p.id AS id_parrain
""")}

tranches = {}
for c in db.clients.find({"id": {"$in": list(parrains_ids)}},
                          {"_id": 0, "id": 1, "naissance": 1}):
    age = age_depuis_naissance(c.get("naissance"))
    t = tranche_age(age)
    tranches[t] = tranches.get(t, 0) + 1

ordre = ["18-27", "28-37", "38-47", "48-57", "58-67", "68+", "Inconnu"]
tranches_sorted = [(t, tranches.get(t, 0)) for t in ordre if t in tranches]
afficher(tranches_sorted, headers=["Tranche d'âge", "Nb parrains"])

labels5 = [t[0] for t in tranches_sorted]
vals5   = [t[1] for t in tranches_sorted]
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(labels5, vals5, color="#4C72B0")
ax.set_xlabel("Tranche d'âge")
ax.set_ylabel("Nombre de parrains")
ax.set_title("Parrains par tranche d'âge")
sauver_fig("q5_parrains_age.png")

titre("Q6 – Chaîne de parrainage la plus longue")

res_q6 = cypher("""
MATCH path = (a:Client)-[:PARRAINE*1..]->(b:Client)
WHERE NOT (b)-[:PARRAINE]->(:Client)
WITH path, length(path) AS longueur
ORDER BY longueur DESC
LIMIT 1
RETURN longueur,
       [n IN nodes(path) | n.prenom + ' ' + n.nom] AS chaine
""")
if res_q6:
    r = res_q6[0]
    print(f"Longueur de la chaîne : {r['longueur']}")
    print("Chaîne : " + " → ".join(r["chaine"]))
else:
    print("Aucune chaîne trouvée.")

titre("Q7 – Entreprise avec le plus d'employés clients fidélité")

pipeline_q7 = [
    {"$match": {"entreprise.siret": {"$exists": True, "$ne": None}}},
    {"$group": {
        "_id":  "$entreprise.siret",
        "nom":  {"$first": "$entreprise.nom"},
        "nb_employes": {"$sum": 1}
    }},
    {"$sort":  {"nb_employes": -1}},
    {"$limit": 10},
]
q7 = list(db.clients.aggregate(pipeline_q7))
afficher([(r["nom"], r["nb_employes"]) for r in q7],
         headers=["Entreprise", "Nb employés clients"])

titre("Q8 – Domaines d'activité avec le plus d'entreprises")

pipeline_q8 = [
    {"$group": {
        "_id":          "$domain_label",
        "nb_entreprises": {"$sum": 1}
    }},
    {"$sort":  {"nb_entreprises": -1}},
    {"$limit": 10},
]
q8 = list(db.entreprises.aggregate(pipeline_q8))
afficher([(r["_id"], r["nb_entreprises"]) for r in q8],
         headers=["Domaine d'activité", "Nb entreprises"])

titre("Q9 – Top 10 entreprises générant le plus de parrains")

parrains_ids_list = list(parrains_ids)

pipeline_q9 = [
    {"$match": {
        "id": {"$in": parrains_ids_list},
        "entreprise.siret": {"$exists": True, "$ne": None}
    }},
    {"$group": {
        "_id":         "$entreprise.siret",
        "nom":         {"$first": "$entreprise.nom"},
        "nb_parrains": {"$sum": 1}
    }},
    {"$sort":  {"nb_parrains": -1}},
    {"$limit": 10},
]
q9 = list(db.clients.aggregate(pipeline_q9))
afficher([(r["nom"], r["nb_parrains"]) for r in q9],
         headers=["Entreprise", "Nb parrains"])

noms9 = [r["nom"][:30] for r in q9]
vals9 = [r["nb_parrains"] for r in q9]
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(noms9[::-1], vals9[::-1], color="#55A868")
ax.set_xlabel("Nombre de parrains")
ax.set_title("Top 10 entreprises générant le plus de parrains")
sauver_fig("q9_entreprises_parrains.png")

titre("Q10 – Abonnés fidélité dans un rayon de 4 km par magasin")

res_q10 = cypher("""
MATCH (s:Shop)-[:SPONSOR]->(c:Client)
RETURN s.nom AS magasin, count(c) AS nb_abonnes
ORDER BY nb_abonnes DESC
""")
afficher([(r["magasin"], r["nb_abonnes"]) for r in res_q10],
         headers=["Magasin", "Nb abonnés (≤ 4 km)"])

driver.close()
mongo_client.close()
print("\n✓ Toutes les analyses parrainage terminées.")
print(f"  Graphiques exportés dans : {OUTPUT_DIR}")
