# save as openalex_professor_firestore.py
import requests
import difflib
import time
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# --- CONFIG ---
INPUT_CSV = "professors.csv"       # one column with names
SERVICE_ACCOUNT = "serviceAccountKey.json"  # your Firebase service account key
FIRESTORE_COLLECTION = "professors_openalex"
OPENALEX_BASE = "https://api.openalex.org"
SLEEP = 0.5

# --- FIREBASE SETUP ---
cred = credentials.Certificate(SERVICE_ACCOUNT)
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- HELPERS ---
def read_names(path):
    df = pd.read_csv(path, dtype=str).fillna("")
    return [n.strip() for n in df[df.columns[0]].tolist() if n.strip()]

def search_author(name):
    r = requests.get(
        f"{OPENALEX_BASE}/authors",
        params={"search": name, "per_page": 5},
        timeout=20
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None
    # pick the best match by fuzzy string similarity
    return max(results, key=lambda a: difflib.SequenceMatcher(None, name.lower(), a["display_name"].lower()).ratio())

def get_author_topics(author):
    return [t["display_name"] for t in (author.get("topics") or [])]

def get_top_work(author_id):
    r = requests.get(
        f"{OPENALEX_BASE}/works",
        params={"filter": f"author.id:{author_id}", "sort": "cited_by_count:desc", "per_page": 1},
        timeout=20
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None

def reconstruct_abstract(inv_index):
    if not inv_index:
        return None
    positions = []
    for word, pos in inv_index.items():
        positions.extend((p, word) for p in pos)
    positions.sort()
    return " ".join(w for _, w in positions)

def get_work_info(work):
    return {
        "title": work.get("display_name"),
        "topics": [t["display_name"] for t in (work.get("topics") or [])],
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
    }

# --- MAIN ---
def main():
    names = read_names(INPUT_CSV)
    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}] {name}")
        try:
            author = search_author(name)
            if not author:
                doc = {"professor": name, "error": "no author match"}
            else:
                topics = get_author_topics(author)
                time.sleep(SLEEP)
                work = get_top_work(author["id"])
                work_info = get_work_info(work) if work else {}
                doc = {
                    "professor": name,
                    "author_id": author.get("id"),
                    "author_name": author.get("display_name"),
                    "author_topics": topics,
                    "paper": work_info
                }
            # save to Firestore (document id = underscored professor name)
            db.collection(FIRESTORE_COLLECTION).document(name.replace(" ", "_")).set(doc)
        except Exception as e:
            db.collection(FIRESTORE_COLLECTION).document(name.replace(" ", "_")).set({
                "professor": name,
                "error": str(e)
            })
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()
