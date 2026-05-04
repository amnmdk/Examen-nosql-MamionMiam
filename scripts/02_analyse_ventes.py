# analyse ventes mamion miam

import os
import sys
from collections import Counter
from itertools import combinations

import matplotlib.pyplot as plt
from tabulate import tabulate

# sys.path : sinon import config marche pas si lancé depuis scripts/
RACINE_PROJET = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RACINE_PROJET not in sys.path:
    sys.path.insert(0, RACINE_PROJET)

from config import get_mongo_db


DOSSIER_SORTIE = os.path.join(RACINE_PROJET, "outputs")


def question_1(db):
    """q1 top10 cat par nb produits"""
    print("Q1 — Top 10 catégories par nombre de produits")

    pipeline = [
        # $group categorie + count
        {"$group": {"_id": "$Categorie", "nb_produits": {"$sum": 1}}},
        {"$sort": {"nb_produits": -1}},  # -1 = desc
        {"$limit": 10},
    ]

    liste_docs = list(db.produits.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        categorie = doc["_id"]
        nb_produits = doc["nb_produits"]
        lignes.append((categorie, nb_produits))

    print(tabulate(lignes, headers=["Catégorie", "Nb produits"], tablefmt="grid"))

    # barh
    noms_categories = []
    valeurs = []
    for doc in liste_docs:
        noms_categories.append(str(doc["_id"]))
        valeurs.append(doc["nb_produits"])

    # reverse sinon n1 en BAS (matplotlib)
    noms_categories.reverse()
    valeurs.reverse()

    plt.figure(figsize=(10, 6))
    plt.barh(noms_categories, valeurs, color="steelblue")
    plt.xlabel("Nombre de produits")
    plt.ylabel("Catégorie")
    plt.title("Q1 — Top 10 des catégories par nombre de produits")
    plt.tight_layout()
    chemin = os.path.join(DOSSIER_SORTIE, "q1_top10_categories.png")
    plt.savefig(chemin, dpi=120)
    plt.close()
    print(f"[OK] Graphique enregistré : {chemin}")


def question_2(db):
    """q2 rayon -> nb cat distinctes top10"""
    print("Q2 — Top 10 rayons par nombre de catégories distinctes")

    pipeline = [
        # addToSet = pas de doublons cat
        {"$group": {"_id": "$Rayon", "categories": {"$addToSet": "$Categorie"}}},
        # $size du tab = nb cat
        {
            "$project": {
                "_id": 0,
                "rayon": "$_id",
                "nb_categories": {"$size": "$categories"},
            }
        },
        {"$sort": {"nb_categories": -1}},
        {"$limit": 10},
    ]

    liste_docs = list(db.produits.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        lignes.append((doc["rayon"], doc["nb_categories"]))

    print(tabulate(lignes, headers=["Rayon", "Nb catégories distinctes"], tablefmt="grid"))


def question_3(db):
    """q3 top10 rayon nb produits"""
    print("Q3 — Top 10 rayons par nombre de produits")

    pipeline = [
        # group par rayon sum 1
        {"$group": {"_id": "$Rayon", "nb_produits": {"$sum": 1}}},
        {"$sort": {"nb_produits": -1}},
        {"$limit": 10},
    ]

    liste_docs = list(db.produits.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        lignes.append((doc["_id"], doc["nb_produits"]))

    print(tabulate(lignes, headers=["Rayon", "Nb produits"], tablefmt="grid"))


def question_4(db):
    """q4 paires produits meme ticket top10"""
    print("Q4 — Top 10 paires de produits achetés ensemble (même ticket)")

    compteur_paires = Counter()

    # python pas aggregate : combinations sur SKUs uniques du ticket
    curseur_achats = db.achats.find({}, {"detail.SKU": 1})
    for achat in curseur_achats:
        detail = achat.get("detail")
        if detail is None:
            continue

        skus = set()
        for ligne in detail:
            if "SKU" in ligne:
                skus.add(ligne["SKU"])

        skus_tries = sorted(skus)
        for paire in combinations(skus_tries, 2):
            compteur_paires[paire] += 1

    dix_paires_plus_frequentes = compteur_paires.most_common(10)

    tous_skus = set()
    for (sku_a, sku_b), _nb in dix_paires_plus_frequentes:
        tous_skus.add(sku_a)
        tous_skus.add(sku_b)

    libelles_par_sku = {}
    if len(tous_skus) > 0:
        liste_sku = list(tous_skus)
        curseur_produits = db.produits.find({"SKU": {"$in": liste_sku}}, {"SKU": 1, "Label": 1})
        for produit in curseur_produits:
            libelles_par_sku[produit["SKU"]] = produit.get("Label", "")

    lignes = []
    for (sku_a, sku_b), nb_fois in dix_paires_plus_frequentes:
        label_a = libelles_par_sku.get(sku_a, str(sku_a))
        label_b = libelles_par_sku.get(sku_b, str(sku_b))
        texte_paire = f"{label_a}  +  {label_b}"
        lignes.append((texte_paire, nb_fois))

    print(tabulate(lignes, headers=["Paire de produits", "Nb tickets"], tablefmt="grid"))


def question_5(db):
    """q5 top10 cat par nb lignes vente"""
    print("Q5 — Top 10 catégories par nombre de lignes de vente")

    pipeline = [
        {"$unwind": "$detail"},  # 1 ligne par article
        # lookup achats -> produits
        {
            "$lookup": {
                "from": "produits",
                "localField": "detail.SKU",
                "foreignField": "SKU",
                "as": "produit",
            }
        },
        {"$unwind": "$produit"},
        {"$group": {"_id": "$produit.Categorie", "nb_lignes": {"$sum": 1}}},
        {"$sort": {"nb_lignes": -1}},
        {"$limit": 10},
    ]

    liste_docs = list(db.achats.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        lignes.append((doc["_id"], doc["nb_lignes"]))

    print(tabulate(lignes, headers=["Catégorie", "Nb lignes de vente"], tablefmt="grid"))


def question_6(db):
    """q6 meme truc que q5 mais sum(qte)"""
    print("Q6 — Top 10 catégories par quantité vendue")

    pipeline = [
        {"$unwind": "$detail"},
        {
            "$lookup": {
                "from": "produits",
                "localField": "detail.SKU",
                "foreignField": "SKU",
                "as": "produit",
            }
        },
        {"$unwind": "$produit"},
        {"$group": {"_id": "$produit.Categorie", "quantite_totale": {"$sum": "$detail.qte"}}},  # sum qte
        {"$sort": {"quantite_totale": -1}},
        {"$limit": 10},
    ]

    liste_docs = list(db.achats.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        lignes.append((doc["_id"], doc["quantite_totale"]))

    print(tabulate(lignes, headers=["Catégorie", "Quantité vendue"], tablefmt="grid"))


def question_7(db):
    """q7 par genre : nb achats + depense"""
    print("Q7 — Achats et dépense totale par genre")

    pipeline = [
        # lookup acheteur -> clients.id (champ id pas _id!!)
        {
            "$lookup": {
                "from": "clients",
                "localField": "acheteur",
                "foreignField": "id",
                "as": "client",
            }
        },
        {"$unwind": "$client"},
        {
            "$group": {
                "_id": "$client.genre",
                "nb_achats": {"$sum": 1},
                "depense": {"$sum": "$total"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    liste_docs = list(db.achats.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        lignes.append((doc["_id"], doc["nb_achats"], round(doc["depense"], 2)))

    print(tabulate(lignes, headers=["Genre", "Nb achats", "Dépense totale"], tablefmt="grid"))

    # bar + couleurs H/F
    genres = []
    depenses = []
    couleurs = []
    for doc in liste_docs:
        g = doc["_id"]
        genres.append(str(g))
        depenses.append(doc["depense"])
        if g == "H":
            couleurs.append("#4C72B0")
        elif g == "F":
            couleurs.append("#C44E52")
        else:
            couleurs.append("#888888")

    plt.figure(figsize=(8, 6))
    plt.bar(genres, depenses, color=couleurs)
    plt.xlabel("Genre")
    plt.ylabel("Dépense totale (€)")
    plt.title("Q7 — Dépense totale par genre")
    plt.tight_layout()
    chemin = os.path.join(DOSSIER_SORTIE, "q7_depense_par_genre.png")
    plt.savefig(chemin, dpi=120)
    plt.close()
    print(f"[OK] Graphique enregistré : {chemin}")


def question_8(db):
    """q8 genre+rayon : nb lignes + depense (detail.total)"""
    print("Q8 — Lignes de vente et dépense par genre et par rayon")

    pipeline = [
        {"$unwind": "$detail"},
        {
            "$lookup": {
                "from": "produits",
                "localField": "detail.SKU",
                "foreignField": "SKU",
                "as": "produit",
            }
        },
        {"$unwind": "$produit"},
        {
            "$lookup": {
                "from": "clients",
                "localField": "acheteur",
                "foreignField": "id",
                "as": "client",
            }
        },
        {"$unwind": "$client"},
        # _id objet {genre, rayon}
        {
            "$group": {
                "_id": {"genre": "$client.genre", "rayon": "$produit.Rayon"},
                "nb_lignes": {"$sum": 1},
                "depense": {"$sum": "$detail.total"},
            }
        },
        {"$sort": {"depense": -1}},
    ]

    liste_docs = list(db.achats.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        cle = doc["_id"]
        genre = cle["genre"]
        rayon = cle["rayon"]
        lignes.append((genre, rayon, doc["nb_lignes"], round(doc["depense"], 2)))

    print(
        tabulate(
            lignes,
            headers=["Genre", "Rayon", "Nb lignes", "Dépense"],
            tablefmt="grid",
        )
    )


def question_9(db):
    """q9 par commune tri depense desc"""
    print("Q9 — Achats et dépense par commune (tri par dépense)")

    pipeline = [
        {
            "$lookup": {
                "from": "clients",
                "localField": "acheteur",
                "foreignField": "id",
                "as": "client",
            }
        },
        {"$unwind": "$client"},
        {
            "$group": {
                "_id": "$client.commune",
                "nb_achats": {"$sum": 1},
                "depense": {"$sum": "$total"},
            }
        },
        {"$sort": {"depense": -1}},
    ]

    liste_docs = list(db.achats.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        lignes.append((doc["_id"], doc["nb_achats"], round(doc["depense"], 2)))

    print(tabulate(lignes, headers=["Commune", "Nb achats", "Dépense totale"], tablefmt="grid"))

    # graph top10 communes
    dix_premiers = liste_docs[:10]
    noms_communes = []
    montants = []
    for doc in dix_premiers:
        noms_communes.append(str(doc["_id"]))
        montants.append(doc["depense"])

    noms_communes.reverse()  # idem q1 barh
    montants.reverse()

    plt.figure(figsize=(10, 6))
    plt.barh(noms_communes, montants, color="seagreen")
    plt.xlabel("Dépense totale (€)")
    plt.ylabel("Commune")
    plt.title("Q9 — Top 10 des communes par dépense totale")
    plt.tight_layout()
    chemin = os.path.join(DOSSIER_SORTIE, "q9_top10_communes.png")
    plt.savefig(chemin, dpi=120)
    plt.close()
    print(f"[OK] Graphique enregistré : {chemin}")


def question_10(db):
    """q10 commune x genre depense"""
    print("Q10 — Dépense par commune et par genre")

    pipeline = [
        {
            "$lookup": {
                "from": "clients",
                "localField": "acheteur",
                "foreignField": "id",
                "as": "client",
            }
        },
        {"$unwind": "$client"},
        {
            "$group": {
                "_id": {"commune": "$client.commune", "genre": "$client.genre"},
                "depense": {"$sum": "$total"},
            }
        },
        {"$sort": {"depense": -1}},
    ]

    liste_docs = list(db.achats.aggregate(pipeline))

    lignes = []
    for doc in liste_docs:
        cle = doc["_id"]
        commune = cle["commune"]
        genre = cle["genre"]
        lignes.append((commune, genre, round(doc["depense"], 2)))

    print(tabulate(lignes, headers=["Commune", "Genre", "Dépense totale"], tablefmt="grid"))


def main():
    db = get_mongo_db()
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)

    print("=" * 60)
    print("ANALYSE DES VENTES — MAMION MIAM")
    print("=" * 60)

    question_1(db)
    print("=" * 60)
    question_2(db)
    print("=" * 60)
    question_3(db)
    print("=" * 60)
    question_4(db)
    print("=" * 60)
    question_5(db)
    print("=" * 60)
    question_6(db)
    print("=" * 60)
    question_7(db)
    print("=" * 60)
    question_8(db)
    print("=" * 60)
    question_9(db)
    print("=" * 60)
    question_10(db)

    print("\n[OK] Toutes les analyses ont été exécutées.")
    print(f"[OK] Graphiques sauvegardés dans : {DOSSIER_SORTIE}")


if __name__ == "__main__":
    main()
