import os
import requests
import shutil
from pathlib import Path
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")

logger = logging.getLogger("drive_uploader")
logging.basicConfig(level=logging.INFO)

# ------------------- AUTHENTICATION -------------------
def authenticate():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)

# ------------------- DRIVE HELPERS -------------------
def get_folder_id(service, folder_name, parent_id=None):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    items = results.get("files", [])

    if items:
        return items[0]["id"]

    file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        file_metadata["parents"] = [parent_id]

    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder.get("id")


def upload_or_update_file(service, folder_id, local_path, file_name):
    media = MediaFileUpload(local_path, resumable=True)
    try:
        query = f"name='{file_name}' and '{folder_id}' in parents"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get("files", [])
        if items:
            file_id = items[0]["id"]
            service.files().update(fileId=file_id, media_body=media).execute()
            logger.info(f"Updated: {file_name}")
        else:
            file_metadata = {"name": file_name, "parents": [folder_id]}
            service.files().create(body=file_metadata, media_body=media, fields="id").execute()
            logger.info(f"Uploaded: {file_name}")
    except Exception as e:
        logger.error(f"Error uploading {file_name}: {e}")

# ------------------- DOWNLOAD -------------------
def download_file(url, save_path):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                shutil.copyfileobj(response.raw, f)
            logger.info(f"Downloaded: {save_path}")
        else:
            logger.error(f"Failed to download {url}")
    except Exception as e:
        logger.error(f"Exception downloading {url}: {e}")

# ------------------- SYNC FOLDERS -------------------
def sync_folder_to_drive(service, local_folder, drive_parent_id):
    """Recursively upload/update local folder to Drive."""
    for item in os.listdir(local_folder):
        local_path = os.path.join(local_folder, item)
        if os.path.isdir(local_path):
            folder_id = get_folder_id(service, item, drive_parent_id)
            sync_folder_to_drive(service, local_path, folder_id)
        else:
            upload_or_update_file(service, drive_parent_id, local_path, item)

# ------------------- MAIN WORKFLOW -------------------
def process_files(files_to_download, owners):
    service = authenticate()
    root_folder_id = get_folder_id(service, "Instructor Files")
    downloads_dir = Path(BASE_DIR) / ".." / "Instructor Files"
    downloads_dir.mkdir(exist_ok=True)
    for owner in owners:
        owner_folder = downloads_dir / owner
        owner_folder.mkdir(exist_ok=True)
        get_folder_id(service, owner, root_folder_id)
    # Download and upload files
    for file_info in files_to_download:
        file_url = file_info["url"]
        owner = file_info["owner"]
        file_name = file_info["file_name"]
        owner_folder = downloads_dir / owner
        local_path = owner_folder / file_name
        download_file(file_url, local_path)
        owner_drive_id = get_folder_id(service, owner, root_folder_id)
        upload_or_update_file(service, owner_drive_id, local_path, file_name)
