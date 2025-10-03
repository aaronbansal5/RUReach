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
GOOGLE_CLIENT_SECRETS_PATH = os.getenv("GOOGLE_CLIENT_SECRETS_PATH", "creds/google_client_secret.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

st.set_page_config(page_title="Rutgers Research Finder", layout="wide")

# -------------------- Helpers --------------------
def safe_rerun():
    # Works on both new and older Streamlit versions
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

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
    Desktop OAuth flow for local dev with safer settings:
    - fixed localhost port (8765)
    - trailing slash on redirect
    - console fallback if the local server callback fails
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

    try:
        creds = flow.run_local_server(
            host="localhost",
            port=8765,                        # fixed port helps with firewall
            access_type="offline",            # get refresh_token
            prompt="consent",                 # force consent, ensures refresh_token
            authorization_prompt_message="",
            success_message="Login complete. You can close this tab and return to the app.",
            open_browser=True,
            redirect_uri_trailing_slash=True,
        )
    except Exception as e:
        st.warning(f"Local callback failed ({e}). Falling back to console login in your terminal window.")
        try:
            creds = flow.run_console(authorization_prompt_message="")
        except Exception as e2:
            st.error(f"Google sign-in failed: {e2}")
            return False

    # Cache tokens in session (used later to send emails)
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

    # Fetch user profile via OIDC userinfo
    try:
        resp = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=20,
        )
        if resp.ok:
            st.session_state.google_user = resp.json()  # {"sub","email","name","picture",...}
            # Stable account id (sub) is a good UID; fallback to email if missing
            st.session_state.user_uid = st.session_state.google_user.get("sub") or st.session_state.google_user.get("email")
    except Exception:
        pass

    return True

def require_google_login_ui():
    signed_in = ("google_creds" in st.session_state) and bool(st.session_state.google_creds.get("token"))
    if not signed_in:
        st.header("Sign in with Google")
        st.write("Please sign in to continue. We use your Google account to send outreach emails via Gmail on your behalf.")
        if st.button("Sign in with Google"):
            if do_google_login():
                # Rerun so the page rebuilds with the signed-in state
                safe_rerun()
    return ("google_creds" in st.session_state) and bool(st.session_state.google_creds.get("token"))

def sign_out():
    for k in ("google_creds", "google_user", "user_uid"):
        if k in st.session_state:
            del st.session_state[k]
    st.success("Signed out.")
    safe_rerun()

# -------------------- Session state --------------------
if "outreach_queue" not in st.session_state:
    st.session_state.outreach_queue = []  # store professor doc IDs

# -------------------- Global login gate (FIRST) --------------------
if not require_google_login_ui():
    st.stop()

# If we get here, user is signed in
user_email = (st.session_state.get("google_user") or {}).get("email") or "Unknown"
user_uid = st.session_state.get("user_uid") or user_email  # stable ID we can log with

# Sidebar chip
with st.sidebar:
    st.markdown("### Account")
    st.success(f"Signed in: {user_email}")
    st.caption(f"UID: {user_uid}")
    if st.button("Sign out"):
        sign_out()

# -------------------- App content --------------------
st.title("Rutgers Research Finder")
st.caption("Discover professors, compose outreach, and track progress — all in one place.")

tab1, tab2, tab3 = st.tabs(["🔎 Discover", "✉️ Outreach", "📊 Tracker"])

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
                "summary": (p.get("research_summary") or "")[:160] + ("..." if p.get("research_summary") and len(p.get("research_summary") > 160) else ""),
                "website": p.get("website")
            } for p in profs])
            st.dataframe(df2, use_container_width=True)
        else:
            st.info("No professors found yet. Your teammate may still be ingesting data.")

# -------------------- Outreach tab --------------------
with tab2:
    st.subheader("Compose & Send Outreach")
    st.write("Queue:", st.session_state.get("outreach_queue") or "Empty")

    with st.form("outreach_form"):
        recipients_csv = st.text_input(
            "Professor doc IDs (comma-separated)",
            value=",".join(st.session_state.get("outreach_queue", []))
        )
        subject = st.text_input("Subject", value="Prospective undergraduate researcher")
        body = st.text_area("Body (plain text)", height=220, value=(
            "Hello Professor LASTNAME,\n\n"
            "My name is YOUR_NAME, a YEAR studying MAJOR at Rutgers. "
            "I’m reaching out because your recent work on TOPIC aligns with my interests.\n\n"
            "I’ve attached my resume (and transcript). Would it be possible to set up a brief call?\n\n"
            "Best,\nYOUR_NAME\nYOUR_EMAIL"
        ))

        # Optional file uploads: if you add a /send-email-direct endpoint later
        colA, colB = st.columns(2)
        with colA:
            resume_file = st.file_uploader("Attach Resume (PDF)", type=["pdf"])
        with colB:
            transcript_file = st.file_uploader("Attach Transcript (PDF, optional)", type=["pdf"])

        # Use the Google UID/email as the student id for logging for now
        student_uid = st.text_input("Your student ID/UID (for logging)", value=user_uid)

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
            "refresh_token": refresh_token,  # lets backend refresh when needed
            "resume_url": None,
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
