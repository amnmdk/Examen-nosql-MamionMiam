# Rapport de projet NoSQL — Mamion Miam

**Groupe 9 :** 3 IABD — ESGI
**Matière :** NoSQL


**Membres du groupe et répartition :**

| Étape | Livrable | Membre |
|---|---|---|
| 1 | Infrastructure (Docker, venv, GitHub) | Aimane |
| 2 | Chargement MongoDB (script `01`) | Jade |
| 3 | Analyse des ventes (script `02`) | Elodie |
| 4 | Chargement Neo4J (script `03`) | Aimane |
| 5 | Analyse du parrainage (script `04`) | Jade |
| 6 | Rapport final | Elodie |

---

## 1. Présentation du projet

La chaîne de magasins **Mamion Miam** (département 92, Hauts-de-Seine) est spécialisée dans les produits pour la cuisine et la maison. Le projet consiste à exploiter un extrait des données fournies par l'enseigne pour répondre à deux familles de questions :

- l'**analyse des ventes** (catégories, rayons, paniers, communes, genre) ;
- l'**analyse du parrainage fidélité** (réseau de parrains/filleuls, entreprises, magasins de proximité).

Pour respecter la nature de chaque problématique, deux bases NoSQL sont mobilisées :

- **MongoDB** comme base documentaire et **source unique de vérité** (les fichiers JSON ne servent qu'à la (ré)initialisation) ;
- **Neo4J** comme base graphe pour les analyses relationnelles (parrainage et proximité magasin–client).

---

## 2. Étape 1 — Infrastructure (Aimane)

### Stack technique

- **Docker Compose** : orchestre deux conteneurs (MongoDB + Neo4J) sur la machine locale.
- **Python 3.12** dans un `venv` (environnement virtuel).
- **GitHub privé** partagé avec le professeur `rcarlier`.
- **`.gitignore`** excluant `venv/`, `data/` (données brutes téléchargées), `__pycache__/`, etc.
- **`requirements.txt`** maintenu pour la reproductibilité.

### `docker-compose.yml`

```yaml
services:
  mongo:
    image: mongo:latest
    container_name: mamionmiam_mongo
    ports: ["27017:27017"]
    volumes: [mongo_data:/data/db]

  neo4j:
    image: neo4j:latest
    container_name: mamionmiam_neo4j
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    volumes: [neo4j_data:/data]
```

Deux **volumes nommés** persistent les données entre redémarrages. Les plugins **APOC** et **GDS** sont chargés au cas où des analyses de graphe avancées seraient nécessaires.

### `requirements.txt`

```
pymongo==4.10.1
neo4j==5.27.0
pandas==2.2.3
matplotlib==3.10.1
requests==2.32.3
tabulate==0.9.0
```

### Module `config.py`

Centralise les URI MongoDB / Neo4J et expose deux helpers `get_mongo_db()` et `get_neo4j_driver()` réutilisés par tous les scripts.

### Lancement de l'environnement

```bash
docker compose up -d
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Étape 2 — Chargement MongoDB (Jade)

### Script

```bash
python3 scripts/01_load_mongodb.py
```

Le script :

1. **télécharge** l'archive `mamionmiam.zip` (si absente) depuis `https://data.atontour.info/IABD/mamionmiam.zip` ;
2. **extrait** les 6 fichiers JSON dans `data/mamionmiam/` ;
3. **insère** chaque fichier dans une collection MongoDB dédiée (1 collection = 1 type de donnée, comme demandé dans le sujet) ;
4. **transforme** les coordonnées en GeoJSON `Point` pour les `clients`, `shops` et `entreprises` (champ `location`) ;
5. **crée les index** (géospatiaux et clés métier) pour accélérer les agrégations ultérieures.

### Transformation GeoJSON

Pour pouvoir, à terme, faire des requêtes géospatiales MongoDB (`$geoWithin`, `$near`), les coordonnées d'origine `{lat, lng}` sont reformatées :

```python
{"type": "Point", "coordinates": [lng, lat]}
```

> **Important** : MongoDB attend l'ordre **`[lng, lat]`** (et non `[lat, lng]`) dans le tableau `coordinates`.

### Index créés

| Collection | Index | Rôle |
|---|---|---|
| `clients` | `location` (2dsphere), `id` | Recherche géospatiale + jointure sur `id` |
| `shops` | `location` (2dsphere), `id` | Idem |
| `produits` | `SKU` | Jointure achats ↔ produits |
| `achats` | `acheteur`, `ticket` | Jointures clients + regroupements ticket |
| `parrainages` | `idParrain`, `idFilleul` | Parcours du graphe parrainage |
| `entreprises` | `siret` | Jointure clients ↔ entreprises |

### Résultats

| Collection | Nb documents |
|---|---:|
| `shops` | 4 |
| `clients` | 781 |
| `parrainages` | 546 |
| `entreprises` | 54 |
| `achats` | 1 422 |
| `produits` | 130 |

---

## 4. Étape 3 — Analyse des ventes (Elodie)

### Script

```bash
python3 scripts/02_analyse_ventes.py
```

**État de la base requis :** MongoDB chargé (étape 2). Aucune dépendance Neo4J.

Le script répond aux **10 questions de la partie ventes** via le **framework d'agrégation MongoDB** (`$group`, `$lookup`, `$unwind`…) et exporte **3 graphiques PNG** dans `outputs/`.

### Q1 — Top 10 catégories par nombre de produits

Pipeline `$group` sur `Categorie` + `$sort` desc + `$limit 10` sur la collection `produits`.

| Catégorie | Nb produits |
|---|---:|
| Verres / verrines jetables | 16 |
| Vaisselle jetable | 16 |
| Nappage | 10 |
| Couverts jetables | 9 |
| Verres | 8 |
| Plateaux et set de table | 8 |
| Accessoires de table | 7 |
| Bol et tasse | 6 |
| Ustensile pâtisserie | 6 |
| Lavage | 6 |

Graphique : `outputs/q1_top10_categories.png`

### Q2 — Top rayons par nombre de catégories distinctes

Astuce MongoDB : `$addToSet` pour dédupliquer les catégories par rayon, puis `$size` sur le tableau.

| Rayon | Nb catégories distinctes |
|---|---:|
| Arts de la table | 11 |
| Cuisine cuisson | 8 |
| Ménage | 6 |
| Puériculture | 1 |

### Q3 — Top rayons par nombre de produits

| Rayon | Nb produits |
|---|---:|
| Arts de la table | 86 |
| Cuisine cuisson | 24 |
| Ménage | 19 |
| Puériculture | 1 |

### Q4 — Paires de produits achetés ensemble

Pour chaque ticket, on construit l'ensemble des SKUs distincts puis toutes les **combinaisons de 2** via `itertools.combinations`. Un `Counter` agrège les fréquences. Les SKU sont remappés vers les libellés via la collection `produits`.

Top paire la plus fréquente : `Lot de 6 Gobelets en Papier "1 An de Plus" 25cl Blanc + Range couverts vert` — **4 tickets**. Les paires suivantes apparaissent 3 fois.

### Q5 — Top catégories par nombre de lignes de vente

Pipeline : `$unwind: "$detail"` (1 ligne par article du ticket) → `$lookup` vers `produits` sur `SKU` → `$group` par `Categorie` → `$sum: 1`.

| Catégorie | Nb lignes |
|---|---:|
| Vaisselle jetable | 344 |
| Verres / verrines jetables | 334 |
| Nappage | 197 |
| Couverts jetables | 175 |
| Accessoires de table | 159 |

### Q6 — Top catégories par quantité vendue

Même pipeline que Q5 mais `$sum: "$detail.qte"` au lieu de `$sum: 1`.

| Catégorie | Quantité vendue |
|---|---:|
| Vaisselle jetable | 633 |
| Verres / verrines jetables | 621 |
| Nappage | 362 |
| Couverts jetables | 329 |
| Accessoires de table | 286 |

### Q7 — Achats et dépense par genre

`$lookup` `achats.acheteur` ↔ `clients.id` puis `$group` par `client.genre`.

| Genre | Nb achats | Dépense totale (€) |
|---|---:|---:|
| F | 992 | 15 846,30 |
| H | 430 | 6 642,29 |

> Les femmes représentent **70 % des achats** et **70,5 % du chiffre d'affaires**. Graphique : `outputs/q7_depense_par_genre.png`.

### Q8 — Genre × rayon

Triple `$lookup` (achats → produits → clients) puis `$group` sur `{genre, rayon}`.

| Genre | Rayon | Nb lignes | Dépense (€) |
|---|---|---:|---:|
| F | Arts de la table | 1 266 | 10 217,30 |
| H | Arts de la table | 523 | 4 252,06 |
| F | Cuisine cuisson | 350 | 3 132,40 |
| F | Ménage | 253 | 2 395,47 |
| H | Ménage | 134 | 1 172,98 |
| H | Cuisine cuisson | 137 | 1 163,70 |
| F | Puériculture | 11 | 101,15 |
| H | Puériculture | 4 | 53,55 |

### Q9 — Achats et dépense par commune

Top 3 communes : **Meudon** (1 206,09 €), **Villeneuve-la-Garenne** (1 009,66 €), **Nanterre** (902,25 €). Graphique : `outputs/q9_top10_communes.png`.

### Q10 — Dépense par commune × genre

Trié par dépense décroissante : les premières lignes sont **toutes des couples F/commune**, ce qui confirme la tendance observée en Q7. Le couple le plus élevé reste `Meudon / F` (963,25 €).

### Synthèse ventes

- **Arts de la table** est le rayon dominant (86 produits, 11 catégories).
- Les produits **jetables** dominent en volume (vaisselle, verres, couverts).
- Les **femmes** réalisent **2,3× plus d'achats** et dépensent **2,4× plus** que les hommes.
- **Meudon** et **Villeneuve-la-Garenne** sont les meilleures communes en chiffre d'affaires.

---

## 5. Étape 4 — Chargement Neo4J (Aimane)

### Script

```bash
python3 scripts/03_graphe.py
```

**État de la base requis :** MongoDB chargé. Le script **vide** Neo4J avant de le réalimenter (`MATCH (n) DETACH DELETE n`), comme prévu par le sujet.

### Modèle de graphe

```
(:Client)-[:PARRAINE]->(:Client)
(:Client)-[:WORKS_AT]->(:Entreprise)
(:Entreprise)-[:IN_DOMAIN]->(:DomainActivite)
(:Shop)-[:SPONSOR {dist_km}]->(:Client)
```

### Étapes du chargement

1. **Clients** (781 nœuds) — propriétés `id`, `nom`, `prenom`, `genre`, `naissance`, `commune`, `lat`, `lng`. Index `client_id` créé.
2. **Domaines d'activité** (12 nœuds) — extraits des entreprises via `domain_code` / `domain_label`.
3. **Entreprises** (54 nœuds) — clé `siret`, créées avec leur relation `IN_DOMAIN` vers le domaine correspondant.
4. **WORKS_AT** (467 relations) — pour chaque client ayant un `entreprise.siret`, on crée la relation `Client→Entreprise`.
5. **PARRAINE** (546 relations) — depuis la collection `parrainages` (clé : `idParrain`, `idFilleul`, propriété `date`).
6. **Shops** (4 nœuds) — magasins avec leurs coordonnées.
7. **SPONSOR** (681 relations) — pour chaque couple (shop, client), la **distance haversine** est calculée en Python ; si elle est ≤ 4 km, une relation `(:Shop)-[:SPONSOR {dist_km}]->(:Client)` est créée.

### Pourquoi calculer la distance en Python plutôt qu'en Cypher ?

- Le calcul **haversine** se fait sur quelques milliers de paires (4 × 781 = 3 124 distances), ce qui est très rapide en Python.
- Cela évite de dépendre du module `point()` de Neo4J et de gérer un système de coordonnées dans Cypher.
- Toutes les distances sont stockées dans la propriété `dist_km` de la relation, ce qui rend les requêtes ultérieures triviales.

### Insertion par batchs

Toutes les insertions utilisent le pattern `UNWIND $items AS x` avec un `BATCH_SIZE = 500` pour minimiser les allers-retours réseau.

---

## 6. Étape 5 — Analyse du parrainage (Jade)

### Script

```bash
python3 scripts/04_analyse_parrainage.py
```

**État des bases requis :** MongoDB **et** Neo4J chargés (étapes 2 et 4).

Le script **mixe Cypher et MongoDB** :
- Cypher pour les questions liées au **graphe** (Q1, Q2, Q3, Q4, Q6, Q10) ;
- MongoDB pour les questions sur les **entreprises et domaines** (Q7, Q8, Q9) ;
- les deux pour Q5 (Cypher → ids des parrains, puis MongoDB pour les dates de naissance).

### Q1 — Personne ayant le plus parrainé

Cypher : `MATCH (p)-[:PARRAINE]->(f) WITH p, count(f) ORDER BY ... LIMIT 1`.

> **Marthe Roux** — 5 filleuls (Patrick Sanchez, Élodie Vincent, Christine Thibault, Brigitte Le Roux, Corinne Aubry).

### Q2 — H/F parrains et filleuls

| | F | H |
|---|---:|---:|
| Parrains | 277 | 107 |
| Filleuls | 376 | 170 |

### Q3 / Q4 — Répartitions H/F (camemberts)

- Parrains : 72,1 % F / 27,9 % H — `outputs/q3_repartition_parrains.png`
- Filleuls : 68,9 % F / 31,1 % H — `outputs/q4_repartition_filleuls.png`

### Q5 — Tranches d'âge des parrains

| Tranche | Nb parrains |
|---|---:|
| 18-27 | 67 |
| 28-37 | 68 |
| 38-47 | **82** |
| 48-57 | 67 |
| 58-67 | 79 |
| 68+ | 21 |

Graphique : `outputs/q5_parrains_age.png`.

### Q6 — Chaîne de parrainage la plus longue

Cypher avec **chemin variable** `[:PARRAINE*1..]` filtré sur les filleuls qui n'ont eux-mêmes aucun filleul (pour s'arrêter à la fin de la chaîne).

