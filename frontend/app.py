import os
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

# --- Google OAuth imports ---
from google_auth_oauthlib.flow import InstalledAppFlow

# -------------------- Config --------------------
load_dotenv()
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
GOOGLE_CLIENT_SECRETS_PATH = os.getenv("GOOGLE_CLIENT_SECRETS_PATH", "google_client_secret.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "email",
    "profile",
]

st.set_page_config(page_title="Rutgers Research Finder", layout="wide")
st.title("Rutgers Research Finder")
st.caption("Discover professors, compose outreach, and track progress — all in one place.")

tab1, tab2, tab3 = st.tabs(["🔎 Discover", "✉️ Outreach", "📊 Tracker"])

# -------------------- Backend helpers --------------------
def api_get_professors(q: str = "", limit: int = 50):
    try:
        r = requests.get(f"{API_BASE}/professors", params={"q": q, "limit": limit}, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        st.error(f"Failed to load professors: {e}")
        return []

def api_recommend(query: str, campus: str = "", top_k: int = 20):
    try:
        payload = {"query": query, "campus": campus or None, "top_k": top_k}
        r = requests.post(f"{API_BASE}/recommendations", json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        st.error(f"Failed to get recommendations: {e}")
        return []

def api_send_email(payload: dict):
    try:
        r = requests.post(f"{API_BASE}/send-email", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return {"error": str(e)}

# -------------------- Google Sign-In helpers --------------------
def do_google_login():
    """
    Desktop OAuth flow for local dev:
    - Opens browser to Google's consent screen
    - Receives callback on a local loopback port
    - Returns access_token AND refresh_token
    """
    if not os.path.exists(GOOGLE_CLIENT_SECRETS_PATH):
        st.error(
            f"Missing Google client secrets JSON at '{GOOGLE_CLIENT_SECRETS_PATH}'. "
            f"Place your downloaded OAuth client file there or set GOOGLE_CLIENT_SECRETS_PATH env."
        )
        return False

    flow = InstalledAppFlow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_PATH, scopes=SCOPES
    )
    creds = flow.run_local_server(
        port=0,
        access_type="offline",     # ensure refresh_token
        prompt="consent",          # force consent so refresh_token is issued
        authorization_prompt_message="",
        success_message="Login complete. You can close this tab and return to the app."
    )

    # Cache tokens in session
    st.session_state.google_creds = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
        "expiry": creds.expiry.isoformat() if getattr(creds, "expiry", None) else None,
        "id_token": getattr(creds, "id_token", None),
    }

    # Fetch basic profile (email, name) for UI
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=20,
        )
        if resp.ok:
            st.session_state.google_user = resp.json()  # {"email": "...", "name": "...", "picture": "..."}
    except Exception:
        pass

    return True

def require_google_login_ui():
    signed_in = ("google_creds" in st.session_state) and st.session_state.google_creds.get("token")
    if not signed_in:
        st.info("Sign in with Google to send emails via your account.")
        if st.button("Sign in with Google"):
            if do_google_login():
                st.experimental_rerun()
    return ("google_creds" in st.session_state) and st.session_state.google_creds.get("token")

def sign_out():
    for k in ("google_creds", "google_user"):
        if k in st.session_state:
            del st.session_state[k]
    st.success("Signed out.")
    st.experimental_rerun()

# -------------------- Session state --------------------
if "outreach_queue" not in st.session_state:
    st.session_state.outreach_queue = []  # store professor doc IDs

