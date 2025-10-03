# mailer/gmail_sender.py
import base64
import mimetypes
from typing import List, Optional, Dict, Any, Union
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

def _build_credentials(
    *,
    access_token: str,
    refresh_token: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    scopes: Optional[List[str]] = None,
) -> Credentials:
    """
    Build OAuth credentials; refresh if needed (when a refresh_token is present).
    """
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes or DEFAULT_SCOPES,
    )
    # Refresh if expired and we have a refresh token
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

def _guess_mimetype(filename: str) -> str:
    mt, _ = mimetypes.guess_type(filename or "")
    return mt or "application/octet-stream"

def _email_message(
    *,
    to: str,
    subject: str,
    body_text: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    from_display: Optional[str] = None,   # e.g., "Your Name <me>"
) -> EmailMessage:
    """
    Build an EmailMessage with optional attachments.

    attachments: list of dicts, each can be one of:
      - {"filename": "resume.pdf", "bytes": b"...", "mimetype": "application/pdf"}
      - {"filename": "resume.pdf", "b64": "<base64 string>", "mimetype": "application/pdf"}

    If mimetype omitted, it is guessed from filename.
    """
    msg = EmailMessage()
    msg["To"] = to
    if from_display:
        msg["From"] = from_display  # Gmail will still send as authenticated user
    msg["Subject"] = subject
    msg.set_content(body_text)

    for att in attachments or []:
        filename = att.get("filename") or "attachment"
        mimetype = att.get("mimetype") or _guess_mimetype(filename)

        data: Optional[bytes] = None
        if "bytes" in att and att["bytes"] is not None:
            data = att["bytes"]
        elif "b64" in att and att["b64"] is not None:
            data = base64.b64decode(att["b64"])

        if data is None:
            continue  # skip malformed attachment

        maintype, subtype = mimetype.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    return msg

def send_gmail(
    *,
    access_token: str,
    refresh_token: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    to: str,
    subject: str,
    body_text: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    from_display: Optional[str] = None,
) -> Dict[str, str]:
    """
    Send an email via Gmail API using the signed-in user's account ("me").
    Returns {"id": <gmail message id>, "threadId": <gmail thread id>} on success.
    """
    creds = _build_credentials(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        scopes=DEFAULT_SCOPES,
    )
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    msg = _email_message(
        to=to,
        subject=subject,
        body_text=body_text,
        attachments=attachments,
        from_display=from_display,
    )
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"id": result.get("id", ""), "threadId": result.get("threadId", "")}

# --------- convenience helpers for Streamlit UploadedFile ----------
def filepart_from_uploadedfile(uploaded_file) -> Dict[str, Any]:
    """
    Convert a Streamlit UploadedFile to an attachment dict for send_gmail().
    """
    if uploaded_file is None:
        return {}
    content = uploaded_file.getvalue()  # bytes
    return {
        "filename": uploaded_file.name or "attachment",
        "bytes": content,
        "mimetype": uploaded_file.type or _guess_mimetype(uploaded_file.name),
    }