> **Longueur 13** : Sébastien Da Costa → Alix Humbert → Hélène Guillon → Bernadette Legros → Simone Wagner → Sébastien Da Costa → Michel Dos Santos → Alexandrie Boyer → Mathilde Gros → Raymond Rivière → Henriette Legrand → Capucine Lemonnier → Philippe Leroy → Françoise Delmas

### Q7 — Entreprise avec le plus d'employés clients fidélité

| Entreprise | Nb employés |
|---|---:|
| SIDEXIA | 35 |
| C L V | 34 |
| COULEURS VOCALES | 33 |
| ARCADE NETTOYAGE | 31 |
| FONDATION PERCE NEIGE | 30 |

### Q8 — Domaines d'activité concentrant le plus d'entreprises

Top : **Commerce, Vente et Grande distribution** (12), Santé (9), Construction/BTP (8).

### Q9 — Top entreprises générant le plus de parrains

| Entreprise | Nb parrains |
|---|---:|
| INTERMARCHE | 18 |
| SINA DECORE | 15 |
| LES PAPILLONS BLANCS DE LA COLLINE | 15 |
| AFA CONTROLE | 15 |
| COULEURS VOCALES | 15 |

Graphique : `outputs/q9_entreprises_parrains.png`.

### Q10 — Abonnés fidélité dans un rayon de 4 km par magasin

