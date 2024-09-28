from pymongo import MongoClient

def db_connect():
    client = MongoClient('mongodb://localhost:27017/')
    db = client.githubEvents
    events_collection = db.events
    return events_collection