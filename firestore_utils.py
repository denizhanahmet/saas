from firebase_config import db

def get_collection(collection_name):
    return db.collection(collection_name)

def add_document(collection_name, data, doc_id=None):
    col = get_collection(collection_name)
    if doc_id:
        col.document(doc_id).set(data)
    else:
        col.add(data)

def get_document(collection_name, doc_id):
    return get_collection(collection_name).document(doc_id).get().to_dict()

def update_document(collection_name, doc_id, data):
    get_collection(collection_name).document(doc_id).update(data)

def delete_document(collection_name, doc_id):
    get_collection(collection_name).document(doc_id).delete()

def query_collection(collection_name, field, value):
    return [doc.to_dict() for doc in get_collection(collection_name).where(field, '==', value).stream()]
