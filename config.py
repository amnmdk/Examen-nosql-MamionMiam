from pymongo import MongoClient
from neo4j import GraphDatabase

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB  = "mamionmiam"

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "password"


def get_mongo_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB]


def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
