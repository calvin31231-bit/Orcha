from __future__ import annotations

from pathlib import Path
from typing import Any

from shorts_orchestrator.settings import settings

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def _import_google_deps():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Google API packages are not installed. Run: pip install -r requirements.txt"
        ) from exc
    return Request, Credentials, InstalledAppFlow, build, MediaFileUpload


def get_credentials():
    Request, Credentials, InstalledAppFlow, _, _ = _import_google_deps()
    token_path = Path(settings.youtube_token_file)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_secrets = Path(settings.youtube_client_secrets)
            if not client_secrets.exists():
                raise FileNotFoundError(
                    f"YouTube OAuth client secrets not found at {client_secrets}. "
                    "Create a Google Cloud OAuth Desktop client and save it there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def youtube_service():
    _, _, _, build, _ = _import_google_deps()
    return build("youtube", "v3", credentials=get_credentials())


def analytics_service():
    _, _, _, build, _ = _import_google_deps()
    return build("youtubeAnalytics", "v2", credentials=get_credentials())


def search_youtube(query: str, max_results: int = 10, order: str = "viewCount", video_license: str | None = None) -> list[dict[str, Any]]:
    service = youtube_service()
    request_kwargs: dict[str, Any] = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": order,
        "safeSearch": "strict",
    }
    if video_license:
        request_kwargs["videoLicense"] = video_license
    resp = service.search().list(**request_kwargs).execute()
    return resp.get("items", [])


def upload_video(
    file_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy_status: str = "private",
    made_for_kids: bool = False,
    category_id: str = "22",
    notify_subscribers: bool = False,
) -> str:
    _, _, _, _, MediaFileUpload = _import_google_deps()
    service = youtube_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
        notifySubscribers=notify_subscribers,
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def get_channel_basic_analytics(start_date: str, end_date: str) -> dict[str, Any]:
    # Note: Revenue metrics usually require monetized/YPP access and may not be available to all channels.
    svc = analytics_service()
    result = svc.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        metrics="views,likes,comments,shares,estimatedMinutesWatched,subscribersGained",
        dimensions="day",
        sort="day",
    ).execute()
    return result
