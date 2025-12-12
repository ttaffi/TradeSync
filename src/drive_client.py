import os
import io
import pickle
import logging
import ssl
import threading
from typing import Optional, List, Any
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# If modifying these scopes, delete the file token.pickle.
SCOPES: List[str] = ['https://www.googleapis.com/auth/drive']

class DriveClient:
    """
    A wrapper around the Google Drive API to handle file operations
    for TradeSync. Thread-safe using thread-local storage for API clients.
    """

    def __init__(self, credentials_path: str):
        """
        Initialize the Drive API client.
        
        Args:
            credentials_path (str): Path to the OAuth Client ID JSON file.
        """
        self.logger = logging.getLogger(__name__)
        self.creds = self._authenticate(credentials_path)
        self._thread_local = threading.local()

    @property
    def service(self) -> Resource:
        """
        Get the thread-local Drive API service instance.
        If it doesn't exist for the current thread, create it.
        """
        if not hasattr(self._thread_local, 'service'):
            self._thread_local.service = build('drive', 'v3', credentials=self.creds)
        return self._thread_local.service

    def _authenticate(self, credentials_path: str) -> Any:
        """
        Authenticate using OAuth 2.0 User Credentials (Desktop App).
        Falls back to Service Account if the file looks like one (legacy/headless).
        """
        creds = None
        
        # Check if token.pickle exists (cached credentials)
        # Store token.pickle in the same directory as credentials_path
        creds_dir = os.path.dirname(credentials_path)
        token_path = os.path.join(creds_dir, 'token.pickle')
        
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                try:
                    creds = pickle.load(token)
                except Exception:
                    creds = None
                
        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                     raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
                
                from google_auth_oauthlib.flow import InstalledAppFlow
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    # Fallback to Service Account if Flow fails (maybe it IS a service account file)
                    self.logger.warning(f"OAuth Flow failed ({e}), trying Service Account...")
                    credentials = Credentials.from_service_account_file(
                        credentials_path, scopes=SCOPES)
                    return credentials

            # Save the credentials for the next run
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        return creds

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, ConnectionError, TimeoutError, ssl.SSLError))
    )
    def find_file(self, name: str, folder_id: str) -> Optional[str]:
        """
        Find a file by name within a specific folder.
        
        Args:
            name (str): Name of the file to search for.
            folder_id (str): ID of the folder to search in.
            
        Returns:
            Optional[str]: The file ID if found, otherwise None.
        """
        query = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(
            q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        
        if not items:
            return None
        return items[0]['id']

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, ConnectionError, TimeoutError, ssl.SSLError))
    )
    def ensure_folder(self, name: str, parent_id: str) -> str:
        """
        Ensure a folder exists within a parent folder.
        If it doesn't exist, create it.
        
        Args:
            name (str): Name of the folder.
            parent_id (str): ID of the parent folder.
            
        Returns:
            str: The ID of the folder.
        """
        existing_id = self.find_file(name, parent_id)
        if existing_id:
            return existing_id
            
        # Create it
        file_metadata = {
            'name': name,
            'parents': [parent_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        file = self.service.files().create(body=file_metadata, fields='id').execute()
        self.logger.info(f"Created folder: {name} (ID: {file.get('id')})")
        return file.get('id')

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((HttpError, ConnectionError, TimeoutError, ssl.SSLError))
    )
    def download_file(self, file_id: str) -> bytes:
        """
        Download a file's content.
        
        Args:
            file_id (str): The ID of the file to download.
            
        Returns:
            bytes: The file content.
        """
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, ConnectionError, TimeoutError, ssl.SSLError))
    )
    def upload_file(self, path: str, folder_id: str, name: Optional[str] = None) -> str:
        """
        Upload a NEW file to a specific folder.
        
        Args:
            path (str): Local path to the file to upload.
            folder_id (str): Destination folder ID.
            name (str, optional): Name for the file on Drive. Defaults to basename.
            
        Returns:
            str: The ID of the uploaded file.
        """
        if name is None:
            name = os.path.basename(path)
            
        file_metadata = {
            'name': name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(path, resumable=True)
        file = self.service.files().create(body=file_metadata,
                                            media_body=media,
                                            fields='id').execute()
        self.logger.info(f"File uploaded: {name} (ID: {file.get('id')})")
        return file.get('id')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, ConnectionError, TimeoutError, ssl.SSLError))
    )
    def update_file(self, file_id: str, path: str) -> None:
        """
        Update the content of an existing file.
        
        Args:
            file_id (str): ID of the file to update.
            path (str): Local path to the new content file.
        """
        media = MediaFileUpload(path, resumable=True)
        file = self.service.files().update(fileId=file_id,
                                           media_body=media,
                                           fields='id').execute()
        self.logger.info(f"File updated with content from {path}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, ConnectionError, TimeoutError, ssl.SSLError))
    )
    def manage_backups(self, folder_id: str, name_prefix: str, retention_count: int) -> None:
        """
        Keep only the latest `retention_count` backups matching the prefix.
        
        Args:
            folder_id (str): The folder ID where backups are stored.
            name_prefix (str): The prefix of backup files (e.g. "backup_").
            retention_count (int): Max number of files to keep.
        """
        query = f"name contains '{name_prefix}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(
            q=query, 
            orderBy="createdTime desc", 
            spaces='drive', 
            fields='files(id, name, createdTime)'
        ).execute()
        
        backups = results.get('files', [])
        
        if len(backups) > retention_count:
            to_delete = backups[retention_count:]
            for file in to_delete:
                try:
                    self.service.files().delete(fileId=file['id']).execute()
                    self.logger.info(f"Deleted old backup: {file['name']} (ID: {file['id']})")
                except Exception as e:
                    self.logger.error(f"Failed to delete backup {file['name']}: {e}")