| Magasin | Nb abonnés (≤ 4 km) |
|---|---:|
| Mamion Miam (La Garenne-Colombes) | 225 |
| Mamion Miam, Bagneux | 194 |
| Mamion Miam, Chaville | 152 |
| Mamion Miam, Rueil | 110 |

### Synthèse parrainage

- Réseau **majoritairement féminin** (72 % de parrains F, 69 % de filleuls F).
- Réseau **dense** : la plus longue chaîne fait **13 liens** (présence d'un cycle, Sébastien Da Costa apparaît deux fois).
- Le parrainage est **stimulé par certaines entreprises** : INTERMARCHE en tête (18 parrains).
- Le magasin de **La Garenne-Colombes** est le mieux situé : 225 abonnés à moins de 4 km.

---

## 7. Récapitulatif des graphiques exportés

### Script 02 — Ventes (3 graphiques)
- `outputs/q1_top10_categories.png`
- `outputs/q7_depense_par_genre.png`
- `outputs/q9_top10_communes.png`

### Script 04 — Parrainage (4 graphiques)
- `outputs/q3_repartition_parrains.png`
- `outputs/q4_repartition_filleuls.png`
- `outputs/q5_parrains_age.png`
- `outputs/q9_entreprises_parrains.png`

> Le sujet impose **au moins 3 graphiques par partie** : ✅ pour les ventes (3), ✅ pour le parrainage (4).

> Remarque : la numérotation Q1…Q10 redémarre dans chaque script ; il existe donc un Q9 ventes (`q9_top10_communes.png`) **et** un Q9 parrainage (`q9_entreprises_parrains.png`).

---

## 8. Structure du projet livré

```
Examen-nosql-MamionMiam/
├── docker-compose.yml         # Aimane (étape 1)
├── requirements.txt           # Aimane (étape 1)
├── config.py                  # config commune Mongo/Neo4J
├── .gitignore
├── scripts/
│   ├── 01_load_mongodb.py     # Jade (étape 2)
│   ├── 02_analyse_ventes.py   # Elodie (étape 3)
│   ├── 03_graphe.py           # Aimane (étape 4)
│   └── 04_analyse_parrainage.py  # Jade (étape 5)
├── data/                      # ignoré par git (téléchargé à l'exécution)
└── outputs/                   # 7 PNG générés par les scripts
```

---

## 9. Reproductibilité — comment relancer le projet

```bash
# 1. Lancer Mongo + Neo4J
docker compose up -d

# 2. Environnement Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Pipeline complet
python3 scripts/01_load_mongodb.py        # MongoDB
python3 scripts/02_analyse_ventes.py      # Analyses ventes + 3 PNG
python3 scripts/03_graphe.py              # Neo4J
python3 scripts/04_analyse_parrainage.py  # Analyses parrainage + 4 PNG
```

Chaque script est **idempotent** : il vide / réinsère sa partie de données, on peut donc le relancer autant de fois que nécessaire.

---

## 10. Conclusion

Le pipeline complet a été exécuté avec succès et répond aux **20 questions** du sujet (10 ventes + 10 parrainage), avec **7 graphiques** exportés (3 ventes + 4 parrainage), **2 bases NoSQL** complémentaires (MongoDB documentaire + Neo4J graphe), et un environnement **entièrement reproductible** (Docker + venv + `requirements.txt`).

**Tendances retenues :**
- **Ventes** : `Arts de la table` domine, les produits jetables tirent les volumes, et le chiffre d'affaires est très majoritairement porté par la clientèle féminine (≈ 70 %).
- **Parrainage** : un réseau dense, très féminin, stimulé par certaines grandes entreprises locales, avec une chaîne de parrainage atteignant 13 liens.
- **Magasins** : le point de vente de La Garenne-Colombes a la zone de chalandise la plus dense (225 abonnés à moins de 4 km).


