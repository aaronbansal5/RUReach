from google.cloud import firestore, storage
from dotenv import load_dotenv
import os 

load_dotenv()

class FirestoreClient:
    def __init__(self, firestore_collection : str):
        self.firestore_collection = firestore_collection

        self.project_id = os.getenv("FIREBASE_PROJECT_ID")
        self.creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.bucket_name = os.getenv("BUCKET_NAME", f"{self.project_id}.appspot.com")

        if not self.project_id:
            raise RuntimeError("FIREBASE_PROJECT_ID missing in .env")
        if not self.creds_path or not os.path.exists(self.creds_path):
            raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS path is missing or invalid")

        self.db = firestore.Client(project=self.project_id)
        self.gcs = storage.Client(project=self.project_id)
        self.bucket = self.gcs.bucket(self.bucket_name)

    def add_document(self, doc_id, doc):
        self.db.collection(self.firestore_collection).document(doc_id).set(doc)