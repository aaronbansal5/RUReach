import requests
import difflib
import time
from FirestoreClient import FirestoreClient

def reconstruct_abstract(inv_index):
    if not inv_index:
        return None
    positions = []
    for word, pos in inv_index.items():
        positions.extend((p, word) for p in pos)
    positions.sort()
    return " ".join(w for _, w in positions)

def build_professor_doc(name: str):

    OPENALEX_BASE = "https://api.openalex.org"

    try:
        r = requests.get(f"{OPENALEX_BASE}/authors", params={"search": name, "per_page": 5}, timeout=20)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return {"professor": name, "error": "no author match"}

        author = max(results, key=lambda a: difflib.SequenceMatcher(None, name.lower(), a["display_name"].lower()).ratio())
        author_topics = [t["display_name"] for t in (author.get("topics") or [])]

        r = requests.get(f"{OPENALEX_BASE}/works", params={"filter": f"author.id:{author['id']}", "sort": "cited_by_count:desc", "per_page": 1}, timeout=20)
        r.raise_for_status()
        works = r.json().get("results", [])
        work = works[0] if works else None

        print("Found author:", author["display_name"])

        work_info = {}
        if work:
            work_info = {
                "title": work.get("display_name"),
                "topics": [t["display_name"] for t in (work.get("topics") or [])],
                "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
            }

        return {
            "professor": name,
            "author_id": author.get("id"),
            "author_name": author.get("display_name"),
            "author_topics": author_topics,
            "paper": work_info
        }

    except Exception as e:
        return {"professor": name, "error": str(e)}

def seed_database(input_txt_path : str, firestore_collection : str, sleep_time : float = 1.0):
    with open(input_txt_path, "r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]

    firestore_client = FirestoreClient(firestore_collection)
   
    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}] {name}")
        doc = build_professor_doc(name)
        doc_id = name.replace(" ", "_")
        firestore_client.add_document(doc_id, doc)
        time.sleep(sleep_time)

def main():
    input_csv = "professor_names.txt"
    firestore_collection = "professors"
    seed_database(input_csv, firestore_collection)

if __name__ == "__main__":
    main()
