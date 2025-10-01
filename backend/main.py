import os
from datetime import timedelta
from dotenv import load_dotenv

from fastapi import FastAPI
from google.cloud import firestore, storage

# --- Load environment ---
load_dotenv()
PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
BUCKET_NAME = os.getenv("BUCKET_NAME", f"{PROJECT_ID}.appspot.com")

if not PROJECT_ID:
    raise RuntimeError("FIREBASE_PROJECT_ID missing in .env")
if not CREDS_PATH or not os.path.exists(CREDS_PATH):
    raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS path is missing or invalid")

# --- Init Firebase Admin clients ---
db = firestore.Client(project=PROJECT_ID)
gcs = storage.Client(project=PROJECT_ID)
bucket = gcs.bucket(BUCKET_NAME)

app = FastAPI(title="RUReach Backend Smoke Test")

@app.get("/health")
def health():
    return {"ok": True, "project": PROJECT_ID, "bucket": BUCKET_NAME}

@app.get("/ping-firestore")
def ping_firestore():
    """
    Writes a tiny demo doc to Firestore and reads it back.
    Collection: professors / Document: demo
    """
    ref = db.collection("professors").document("demo")
    ref.set({"name": "Demo Professor", "topics": ["setup", "test"], "institution": "Rutgers"}, merge=True)
    doc = ref.get().to_dict()
    return {"ok": True, "doc": doc}

