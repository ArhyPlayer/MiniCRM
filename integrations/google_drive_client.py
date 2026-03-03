"""
Google Drive CRUD client via Google Drive API v3.

Два варианта подключения:

  1. Сервисный аккаунт (GoogleDriveClient) — для серверных/автоматизированных задач.
     Файлы создаются от имени сервисного аккаунта.

  2. OAuth2 / личный аккаунт (GoogleDriveOAuthClient) — файлы создаются от имени
     конкретного пользователя. При первом запуске открывается браузер для авторизации;
     токен сохраняется локально и обновляется автоматически.

Usage:
    from google_drive_client import GoogleDriveClient, GoogleDriveOAuthClient

    # Сервисный аккаунт
    sa = GoogleDriveClient(credentials_path="excel-factory-488906-cd544edd406e.json")
    sa.list_files()

    # OAuth2 (личный аккаунт)
    oauth = GoogleDriveOAuthClient(client_secret_path="client_secret_...json")
    oauth.create_document("Мой документ", folder_id="<folder_id>")
    oauth.create_spreadsheet("Моя таблица", folder_id="<folder_id>")
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload


_SCOPES = ["https://www.googleapis.com/auth/drive"]

# Mime-типы Google Workspace
_MIME_GDOC   = "application/vnd.google-apps.document"
_MIME_GSHEET = "application/vnd.google-apps.spreadsheet"
_MIME_FOLDER = "application/vnd.google-apps.folder"


class GoogleDriveClient:
    """CRUD-клиент для работы с файлами Google Drive через сервисный аккаунт.

    Args:
        credentials_path: Путь к JSON-ключу сервисного аккаунта.
        default_folder_id: ID папки по умолчанию (используется, когда folder_id не передан явно).
    """

    def __init__(
        self,
        credentials_path: str,
        default_folder_id: str | None = None,
    ) -> None:
        if not os.path.isfile(credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")

        self.default_folder_id = default_folder_id

        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=_SCOPES,
        )
        service = build("drive", "v3", credentials=creds)
        self._files = service.files()

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_files(
        self,
        folder_id: str | None = None,
        query: str | None = None,
        page_size: int = 100,
        fields: str = "files(id, name, mimeType, size, modifiedTime, parents)",
    ) -> list[dict]:
        """Возвращает список файлов и папок, доступных сервисному аккаунту.

        Args:
            folder_id: Ограничить поиск конкретной папкой. Если не указан — используется
                       default_folder_id; если и он None — возвращаются все доступные файлы.
            query: Дополнительный q-фильтр Drive API, например «mimeType='application/pdf'».
            page_size: Количество элементов на страницу (1–1000).
            fields: Список полей метаданных для возврата.

        Returns:
            Список словарей с метаданными файлов.
        """
        q_parts: list[str] = ["trashed = false"]
        effective_folder = folder_id or self.default_folder_id
        if effective_folder:
            q_parts.append(f"'{effective_folder}' in parents")
        if query:
            q_parts.append(query)

        q = " and ".join(q_parts)
        all_files: list[dict] = []
        page_token: str | None = None

        try:
            while True:
                kwargs: dict[str, Any] = {
                    "q": q,
                    "pageSize": page_size,
                    "fields": f"nextPageToken, {fields}",
                }
                if page_token:
                    kwargs["pageToken"] = page_token

                response = self._files.list(**kwargs).execute()
                all_files.extend(response.get("files", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as exc:
            raise RuntimeError(f"list_files failed: {exc}") from exc

        return all_files

    def get_file(
        self,
        file_id: str,
        fields: str = "id, name, mimeType, size, modifiedTime, parents",
    ) -> dict:
        """Возвращает метаданные файла по его ID.

        Args:
            file_id: ID файла в Google Drive.
            fields: Поля для возврата.

        Returns:
            Словарь с метаданными файла.
        """
        try:
            return self._files.get(fileId=file_id, fields=fields).execute()
        except HttpError as exc:
            raise RuntimeError(f"get_file failed: {exc}") from exc

    def download_file(self, file_id: str, dest_path: str | Path) -> Path:
        """Скачивает файл из Drive и сохраняет его локально.

        Args:
            file_id: ID файла в Google Drive.
            dest_path: Путь для сохранения (включая имя файла).

        Returns:
            Объект Path, указывающий на сохранённый файл.
        """
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            request = self._files.get_media(fileId=file_id)
        except HttpError as exc:
            raise RuntimeError(f"download_file failed: {exc}") from exc

        with open(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return dest

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def upload_file(
        self,
        name: str,
        source: str | Path | bytes,
        mime_type: str = "application/octet-stream",
        folder_id: str | None = None,
    ) -> dict:
        """Загружает файл в Google Drive.

        Args:
            name: Имя файла в Drive.
            source: Локальный путь к файлу (str/Path) или содержимое в байтах (bytes).
            mime_type: MIME-тип файла.
            folder_id: ID папки-родителя. Если не указан — используется default_folder_id.

        Returns:
            Метаданные созданного файла: id, name, mimeType.
        """
        folder = folder_id or self.default_folder_id
        metadata: dict[str, Any] = {"name": name}
        if folder:
            metadata["parents"] = [folder]

        try:
            if isinstance(source, (str, Path)):
                media = MediaFileUpload(str(source), mimetype=mime_type, resumable=True)
            else:
                media = MediaIoBaseUpload(io.BytesIO(source), mimetype=mime_type, resumable=True)

            return (
                self._files.create(
                    body=metadata,
                    media_body=media,
                    fields="id, name, mimeType",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"upload_file failed: {exc}") from exc

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        """Создаёт папку в Google Drive.

        Args:
            name: Название папки.
            parent_id: ID папки-родителя. Если не указан — используется default_folder_id.

        Returns:
            Метаданные созданной папки: id, name, mimeType.
        """
        parent = parent_id or self.default_folder_id
        metadata: dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent:
            metadata["parents"] = [parent]

        try:
            return (
                self._files.create(body=metadata, fields="id, name, mimeType")
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"create_folder failed: {exc}") from exc

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def rename_file(self, file_id: str, new_name: str) -> dict:
        """Переименовывает файл или папку.

        Args:
            file_id: ID файла/папки.
            new_name: Новое имя.

        Returns:
            Обновлённые метаданные: id, name.
        """
        try:
            return (
                self._files.update(
                    fileId=file_id,
                    body={"name": new_name},
                    fields="id, name",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"rename_file failed: {exc}") from exc

    def update_content(
        self,
        file_id: str,
        source: str | Path | bytes,
        mime_type: str = "application/octet-stream",
    ) -> dict:
        """Заменяет содержимое существующего файла без изменения его имени или расположения.

        Args:
            file_id: ID файла в Google Drive.
            source: Новое содержимое — локальный путь (str/Path) или байты (bytes).
            mime_type: MIME-тип нового содержимого.

        Returns:
            Обновлённые метаданные: id, name, mimeType, modifiedTime.
        """
        try:
            if isinstance(source, (str, Path)):
                media = MediaFileUpload(str(source), mimetype=mime_type, resumable=True)
            else:
                media = MediaIoBaseUpload(io.BytesIO(source), mimetype=mime_type, resumable=True)

            return (
                self._files.update(
                    fileId=file_id,
                    media_body=media,
                    fields="id, name, mimeType, modifiedTime",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"update_content failed: {exc}") from exc

    def move_file(self, file_id: str, new_folder_id: str) -> dict:
        """Перемещает файл в другую папку.

        Args:
            file_id: ID файла.
            new_folder_id: ID папки назначения.

        Returns:
            Обновлённые метаданные: id, name, parents.
        """
        try:
            file_meta = self._files.get(fileId=file_id, fields="parents").execute()
            previous_parents = ",".join(file_meta.get("parents", []))

            return (
                self._files.update(
                    fileId=file_id,
                    addParents=new_folder_id,
                    removeParents=previous_parents,
                    fields="id, name, parents",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"move_file failed: {exc}") from exc

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete_file(self, file_id: str) -> None:
        """Удаляет файл или папку навсегда (минуя корзину).

        Args:
            file_id: ID файла/папки для безвозвратного удаления.
        """
        try:
            self._files.delete(fileId=file_id).execute()
        except HttpError as exc:
            raise RuntimeError(f"delete_file failed: {exc}") from exc

    def trash_file(self, file_id: str) -> dict:
        """Перемещает файл в корзину (мягкое, восстановимое удаление).

        Args:
            file_id: ID файла/папки.

        Returns:
            Обновлённые метаданные: id, name, trashed.
        """
        try:
            return (
                self._files.update(
                    fileId=file_id,
                    body={"trashed": True},
                    fields="id, name, trashed",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"trash_file failed: {exc}") from exc


# ==============================================================================
# OAuth2 helper
# ==============================================================================

def _load_oauth_creds(client_secret_path: str, token_path: str) -> Credentials:
    """Загружает сохранённый токен или запускает OAuth2-поток авторизации.

    При первом вызове открывается браузер; пользователь разрешает доступ, после
    чего токен сохраняется в token_path. При последующих вызовах токен читается
    из файла и при необходимости обновляется автоматически (refresh).

    Args:
        client_secret_path: Путь к client_secret_*.json (тип «installed»).
        token_path: Путь для сохранения/чтения токена пользователя.

    Returns:
        Действующий объект Credentials.
    """
    creds: Credentials | None = None

    if os.path.isfile(token_path):
        creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())

    return creds


# ==============================================================================
# OAuth2-клиент (личный аккаунт пользователя)
# ==============================================================================

class GoogleDriveOAuthClient(GoogleDriveClient):
    """CRUD-клиент Google Drive + создание Docs/Sheets от имени пользователя (OAuth2).

    Наследует все CRUD-методы GoogleDriveClient (list_files, upload_file, delete_file
    и т.д.) и добавляет create_document / create_spreadsheet.

    Первый запуск открывает браузер для авторизации. Токен сохраняется локально
    и используется повторно (с автоматическим обновлением).

    Args:
        client_secret_path: Путь к client_secret_*.json (тип «installed»).
        token_path: Файл для хранения токена пользователя (создаётся автоматически).
        default_folder_id: ID папки по умолчанию для операций создания/листинга.
    """

    def __init__(
        self,
        client_secret_path: str,
        token_path: str = "token_drive.json",
        default_folder_id: str | None = None,
    ) -> None:
        if not os.path.isfile(client_secret_path):
            raise FileNotFoundError(f"Client secret file not found: {client_secret_path}")

        self.default_folder_id = default_folder_id
        creds = _load_oauth_creds(client_secret_path, token_path)
        service = build("drive", "v3", credentials=creds)
        self._files = service.files()

    # ------------------------------------------------------------------
    # Создание Google Workspace файлов
    # ------------------------------------------------------------------

    def create_document(self, name: str, folder_id: str | None = None) -> dict:
        """Создаёт пустой Google Документ в указанной папке.

        Args:
            name: Название документа.
            folder_id: ID папки-родителя. Если не указан — используется default_folder_id;
                       если и он None — документ создаётся в корне My Drive пользователя.

        Returns:
            Метаданные созданного файла: id, name, mimeType, webViewLink.
        """
        return self._create_workspace_file(name, _MIME_GDOC, folder_id)

    def create_spreadsheet(self, name: str, folder_id: str | None = None) -> dict:
        """Создаёт пустую Google Таблицу в указанной папке.

        Args:
            name: Название таблицы.
            folder_id: ID папки-родителя. Если не указан — используется default_folder_id;
                       если и он None — таблица создаётся в корне My Drive пользователя.

        Returns:
            Метаданные созданного файла: id, name, mimeType, webViewLink.
        """
        return self._create_workspace_file(name, _MIME_GSHEET, folder_id)

    # ------------------------------------------------------------------
    # Внутренний хелпер
    # ------------------------------------------------------------------

    def _create_workspace_file(
        self, name: str, mime_type: str, folder_id: str | None
    ) -> dict:
        folder = folder_id or self.default_folder_id
        metadata: dict[str, Any] = {"name": name, "mimeType": mime_type}
        if folder:
            metadata["parents"] = [folder]
        try:
            return (
                self._files.create(
                    body=metadata,
                    fields="id, name, mimeType, webViewLink",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"_create_workspace_file failed: {exc}") from exc


# ==============================================================================
# Точка входа — чтение всех файлов, доступных сервисному аккаунту
# ==============================================================================

def _print_files_table(files: list[dict]) -> None:
    col_id, col_type = 44, 42
    print(f"{'ID':<{col_id}} {'MIME-тип':<{col_type}} Имя")
    print("-" * (col_id + col_type + 40))
    for f in files:
        fid   = f.get("id", "—")
        ftype = f.get("mimeType", "—")
        fname = f.get("name", "—")
        fsize = f.get("size")
        size_str = f"  ({int(fsize):,} байт)".replace(",", " ") if fsize else ""
        print(f"{fid:<{col_id}} {ftype:<{col_type}} {fname}{size_str}")
    print(f"\nВсего объектов: {len(files)}")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    BASE_DIR = Path(__file__).parent

    # ------------------------------------------------------------------
    # OAuth2-клиент (личный аккаунт)
    # ------------------------------------------------------------------
    CLIENT_SECRET = os.getenv(
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "client_secret_353987013951-dm6ap9v6tvf1hg8i6d3siravbehlfkbh.apps.googleusercontent.com.json",
    )
    TOKEN_PATH = os.getenv("GOOGLE_OAUTH_TOKEN_PATH", "token_drive.json")

    if not os.path.isabs(CLIENT_SECRET):
        CLIENT_SECRET = str(BASE_DIR / CLIENT_SECRET)
    if not os.path.isabs(TOKEN_PATH):
        TOKEN_PATH = str(BASE_DIR / TOKEN_PATH)

    FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID") or None

    print("=" * 70)
    print("OAuth2-клиент (личный аккаунт пользователя)")
    print("=" * 70)
    print("При первом запуске откроется браузер для авторизации.\n")

    oauth_client = GoogleDriveOAuthClient(
        client_secret_path=CLIENT_SECRET,
        token_path=TOKEN_PATH,
        default_folder_id=FOLDER_ID,
    )

    print("Запрашиваю список файлов...\n")
    files = oauth_client.list_files()

    if not files:
        print("Папка пуста или файлы не найдены.")
    else:
        _print_files_table(files)