# -------------------- Discover tab --------------------
with tab1:
    st.subheader("Find Matching Professors")
    with st.form("discover_form"):
        query = st.text_input("Your research interest", value="machine learning for biology")
        top_k = st.slider("How many matches?", 5, 50, 20)
        submit = st.form_submit_button("Recommend Matches")

    if submit:
        results = api_recommend(query=query, top_k=top_k)
        if results:
            df = pd.DataFrame([{
                "id": r.get("id"),
                "name": r.get("name"),
                "institution": r.get("institution"),
                "topics": ", ".join(r.get("topics", [])[:6]),
                "score": round(r.get("score", 0.0), 3),
                "website": r.get("website")
            } for r in results])
            st.dataframe(df, use_container_width=True)
            add_ids = st.multiselect(
                "Select professors to add to Outreach queue (by id)",
                options=[r.get("id") for r in results],
            )
            if st.button("Add to Outreach queue"):
                for pid in add_ids:
                    if pid not in st.session_state.outreach_queue:
                        st.session_state.outreach_queue.append(pid)
                st.success(f"Added {len(add_ids)} to Outreach queue.")
        else:
            st.info("No results yet. Try a broader query.")

    st.divider()
    st.subheader("Browse (simple search)")
    q = st.text_input("Quick filter", value="")
    if st.button("Load Professors"):
        profs = api_get_professors(q=q, limit=100)
        if profs:
            df2 = pd.DataFrame([{
                "id": p.get("id"),
                "name": p.get("name"),
                "institution": p.get("institution"),
                "topics": ", ".join(p.get("topics", [])[:6]),
                "summary": (p.get("research_summary") or "")[:160] + ("..." if p.get("research_summary") and len(p.get("research_summary")) > 160 else ""),
                "website": p.get("website")
            } for p in profs])
            st.dataframe(df2, use_container_width=True)
        else:
            st.info("No professors found yet. Your teammate may still be ingesting data.")

# -------------------- Outreach tab --------------------
with tab2:
    st.subheader("Compose & Send Outreach")

    # Google login / user chip
    if require_google_login_ui():
        user_email = (st.session_state.get("google_user") or {}).get("email") or "Unknown"
        cols = st.columns([1, 1, 6])
        with cols[0]:
            st.success(f"Signed in: {user_email}")
        with cols[1]:
            if st.button("Sign out"):
                sign_out()
    else:
        st.stop()  # render only login prompt until signed in

    st.write("Queue:", st.session_state.outreach_queue or "Empty")

    with st.form("outreach_form"):
        recipients_csv = st.text_input(
            "Professor doc IDs (comma-separated)",
            value=",".join(st.session_state.outreach_queue)
        )
        subject = st.text_input("Subject", value="Prospective undergraduate researcher")
        body = st.text_area("Body (plain text)", height=220, value=(
            "Hello Professor LASTNAME,\n\n"
            "My name is YOUR_NAME, a YEAR studying MAJOR at Rutgers. "
            "I’m reaching out because your recent work on TOPIC aligns with my interests.\n\n"
            "I’ve attached my resume (and transcript). Would it be possible to set up a brief call?\n\n"
            "Best,\nYOUR_NAME\nYOUR_EMAIL"
        ))

        # (Optional) file uploads — next step is uploading to Firebase Storage and passing signed URLs
        colA, colB = st.columns(2)
        with colA:
            resume_file = st.file_uploader("Attach Resume (PDF)", type=["pdf"])
        with colB:
            transcript_file = st.file_uploader("Attach Transcript (PDF, optional)", type=["pdf"])

        # For logging: use email as a stand-in student id for now
        student_uid = st.text_input("Your student ID/UID (for logging)", value=user_email)

        submitted = st.form_submit_button("Send emails")

    if submitted:
        recipients = [{"professor_id": rid.strip()} for rid in recipients_csv.split(",") if rid.strip()]

        # Tokens from Google login
        gc = st.session_state.google_creds
        access_token = gc.get("token")
        refresh_token = gc.get("refresh_token")

        payload = {
            "recipients": recipients,
            "subject": subject,
            "body_markdown": body,
            "student_uid": student_uid,
            "access_token": access_token,
            "refresh_token": refresh_token,  # let backend refresh when needed
            "resume_url": None,              # TODO: upload to Firebase Storage and add signed URL
            "transcript_url": None
        }
        res = api_send_email(payload)
        st.success(res)

# -------------------- Tracker tab --------------------
with tab3:
    st.subheader("Sent & Replies")
    st.write("For MVP, we’ll read from a `contacts` Firestore collection in the backend later and expose `/contacts?uid=...`.")
    st.info("Ask your teammate to add a simple `/contacts` endpoint that returns sent logs filtered by `student_uid`.\n"
            "Then we’ll render them here as a table.")
