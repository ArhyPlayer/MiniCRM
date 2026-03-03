"""
Google Sheets CRUD client via Google Sheets API v4.

Usage in other modules:
    from google_sheets_client import GoogleSheetsClient

    client = GoogleSheetsClient(
        spreadsheet_id="your_spreadsheet_id",
        credentials_path="excel-factory-488906-cd544edd406e.json",
    )
    rows = client.read_all()
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsClient:
    """CRUD-клиент для работы с Google Таблицами через сервисный аккаунт.

    Args:
        spreadsheet_id: ID таблицы из URL (часть между /d/ и /edit).
        credentials_path: Путь к JSON-ключу сервисного аккаунта.
        default_sheet: Имя листа по умолчанию (например «Sheet1» или «Лист1»).
    """

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str,
        default_sheet: str = "Sheet1",
    ) -> None:
        if not os.path.isfile(credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")

        self.spreadsheet_id = spreadsheet_id
        self.default_sheet = default_sheet

        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=_SCOPES,
        )
        service = build("sheets", "v4", credentials=creds)
        self._sheets = service.spreadsheets()

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def read_range(self, range_notation: str) -> list[list[Any]]:
        """Читает диапазон ячеек и возвращает список строк.

        Args:
            range_notation: A1-нотация, например «Sheet1!A1:D10» или «A1:D10».
                            Если лист не указан, используется default_sheet.

        Returns:
            Двумерный список значений. Пустые строки в хвосте не возвращаются.
        """
        range_notation = self._ensure_sheet(range_notation)
        try:
            result = (
                self._sheets.values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_notation)
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"read_range failed: {exc}") from exc

        return result.get("values", [])

    def read_all(self, sheet: str | None = None) -> list[list[Any]]:
        """Читает весь лист целиком.

        Args:
            sheet: Имя листа. Если не передан, используется default_sheet.

        Returns:
            Двумерный список значений.
        """
        sheet = sheet or self.default_sheet
        try:
            result = (
                self._sheets.values()
                .get(spreadsheetId=self.spreadsheet_id, range=sheet)
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"read_all failed: {exc}") from exc
        return result.get("values", [])

    # ------------------------------------------------------------------
    # CREATE / UPDATE
    # ------------------------------------------------------------------

    def write_range(
        self,
        range_notation: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Записывает значения в указанный диапазон (перезаписывает существующее).

        Args:
            range_notation: A1-нотация диапазона.
            values: Двумерный список значений для записи.
            value_input_option: «RAW» или «USER_ENTERED» (форматирование, формулы).

        Returns:
            Ответ API (dict).
        """
        range_notation = self._ensure_sheet(range_notation)
        body = {"values": values}
        try:
            result = (
                self._sheets.values()
                .update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_notation,
                    valueInputOption=value_input_option,
                    body=body,
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"write_range failed: {exc}") from exc

        return result

    def update_cell(
        self,
        cell: str,
        value: Any,
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Обновляет одну ячейку.

        Args:
            cell: Адрес ячейки, например «A1» или «Sheet1!B3».
            value: Новое значение.
            value_input_option: «RAW» или «USER_ENTERED».

        Returns:
            Ответ API (dict).
        """
        return self.write_range(cell, [[value]], value_input_option)

    def append_rows(
        self,
        values: list[list[Any]],
        sheet: str | None = None,
        value_input_option: str = "USER_ENTERED",
        insert_data_option: str = "INSERT_ROWS",
    ) -> dict:
        """Добавляет строки после последней заполненной строки на листе.

        Args:
            values: Двумерный список строк для добавления.
            sheet: Имя листа. Если не передан, используется default_sheet.
            value_input_option: «RAW» или «USER_ENTERED».
            insert_data_option: «INSERT_ROWS» (вставить) или «OVERWRITE» (перезаписать).

        Returns:
            Ответ API (dict).
        """
        sheet = sheet or self.default_sheet
        range_notation = f"{sheet}"
        body = {"values": values}
        try:
            result = (
                self._sheets.values()
                .append(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_notation,
                    valueInputOption=value_input_option,
                    insertDataOption=insert_data_option,
                    body=body,
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"append_rows failed: {exc}") from exc

        return result

    # ------------------------------------------------------------------
    # DELETE (clear)
    # ------------------------------------------------------------------

    def clear_range(self, range_notation: str) -> dict:
        """Очищает содержимое диапазона (значения), не удаляя строки/столбцы.

        Args:
            range_notation: A1-нотация диапазона.

        Returns:
            Ответ API (dict).
        """
        range_notation = self._ensure_sheet(range_notation)
        try:
            result = (
                self._sheets.values()
                .clear(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_notation,
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"clear_range failed: {exc}") from exc

        return result

    def clear_all(self, sheet: str | None = None) -> dict:
        """Полностью очищает лист.

        Args:
            sheet: Имя листа. Если не передан, используется default_sheet.

        Returns:
            Ответ API (dict).
        """
        sheet = sheet or self.default_sheet
        try:
            result = (
                self._sheets.values()
                .clear(spreadsheetId=self.spreadsheet_id, range=sheet)
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"clear_all failed: {exc}") from exc
        return result

    # ------------------------------------------------------------------
    # METADATA
    # ------------------------------------------------------------------

    def get_sheet_names(self) -> list[str]:
        """Возвращает список имён всех листов в таблице."""
        try:
            meta = self._sheets.get(spreadsheetId=self.spreadsheet_id).execute()
        except HttpError as exc:
            raise RuntimeError(f"get_sheet_names failed: {exc}") from exc
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def get_sheet_id(self, sheet: str | None = None) -> int:
        """Возвращает числовой sheetId листа (для batchUpdate и др.)."""
        sheet = sheet or self.default_sheet
        try:
            meta = self._sheets.get(spreadsheetId=self.spreadsheet_id).execute()
        except HttpError as exc:
            raise RuntimeError(f"get_sheet_id failed: {exc}") from exc
        for s in meta.get("sheets", []):
            if s["properties"]["title"] == sheet:
                return s["properties"]["sheetId"]
        raise KeyError(f"Лист «{sheet}» не найден")

    def batch_update(self, requests: list[dict]) -> dict:
        """Выполняет пакетное обновление таблицы (слияние, форматирование и т.д.).

        Args:
            requests: Список запросов для spreadsheets.batchUpdate.

        Returns:
            Ответ API (dict).
        """
        try:
            return (
                self._sheets.batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"requests": requests},
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"batch_update failed: {exc}") from exc

    # ------------------------------------------------------------------
    # HELPER
    # ------------------------------------------------------------------

    def _ensure_sheet(self, range_notation: str) -> str:
        """Добавляет имя листа к диапазону, если оно не указано явно."""
        if "!" not in range_notation:
            return f"{self.default_sheet}!{range_notation}"
        return range_notation


# ==============================================================================
# Точка входа — проверочное чтение всего листа
# ==============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "1sRKylkjH-PSqpvnVTOsCvs3l4AJtw3U7XuarvOFiiuQ")
    CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "excel-factory-488906-cd544edd406e.json")
    if not os.path.isabs(CREDENTIALS_PATH):
        CREDENTIALS_PATH = str(Path(__file__).parent / CREDENTIALS_PATH)

    client = GoogleSheetsClient(
        spreadsheet_id=SPREADSHEET_ID,
        credentials_path=CREDENTIALS_PATH,
    )

    sheet_names = client.get_sheet_names()
    print(f"Листы в таблице: {sheet_names}\n")

    sheet = sheet_names[0]
    client.default_sheet = sheet

    print(f"Читаю все ячейки листа «{sheet}»...\n")
    rows = client.read_all()

    if not rows:
        print("Таблица пуста.")
    else:
        for row_idx, row in enumerate(rows, start=1):
            print(f"Строка {row_idx:>3}: {row}")

    print(f"\nВсего строк с данными: {len(rows)}")
