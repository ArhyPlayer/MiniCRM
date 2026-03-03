"""
Tkinter-клиент для Mini CRM.

Требует запущенного CRM-сервера:
    docker compose up

Запуск GUI:
    python start_gui.py
"""

from __future__ import annotations

import json
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

import requests

# ── Путь к Google-интеграциям (добавляем в sys.path) ──────────────────────────
_INTEGRATIONS_DIR = Path(__file__).parent / "integrations"
sys.path.insert(0, str(_INTEGRATIONS_DIR))

BASE_URL = "http://localhost:8000"

# ── Константы статусов ────────────────────────────────────────────────────────

CLIENT_STATUSES = ["lead", "active", "inactive", "archived"]
DEAL_STATUSES   = ["new", "negotiation", "won", "lost", "paused"]
TASK_STATUSES   = ["pending", "in_progress", "done", "cancelled"]
CURRENCIES      = ["RUB", "USD", "EUR", "GBP", "CNY"]


# ══════════════════════════════════════════════════════════════════════════════
# HTTP-КЛИЕНТ
# ══════════════════════════════════════════════════════════════════════════════

class APIClient:
    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        r = self._session.get(f"{self.base}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: Dict) -> Any:
        r = self._session.post(f"{self.base}{path}", json=body, timeout=5)
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, body: Optional[Dict] = None) -> Any:
        r = self._session.patch(f"{self.base}{path}", json=body or {}, timeout=5)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> None:
        r = self._session.delete(f"{self.base}{path}", timeout=5)
        r.raise_for_status()

    # ── Clients ───────────────────────────────────────────────────────────────

    def get_clients(self, status: str = None, limit: int = 200) -> List[Dict]:
        p: Dict[str, Any] = {"limit": limit}
        if status:
            p["status"] = status
        return self._get("/clients", p)

    def search_clients(self, q: str, limit: int = 100) -> List[Dict]:
        return self._get("/clients/search", {"q": q, "limit": limit})

    def get_client(self, cid: int) -> Dict:
        return self._get(f"/clients/{cid}")

    def create_client(self, data: Dict) -> Dict:
        return self._post("/clients", data)

    def update_client(self, cid: int, data: Dict) -> Dict:
        return self._patch(f"/clients/{cid}", data)

    def archive_client(self, cid: int) -> Dict:
        return self._patch(f"/clients/{cid}/archive")

    def delete_client(self, cid: int) -> None:
        self._delete(f"/clients/{cid}")

    # ── Deals ─────────────────────────────────────────────────────────────────

    def get_deals(self, status: str = None, client_id: int = None, limit: int = 200) -> List[Dict]:
        p: Dict[str, Any] = {"limit": limit}
        if status:
            p["status"] = status
        if client_id is not None:
            p["client_id"] = client_id
        return self._get("/deals", p)

    def search_deals(self, q: str, limit: int = 100) -> List[Dict]:
        return self._get("/deals/search", {"q": q, "limit": limit})

    def get_deal(self, did: int) -> Dict:
        return self._get(f"/deals/{did}")

    def create_deal(self, data: Dict) -> Dict:
        return self._post("/deals", data)

    def update_deal(self, did: int, data: Dict) -> Dict:
        return self._patch(f"/deals/{did}", data)

    def delete_deal(self, did: int) -> None:
        self._delete(f"/deals/{did}")

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def get_tasks(self, status: str = None, client_id: int = None,
                  deal_id: int = None, limit: int = 200) -> List[Dict]:
        p: Dict[str, Any] = {"limit": limit}
        if status:
            p["status"] = status
        if client_id is not None:
            p["client_id"] = client_id
        if deal_id is not None:
            p["deal_id"] = deal_id
        return self._get("/tasks", p)

    def create_task(self, data: Dict) -> Dict:
        return self._post("/tasks", data)

    def update_task(self, tid: int, data: Dict) -> Dict:
        return self._patch(f"/tasks/{tid}", data)

    def complete_task(self, tid: int) -> Dict:
        return self._patch(f"/tasks/{tid}/done")

    def reopen_task(self, tid: int) -> Dict:
        return self._patch(f"/tasks/{tid}/reopen")

    def delete_task(self, tid: int) -> None:
        self._delete(f"/tasks/{tid}")

    def get_dashboard(self) -> Dict:
        return self._get("/dashboard")


api = APIClient(BASE_URL)


# ══════════════════════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ══════════════════════════════════════════════════════════════════════════════

def _err(e: Exception) -> None:
    msg = str(e)
    if isinstance(e, requests.HTTPError) and e.response is not None:
        try:
            detail = e.response.json().get("detail", msg)
            msg = f"HTTP {e.response.status_code}: {detail}"
        except Exception:
            pass
    messagebox.showerror("Ошибка", msg)


def _fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        return iso[:10].replace("-", ".") + " " + iso[11:16]
    except Exception:
        return iso[:16]


# ══════════════════════════════════════════════════════════════════════════════
# НАСТРОЙКИ GOOGLE
# ══════════════════════════════════════════════════════════════════════════════

class GoogleSettings:
    """Загрузка и сохранение настроек Google в data/google_settings.json."""

    _PATH = Path("data/google_settings.json")

    @classmethod
    def load(cls) -> Dict[str, str]:
        try:
            return json.loads(cls._PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @classmethod
    def save(cls, data: Dict[str, str]) -> None:
        cls._PATH.parent.mkdir(parents=True, exist_ok=True)
        cls._PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def is_configured(cls) -> bool:
        s = cls.load()
        return bool(s.get("client_secret_path") and s.get("service_account_path"))


# ══════════════════════════════════════════════════════════════════════════════
# ДИАЛОГ НАСТРОЕК GOOGLE
# ══════════════════════════════════════════════════════════════════════════════

class GoogleSettingsDialog(tk.Toplevel):
    """Модальный диалог для настройки Google OAuth и Service Account."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Настройки Google")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._data = GoogleSettings.load()
        self._vars: Dict[str, tk.StringVar] = {}
        self._build()
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()  // 2 - self.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{px}+{py}")
        self.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)

        fields = [
            (
                "client_secret_path",
                "OAuth Client Secret *",
                "file",
                "JSON из Google Cloud Console (тип приложения: Desktop / installed)",
            ),
            (
                "service_account_path",
                "Service Account JSON *",
                "file",
                "JSON ключ сервисного аккаунта с доступом к Sheets API",
            ),
            (
                "folder_id",
                "ID папки в Google Drive",
                "paste",
                "Из URL: drive.google.com/drive/folders/  ← вот этот ID",
            ),
            (
                "token_path",
                "Файл OAuth-токена",
                "file",
                "Где сохранять токен (по умолчанию: credentials/token_drive.json)",
            ),
        ]

        for i, (key, label, wtype, hint) in enumerate(fields):
            base_row = i * 3

            ttk.Label(
                frame, text=label + ":",
                font=("TkDefaultFont", 10, "bold"),
            ).grid(row=base_row, column=0, columnspan=3, sticky="w",
                   pady=(14 if i > 0 else 0, 2))

            var = tk.StringVar(value=self._data.get(key, ""))
            self._vars[key] = var

            entry = ttk.Entry(frame, textvariable=var, width=50)
            entry.grid(row=base_row + 1, column=0, sticky="ew", padx=(0, 6))

            if wtype == "file":
                ttk.Button(
                    frame, text="Обзор…", width=8,
                    command=lambda k=key: self._browse(k),
                ).grid(row=base_row + 1, column=1, sticky="w")
            elif wtype == "paste":
                ttk.Button(
                    frame, text="Вставить", width=9,
                    command=lambda v=var: self._paste(v),
                ).grid(row=base_row + 1, column=1, sticky="w")

            ttk.Label(
                frame, text=hint,
                foreground="#6B7280", font=("TkDefaultFont", 9),
            ).grid(row=base_row + 2, column=0, columnspan=3, sticky="w")

        sep_row = len(fields) * 3
        ttk.Separator(frame, orient="horizontal").grid(
            row=sep_row, column=0, columnspan=3, sticky="ew", pady=(18, 10)
        )

        btn_f = ttk.Frame(frame)
        btn_f.grid(row=sep_row + 1, column=0, columnspan=3)
        ttk.Button(btn_f, text="  Сохранить  ", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_f, text="  Отмена  ",   command=self.destroy).pack(side="left", padx=6)

        self.bind("<Escape>", lambda e: self.destroy())

    def _browse(self, key: str) -> None:
        path = filedialog.askopenfilename(
            title="Выберите JSON файл",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")],
        )
        if path:
            self._vars[key].set(path)

    def _paste(self, var: tk.StringVar) -> None:
        try:
            var.set(self.clipboard_get())
        except Exception:
            pass

    def _save(self) -> None:
        data = {k: v.get().strip() for k, v in self._vars.items()}
        if not data.get("token_path"):
            data["token_path"] = str(
                Path(__file__).parent / "credentials" / "token_drive.json"
            )
        if not data.get("client_secret_path"):
            messagebox.showwarning("Внимание", "Укажите путь к OAuth Client Secret.", parent=self)
            return
        if not data.get("service_account_path"):
            messagebox.showwarning("Внимание", "Укажите путь к Service Account JSON.", parent=self)
            return
        GoogleSettings.save(data)
        messagebox.showinfo("Сохранено", "Настройки Google сохранены.", parent=self)
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# СЕРВИС ЭКСПОРТА В GOOGLE SHEETS
# ══════════════════════════════════════════════════════════════════════════════

class ExportService:
    """
    Создаёт Google Spreadsheet через Drive OAuth и записывает данные
    с форматированием через Sheets Service Account.
    """

    def export(
        self,
        title: str,
        headers: List[str],
        data_rows: List[List],
        analysis: List[List],
    ) -> str:
        """
        Возвращает webViewLink на созданную таблицу.

        Параметры
        ---------
        title      : имя файла в Google Drive
        headers    : заголовки столбцов (1-я строка)
        data_rows  : данные таблицы
        analysis   : [[метка, значение], ...] — блок аналитики снизу
        """
        from google_drive_client import GoogleDriveOAuthClient
        from google_sheets_client import GoogleSheetsClient

        s = GoogleSettings.load()
        client_secret = s["client_secret_path"]
        sa_path       = s["service_account_path"]
        folder_id     = s.get("folder_id") or None
        token_path    = s.get("token_path") or str(
            Path(__file__).parent / "credentials" / "token_drive.json"
        )

        # ── 1. Создать таблицу через OAuth (личный аккаунт) ───────────────────
        drive = GoogleDriveOAuthClient(
            client_secret_path=client_secret,
            token_path=token_path,
            default_folder_id=folder_id,
        )
        meta = drive.create_spreadsheet(title, folder_id=folder_id)
        spreadsheet_id = meta["id"]
        link = meta.get(
            "webViewLink",
            f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        )

        # ── 2. Записать данные через Service Account ──────────────────────────
        sheets = GoogleSheetsClient(
            spreadsheet_id=spreadsheet_id,
            credentials_path=sa_path,
        )
        # Имя первого листа зависит от локали аккаунта (Sheet1 / Лист1 / …)
        sheets.default_sheet = sheets.get_sheet_names()[0]

        num_cols  = max(len(headers), 2)
        ts        = datetime.now().strftime("%d.%m.%Y %H:%M")
        # title вида "Клиенты — 03.03.2026 13:30" → берём только имя раздела
        name_part = title.split(" — ")[0] if " — " in title else title

        # ── Структура листа ───────────────────────────────────────────────────
        #  Строка 0  : ОТЧЁТ: <Название>   (слитые ячейки, синий)
        #  Строка 1  : Дата формирования:  (курсив, серый)
        #  Строка 2  : пусто
        #  Строка 3  : АНАЛИЗ ДАННЫХ       (серый фон, жирный)  ← если есть
        #  Строка 4  : пусто               ← если есть аналитика
        #  Строки 5… : данные аналитики    ← если есть
        #  +2 строки пусто
        #  Строка H  : заголовки столбцов  (синий)
        #  Строки D… : данные

        def _pad(row: list) -> list:
            return (row + [""] * num_cols)[:num_cols]

        all_rows: List[List] = []
        all_rows.append(_pad([f"ОТЧЁТ: {name_part}"]))  # 0
        all_rows.append(_pad([f"Дата формирования: {ts}"]))  # 1
        all_rows.append(_pad([]))  # 2

        analysis_hdr_idx: Optional[int] = None
        if analysis:
            analysis_hdr_idx = len(all_rows)            # 3
            all_rows.append(_pad(["АНАЛИЗ ДАННЫХ"]))
            all_rows.append(_pad([]))                   # 4
            for row in analysis:
                all_rows.append(_pad(list(row)))
            all_rows.append(_pad([]))
            all_rows.append(_pad([]))

        headers_row_idx = len(all_rows)
        all_rows.append(headers)
        all_rows.extend(data_rows)

        sheets.write_range("A1", all_rows)

        # ── 3. Форматирование ─────────────────────────────────────────────────
        sheet_id = sheets.get_sheet_id()
        num_data = len(data_rows)
        _BLUE   = {"red": 0.31, "green": 0.42, "blue": 0.93}
        _WHITE  = {"red": 1.00, "green": 1.00, "blue": 1.00}
        _LGRAY  = {"red": 0.86, "green": 0.88, "blue": 0.95}
        _GRAY   = {"red": 0.45, "green": 0.45, "blue": 0.45}

        def _rng(r0, r1, c0=0, c1=None):
            return {"sheetId": sheet_id,
                    "startRowIndex": r0, "endRowIndex": r1,
                    "startColumnIndex": c0, "endColumnIndex": c1 or num_cols}

        batch_requests = [
            # Строка 0: слить ячейки
            {"mergeCells": {"range": _rng(0, 1), "mergeType": "MERGE_ALL"}},
            # Строка 0: синий фон, белый жирный 14pt, по центру
            {"repeatCell": {
                "range": _rng(0, 1),
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _BLUE,
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {"bold": True, "fontSize": 14,
                                   "foregroundColor": _WHITE},
                }},
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,"
                          "verticalAlignment,textFormat)",
            }},
            # Строка 0: высота 36pt
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                          "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 36},
                "fields": "pixelSize",
            }},
            # Строка 1: серый курсив
            {"repeatCell": {
                "range": _rng(1, 2),
                "cell": {"userEnteredFormat": {
                    "textFormat": {"italic": True,
                                   "foregroundColor": _GRAY, "fontSize": 10},
                }},
                "fields": "userEnteredFormat(textFormat)",
            }},
        ]

        # Строка "АНАЛИЗ ДАННЫХ"
        if analysis_hdr_idx is not None:
            batch_requests += [
                {"mergeCells": {"range": _rng(analysis_hdr_idx, analysis_hdr_idx + 1),
                                "mergeType": "MERGE_ALL"}},
                {"repeatCell": {
                    "range": _rng(analysis_hdr_idx, analysis_hdr_idx + 1),
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": _LGRAY,
                        "textFormat": {"bold": True, "fontSize": 11},
                    }},
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }},
            ]

        # Строка заголовков столбцов: синий фон
        batch_requests.append({"repeatCell": {
            "range": _rng(headers_row_idx, headers_row_idx + 1),
            "cell": {"userEnteredFormat": {
                "backgroundColor": _BLUE,
                "horizontalAlignment": "CENTER",
                "textFormat": {"bold": True, "fontSize": 11,
                               "foregroundColor": _WHITE},
            }},
            "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
        }})

        # Чередующиеся полосы строк данных
        if num_data > 0:
            batch_requests.append({"addBanding": {"bandedRange": {
                "range": _rng(headers_row_idx + 1, headers_row_idx + 1 + num_data),
                "rowProperties": {
                    "firstBandColor":  {"red": 0.95, "green": 0.96, "blue": 1.00},
                    "secondBandColor": _WHITE,
                },
            }}})

        # Заморозить всё до строки данных включительно
        batch_requests.append({"updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": headers_row_idx + 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }})

        # Авто-ширина всех столбцов
        batch_requests.append({"autoResizeDimensions": {
            "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": num_cols},
        }})

        sheets.batch_update(batch_requests)
        return link


# ══════════════════════════════════════════════════════════════════════════════
# ДИАЛОГ УСПЕШНОГО ЭКСПОРТА
# ══════════════════════════════════════════════════════════════════════════════

class _ExportDoneDialog(tk.Toplevel):
    """Показывает ссылку на созданную таблицу и кнопку открыть в браузере."""

    def __init__(self, parent: tk.Widget, title: str, link: str) -> None:
        super().__init__(parent)
        self.title("Отчёт создан")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._link = link
        self._build(title, link)
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()  // 2 - self.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{px}+{py}")
        self.bind("<Escape>", lambda e: self.destroy())

    def _build(self, title: str, link: str) -> None:
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)

        # Иконка + заголовок
        ttk.Label(frame, text="✅  Отчёт успешно создан!",
                  font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"«{title}»",
                  foreground="#6B7280").pack(anchor="w", pady=(2, 14))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 14))

        # Ссылка
        ttk.Label(frame, text="Ссылка на таблицу:",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")

        link_frame = ttk.Frame(frame)
        link_frame.pack(fill="x", pady=(4, 0))

        link_var = tk.StringVar(value=link)
        link_entry = ttk.Entry(link_frame, textvariable=link_var,
                               state="readonly", width=54)
        link_entry.pack(side="left", fill="x", expand=True)

        ttk.Button(
            link_frame, text="📋",
            width=3,
            command=lambda: (self.clipboard_clear(), self.clipboard_append(link)),
        ).pack(side="left", padx=(4, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=16)

        # Кнопки
        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        open_btn = tk.Label(
            btn_frame,
            text="  🌐  Открыть в браузере  ",
            bg="#4F6BED", fg="#FFFFFF",
            font=("TkDefaultFont", 11, "bold"),
            cursor="hand2", padx=4, pady=6,
        )
        open_btn.pack(side="left", padx=(0, 8))
        open_btn.bind("<Button-1>", lambda e: (webbrowser.open(self._link), self.destroy()))
        open_btn.bind("<Enter>",    lambda e: open_btn.config(bg="#3B55D4"))
        open_btn.bind("<Leave>",    lambda e: open_btn.config(bg="#4F6BED"))

        ttk.Button(btn_frame, text="  Закрыть  ",
                   command=self.destroy).pack(side="left")


# ══════════════════════════════════════════════════════════════════════════════
# УНИВЕРСАЛЬНЫЙ ДИАЛОГ ФОРМЫ
# ══════════════════════════════════════════════════════════════════════════════

class FormDialog(tk.Toplevel):
    """
    Модальный диалог для создания / редактирования записи.

    fields: список кортежей (key, label, widget_type, options)
        widget_type: "entry" | "text" | "combo" | "spinbox"
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        fields: List[tuple],
        initial: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: Optional[Dict[str, Any]] = None
        self._fields = fields
        self._widgets: Dict[str, Any] = {}
        self._build(initial or {})
        self.transient(parent)
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()  // 2 - self.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{px}+{py}")
        self.wait_window()

    def _build(self, initial: Dict[str, Any]) -> None:
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        for row_i, (key, label, wtype, opts) in enumerate(self._fields):
            ttk.Label(frame, text=label, width=18, anchor="e").grid(
                row=row_i, column=0, padx=(0, 8), pady=5, sticky="ne"
            )
            val = initial.get(key)
            val_str = str(val) if val is not None else ""

            if wtype == "combo":
                var = tk.StringVar(value=val_str or (opts[0] if opts else ""))
                w = ttk.Combobox(frame, textvariable=var, values=opts,
                                 state="readonly", width=30)
                w.grid(row=row_i, column=1, sticky="w", pady=5)
                self._widgets[key] = var

            elif wtype == "text":
                w = tk.Text(frame, width=34, height=4,
                            relief="solid", bd=1, font=("TkDefaultFont", 10))
                if val_str:
                    w.insert("1.0", val_str)
                w.grid(row=row_i, column=1, sticky="w", pady=5)
                self._widgets[key] = w

            elif wtype == "spinbox":
                var = tk.StringVar(value=val_str or "0")
                w = ttk.Spinbox(frame, from_=opts[0], to=opts[1],
                                textvariable=var, width=31)
                w.grid(row=row_i, column=1, sticky="w", pady=5)
                self._widgets[key] = var

            else:
                var = tk.StringVar(value=val_str)
                w = ttk.Entry(frame, textvariable=var, width=34)
                w.grid(row=row_i, column=1, sticky="w", pady=5)
                self._widgets[key] = var
                if row_i == 0:
                    w.focus_set()

        sep = ttk.Separator(frame, orient="horizontal")
        sep.grid(row=len(self._fields), column=0, columnspan=2,
                 sticky="ew", pady=(12, 8))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(self._fields) + 1, column=0, columnspan=2)
        ttk.Button(btn_frame, text="  Сохранить  ",
                   command=self._on_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="  Отмена  ",
                   command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._on_save())
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_save(self) -> None:
        result: Dict[str, Any] = {}
        for key, _, wtype, _ in self._fields:
            w = self._widgets[key]
            if wtype == "text":
                val = w.get("1.0", "end-1c").strip()
            else:
                val = w.get().strip()
            if val:
                result[key] = val
        self.result = result
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# БАЗОВЫЙ КЛАСС ВКЛАДКИ С ТАБЛИЦЕЙ
# ══════════════════════════════════════════════════════════════════════════════

class BaseTab(ttk.Frame):
    COLS:    tuple = ()
    HEADERS: tuple = ()
    WIDTHS:  tuple = ()

    # Колонка чекбоксов — добавляется автоматически перед COLS
    _COL_SEL = "sel"
    _CHK_ON  = "☑"
    _CHK_OFF = "☐"

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self._sort_col:     str      = ""
        self._sort_reverse: bool     = False
        self._checked:      set[str] = set()   # iid строк с чекбоксом ☑
        self._build_toolbar()
        self._build_tree()
        self.after(100, self.refresh)

    # ── Переопределяемые в подклассах ─────────────────────────────────────────

    def _extra_toolbar(self, bar: ttk.Frame) -> None:
        pass

    def _action_buttons(self, bar: ttk.Frame) -> None:
        pass

    def refresh(self) -> None:
        pass

    def _create_record(self) -> None: ...
    def _edit_record(self)   -> None: ...
    def _delete_record(self) -> None: ...

    def _get_export_data(self) -> tuple:
        """Переопределяется в каждой вкладке.
        По умолчанию возвращает отмеченные строки (или все, если ничего не отмечено).
        """
        rows = self._get_checked_rows()
        ts   = datetime.now().strftime("%d.%m.%Y %H:%M")
        return f"Отчёт — {ts}", list(self.HEADERS), rows, []

    # ── Построение UI ─────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        # ── Строка 1: поиск + чекбоксы + фильтры ─────────────────────────────
        row1 = ttk.Frame(self)
        row1.pack(fill="x", padx=10, pady=(8, 2))

        ttk.Label(row1, text="Поиск:").pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        ttk.Entry(row1, textvariable=self._search_var, width=22).pack(
            side="left", padx=(4, 6)
        )

        ttk.Separator(row1, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(row1, text="☑ Все",
                   command=self._select_all).pack(side="left", padx=(0, 2))
        ttk.Button(row1, text="☐ Снять",
                   command=self._deselect_all).pack(side="left", padx=(0, 4))
        self._check_lbl = tk.Label(row1, text="Выбрано: 0",
                                   fg="#6B7280", font=("TkDefaultFont", 9))
        self._check_lbl.pack(side="left", padx=(0, 6))
        ttk.Separator(row1, orient="vertical").pack(side="left", fill="y", padx=6)

        self._extra_toolbar(row1)

        # ── Строка 2: кнопки действий ─────────────────────────────────────────
        row2 = ttk.Frame(self)
        row2.pack(fill="x", padx=10, pady=(0, 4))

        ttk.Button(row2, text="＋ Добавить",
                   command=self._create_record).pack(side="left", padx=(0, 2))
        ttk.Button(row2, text="✎ Редактировать",
                   command=self._edit_record).pack(side="left", padx=2)
        ttk.Button(row2, text="✕ Удалить",
                   command=self._delete_record).pack(side="left", padx=2)
        self._action_buttons(row2)

        ttk.Separator(row2, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(row2, text="📊 Выгрузить в Google",
                   command=self._export_report).pack(side="left", padx=2)

        ttk.Button(row2, text="⟳ Обновить",
                   command=self.refresh).pack(side="right", padx=2)

    def _build_tree(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        all_cols = (self._COL_SEL,) + self.COLS
        self._tree = ttk.Treeview(
            frame, columns=all_cols, show="headings", selectmode="browse"
        )

        # Колонка чекбокса
        self._tree.heading(self._COL_SEL, text="☑")
        self._tree.column(self._COL_SEL, width=32, minwidth=32,
                          anchor="center", stretch=False)

        # Остальные колонки
        for col, hdr, w in zip(self.COLS, self.HEADERS, self.WIDTHS):
            self._tree.heading(col, text=hdr,
                               command=lambda c=col: self._toggle_sort(c))
            self._tree.column(col, width=w, minwidth=30, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(fill="both", expand=True)

        self._tree.bind("<Button-1>",  self._on_tree_click)
        self._tree.bind("<Double-1>",  self._on_tree_double)
        self._tree.tag_configure("done",     foreground="#94A3B8")
        self._tree.tag_configure("archived", foreground="#94A3B8")
        self._tree.tag_configure("won",      foreground="#22C55E")
        self._tree.tag_configure("lost",     foreground="#EF4444")

    def _populate(self, rows: List[Dict], tag_col: str = "") -> None:
        self._checked.clear()
        self._tree.delete(*self._tree.get_children())
        for r in rows:
            data_vals = tuple(
                (str(r.get(c) or "") if c not in ("created_at", "updated_at", "due_date")
                 else _fmt_date(r.get(c) or ""))
                for c in self.COLS
            )
            vals = (self._CHK_OFF,) + data_vals
            tag  = r.get(tag_col, "") if tag_col else ""
            self._tree.insert("", "end", iid=str(r["id"]), values=vals,
                              tags=(tag,) if tag else ())
        self._update_check_label()

    def _selected_id(self, warn: str = "Сначала выберите запись.") -> Optional[int]:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Выбор", warn)
            return None
        return int(sel[0])

    # ── Чекбоксы ──────────────────────────────────────────────────────────────

    def _on_tree_click(self, event: tk.Event) -> None:
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self._tree.identify_column(event.x)
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        if col == "#1":                 # колонка ☑
            self._toggle_check(iid)
            return                      # не передавать событие дальше

    def _on_tree_double(self, event: tk.Event) -> None:
        col = self._tree.identify_column(event.x)
        if col != "#1":
            self._edit_record()

    def _toggle_check(self, iid: str) -> None:
        if iid in self._checked:
            self._checked.discard(iid)
            self._tree.set(iid, self._COL_SEL, self._CHK_OFF)
        else:
            self._checked.add(iid)
            self._tree.set(iid, self._COL_SEL, self._CHK_ON)
        self._update_check_label()

    def _select_all(self) -> None:
        for iid in self._tree.get_children():
            self._checked.add(iid)
            self._tree.set(iid, self._COL_SEL, self._CHK_ON)
        self._update_check_label()

    def _deselect_all(self) -> None:
        for iid in self._tree.get_children():
            self._tree.set(iid, self._COL_SEL, self._CHK_OFF)
        self._checked.clear()
        self._update_check_label()

    def _update_check_label(self) -> None:
        total   = len(self._tree.get_children())
        checked = len(self._checked)
        if checked:
            self._check_lbl.config(
                text=f"Выбрано: {checked} / {total}",
                fg="#4F6BED",
                font=("TkDefaultFont", 9, "bold"),
            )
        else:
            self._check_lbl.config(
                text=f"Выбрано: 0 / {total}",
                fg="#6B7280",
                font=("TkDefaultFont", 9),
            )

    def _get_checked_rows(self) -> List[List]:
        """Возвращает строки данных (без колонки ☑).
        Если ничего не отмечено — возвращает все строки.
        """
        items = list(self._checked) if self._checked else list(self._tree.get_children())
        return [list(self._tree.item(iid, "values"))[1:] for iid in items]

    def _checked_ids(self) -> List[int]:
        """Возвращает список ID отмеченных чекбоксами строк.
        Если ни одна не отмечена — пробует взять нативно выбранную строку.
        Возвращает [] если ничего не выбрано.
        """
        if self._checked:
            return [int(iid) for iid in self._checked]
        sel = self._tree.selection()
        return [int(sel[0])] if sel else []

    def _on_search(self) -> None:
        self.refresh()

    def _toggle_sort(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        data = [(self._tree.set(iid, col), iid) for iid in self._tree.get_children()]
        try:
            data.sort(
                key=lambda x: float(x[0]) if x[0].replace(".", "").isdigit() else x[0].lower(),
                reverse=self._sort_reverse,
            )
        except Exception:
            data.sort(reverse=self._sort_reverse)
        for idx, (_, iid) in enumerate(data):
            self._tree.move(iid, "", idx)

    # ── Экспорт ───────────────────────────────────────────────────────────────

    def _export_report(self) -> None:
        if not GoogleSettings.is_configured():
            if messagebox.askyesno(
                "Настройки Google",
                "Настройки Google не заданы.\nОткрыть окно настроек?",
            ):
                GoogleSettingsDialog(self)
            return

        title, headers, data_rows, analysis = self._get_export_data()

        if not data_rows:
            messagebox.showinfo("Нет данных", "Таблица пуста — нечего выгружать.")
            return

        self._set_status(f"⏳ Экспорт «{title}»...")

        def _run() -> None:
            try:
                link = ExportService().export(title, headers, data_rows, analysis)
                self.after(0, lambda: self._on_export_done(link, title))
            except Exception as e:
                self.after(0, lambda err=e: _err(err))
                self.after(0, lambda: self._set_status("Ошибка экспорта"))

        threading.Thread(target=_run, daemon=True).start()

    def _on_export_done(self, link: str, title: str) -> None:
        self._set_status(f"✓ Выгружено: {title}")
        _ExportDoneDialog(self.winfo_toplevel(), title, link)

    def _set_status(self, msg: str) -> None:
        top = self.winfo_toplevel()
        if hasattr(top, "_status_var"):
            top._status_var.set(msg)


# ══════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА КЛИЕНТЫ
# ══════════════════════════════════════════════════════════════════════════════

class ClientsTab(BaseTab):
    COLS    = ("id", "name",  "email",  "phone",   "company",  "status", "created_at")
    HEADERS = ("ID", "Имя",   "E-mail", "Телефон", "Компания", "Статус", "Создан")
    WIDTHS  = ( 45,   180,     180,      130,        150,        90,       140)

    def _extra_toolbar(self, bar: ttk.Frame) -> None:
        ttk.Label(bar, text="Статус:").pack(side="left")
        self._status_var = tk.StringVar(value="Все")
        ttk.Combobox(bar, textvariable=self._status_var,
                     values=["Все"] + CLIENT_STATUSES,
                     state="readonly", width=11).pack(side="left", padx=(4, 0))
        self._status_var.trace_add("write", lambda *_: self.refresh())

    def _action_buttons(self, bar: ttk.Frame) -> None:
        ttk.Button(bar, text="📦 Архив",
                   command=self._archive).pack(side="left", padx=2)

    def refresh(self) -> None:
        sv = getattr(self, "_status_var", None)
        status = None if sv is None or sv.get() == "Все" else sv.get()
        try:
            self._populate(api.get_clients(status=status), tag_col="status")
        except Exception as e:
            _err(e)

    def _on_search(self) -> None:
        q = self._search_var.get().strip()
        if not q:
            self.refresh(); return
        try:
            self._populate(api.search_clients(q), tag_col="status")
        except Exception as e:
            _err(e)

    def _fields(self) -> List[tuple]:
        return [
            ("name",    "Имя *",    "entry", []),
            ("email",   "E-mail",   "entry", []),
            ("phone",   "Телефон",  "entry", []),
            ("company", "Компания", "entry", []),
            ("notes",   "Заметки",  "text",  []),
            ("status",  "Статус",   "combo", CLIENT_STATUSES),
        ]

    def _create_record(self) -> None:
        dlg = FormDialog(self, "Новый клиент", self._fields())
        if dlg.result:
            try:
                api.create_client(dlg.result); self.refresh()
            except Exception as e:
                _err(e)

    def _edit_record(self) -> None:
        cid = self._selected_id("Выберите клиента для редактирования.")
        if cid is None: return
        try:
            client = api.get_client(cid)
        except Exception as e:
            _err(e); return
        dlg = FormDialog(self, "Редактировать клиента", self._fields(), initial=client)
        if dlg.result:
            try:
                api.update_client(cid, dlg.result); self.refresh()
            except Exception as e:
                _err(e)

    def _archive(self) -> None:
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Выбор", "Выберите клиента для архивации.")
            return
        n = len(ids)
        label = f"{n} клиентов" if n > 1 else "клиента"
        if messagebox.askyesno("Архивация", f"Архивировать {label}?"):
            for cid in ids:
                try:
                    api.archive_client(cid)
                except Exception as e:
                    _err(e); return
            self._deselect_all()
            self.refresh()

    def _delete_record(self) -> None:
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Выбор", "Выберите клиента для удаления.")
            return
        n = len(ids)
        label = f"{n} клиентов" if n > 1 else "клиента"
        if messagebox.askyesno("Удаление", f"Удалить {label} безвозвратно?\n"
                               "(Связанные сделки и задачи сохранятся.)"):
            for cid in ids:
                try:
                    api.delete_client(cid)
                except Exception as e:
                    _err(e); return
            self._deselect_all()
            self.refresh()

    def _get_export_data(self) -> tuple:
        rows = self._get_checked_rows()
        status_counts: Dict[str, int] = {}
        for r in rows:
            s = r[5] if len(r) > 5 else "?"
            status_counts[s] = status_counts.get(s, 0) + 1

        sel_label = f"{len(rows)} из {len(self._tree.get_children())}" \
                    if self._checked else "все"
        analysis: List[List] = [["Клиентов в отчёте", f"{len(rows)} ({sel_label})"]]
        for status, cnt in sorted(status_counts.items()):
            analysis.append([f"  {status}", cnt])

        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        return f"Клиенты — {ts}", list(self.HEADERS), rows, analysis


# ══════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА СДЕЛКИ
# ══════════════════════════════════════════════════════════════════════════════

class DealsTab(BaseTab):
    COLS    = ("id", "title",    "client_id", "status",  "amount", "currency", "created_at")
    HEADERS = ("ID", "Название", "Клиент ID", "Статус",  "Сумма",  "Валюта",   "Создана")
    WIDTHS  = ( 45,   220,        90,           110,       100,      70,         140)

    def _extra_toolbar(self, bar: ttk.Frame) -> None:
        ttk.Label(bar, text="Статус:").pack(side="left")
        self._status_var = tk.StringVar(value="Все")
        ttk.Combobox(bar, textvariable=self._status_var,
                     values=["Все"] + DEAL_STATUSES,
                     state="readonly", width=12).pack(side="left", padx=(4, 0))
        self._status_var.trace_add("write", lambda *_: self.refresh())

    def refresh(self) -> None:
        sv = getattr(self, "_status_var", None)
        status = None if sv is None or sv.get() == "Все" else sv.get()
        try:
            self._populate(api.get_deals(status=status), tag_col="status")
        except Exception as e:
            _err(e)

    def _on_search(self) -> None:
        q = self._search_var.get().strip()
        if not q:
            self.refresh(); return
        try:
            self._populate(api.search_deals(q), tag_col="status")
        except Exception as e:
            _err(e)

    def _client_options(self) -> List[str]:
        try:
            return [f"{c['id']} — {c['name']}" for c in api.get_clients(limit=200)]
        except Exception:
            return []

    def _fields(self) -> List[tuple]:
        return [
            ("title",       "Название *",  "entry",   []),
            ("description", "Описание",    "text",    []),
            ("_client",     "Клиент",      "combo",   ["(без клиента)"] + self._client_options()),
            ("status",      "Статус",      "combo",   DEAL_STATUSES),
            ("amount",      "Сумма",       "spinbox", (0, 99_999_999)),
            ("currency",    "Валюта",      "combo",   CURRENCIES),
        ]

    def _parse_client(self, val: str) -> Optional[int]:
        if not val or val.startswith("("):
            return None
        try:
            return int(val.split("—")[0].strip())
        except Exception:
            return None

    def _initial_with_client(self, deal: Dict) -> Dict:
        d = dict(deal)
        cid = d.get("client_id")
        d["_client"] = "(без клиента)"
        if cid:
            try:
                c = api.get_client(cid)
                d["_client"] = f"{cid} — {c['name']}"
            except Exception:
                d["_client"] = str(cid)
        return d

    def _build_body(self, result: Dict) -> Dict:
        body = {k: v for k, v in result.items() if k != "_client"}
        body["client_id"] = self._parse_client(result.get("_client", ""))
        if body.get("amount"):
            try:
                body["amount"] = float(body["amount"])
            except ValueError:
                body.pop("amount", None)
        return body

    def _create_record(self) -> None:
        dlg = FormDialog(self, "Новая сделка", self._fields())
        if dlg.result:
            try:
                api.create_deal(self._build_body(dlg.result)); self.refresh()
            except Exception as e:
                _err(e)

    def _edit_record(self) -> None:
        did = self._selected_id("Выберите сделку для редактирования.")
        if did is None: return
        try:
            deal = api.get_deal(did)
        except Exception as e:
            _err(e); return
        dlg = FormDialog(self, "Редактировать сделку", self._fields(),
                         initial=self._initial_with_client(deal))
        if dlg.result:
            try:
                api.update_deal(did, self._build_body(dlg.result)); self.refresh()
            except Exception as e:
                _err(e)

    def _delete_record(self) -> None:
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Выбор", "Выберите сделку для удаления.")
            return
        n = len(ids)
        label = f"{n} сделок" if n > 1 else "сделку"
        if messagebox.askyesno("Удаление", f"Удалить {label} безвозвратно?"):
            for did in ids:
                try:
                    api.delete_deal(did)
                except Exception as e:
                    _err(e); return
            self._deselect_all()
            self.refresh()

    def _get_export_data(self) -> tuple:
        rows = self._get_checked_rows()

        status_counts: Dict[str, int] = {}
        total_amount = 0.0
        won_amount   = 0.0
        for r in rows:
            st = r[3] if len(r) > 3 else "?"
            status_counts[st] = status_counts.get(st, 0) + 1
            try:
                amt = float(r[4]) if len(r) > 4 and r[4] else 0.0
                total_amount += amt
                if st == "won":
                    won_amount += amt
            except ValueError:
                pass

        sel_label = f"{len(rows)} из {len(self._tree.get_children())}" \
                    if self._checked else "все"
        analysis: List[List] = [
            ["Сделок в отчёте",     f"{len(rows)} ({sel_label})"],
            ["Общая сумма",         f"{total_amount:,.0f}".replace(",", " ")],
            ["Сумма выигранных",    f"{won_amount:,.0f}".replace(",", " ")],
        ]
        for status, cnt in sorted(status_counts.items()):
            analysis.append([f"  {status}", cnt])

        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        return f"Сделки — {ts}", list(self.HEADERS), rows, analysis


# ══════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА ЗАДАЧИ
# ══════════════════════════════════════════════════════════════════════════════

class TasksTab(BaseTab):
    COLS    = ("id", "title",   "client_id", "deal_id",   "status",  "due_date", "created_at")
    HEADERS = ("ID", "Задача",  "Клиент ID", "Сделка ID", "Статус",  "Срок",     "Создана")
    WIDTHS  = ( 45,   220,       90,           90,          110,       140,        140)

    def _extra_toolbar(self, bar: ttk.Frame) -> None:
        ttk.Label(bar, text="Статус:").pack(side="left")
        self._status_var = tk.StringVar(value="Активные")
        ttk.Combobox(bar, textvariable=self._status_var,
                     values=["Все", "Активные"] + TASK_STATUSES,
                     state="readonly", width=12).pack(side="left", padx=(4, 0))
        self._status_var.trace_add("write", lambda *_: self.refresh())

    def _action_buttons(self, bar: ttk.Frame) -> None:
        ttk.Button(bar, text="✔ Выполнено",
                   command=self._complete).pack(side="left", padx=2)
        ttk.Button(bar, text="↺ Открыть снова",
                   command=self._reopen).pack(side="left", padx=2)

    def refresh(self) -> None:
        sv = getattr(self, "_status_var", None)
        raw = sv.get() if sv else "Все"
        status = "pending" if raw == "Активные" else (None if raw == "Все" else raw)
        q = getattr(self, "_search_var", None)
        search = q.get().strip().lower() if q else ""
        try:
            rows = api.get_tasks(status=status)
            if search:
                rows = [r for r in rows
                        if search in r.get("title", "").lower()
                        or search in (r.get("description") or "").lower()]
            self._populate(rows, tag_col="status")
        except Exception as e:
            _err(e)

    def _on_search(self) -> None:
        self.refresh()

    def _client_options(self) -> List[str]:
        try:
            return [f"{c['id']} — {c['name']}" for c in api.get_clients(limit=200)]
        except Exception:
            return []

    def _deal_options(self) -> List[str]:
        try:
            return [f"{d['id']} — {d['title']}" for d in api.get_deals(limit=200)]
        except Exception:
            return []

    def _parse_ref(self, val: str) -> Optional[int]:
        if not val or val.startswith("("):
            return None
        try:
            return int(val.split("—")[0].strip())
        except Exception:
            return None

    def _fields(self) -> List[tuple]:
        return [
            ("title",       "Задача *",   "entry", []),
            ("description", "Описание",   "text",  []),
            ("_client",     "Клиент",     "combo", ["(без клиента)"] + self._client_options()),
            ("_deal",       "Сделка",     "combo", ["(без сделки)"]  + self._deal_options()),
            ("status",      "Статус",     "combo", TASK_STATUSES),
            ("due_date",    "Срок (ISO)", "entry", []),
        ]

    def _initial_with_refs(self, task: Dict) -> Dict:
        d = dict(task)
        cid, did = d.get("client_id"), d.get("deal_id")
        d["_client"] = "(без клиента)"
        d["_deal"]   = "(без сделки)"
        if cid:
            try:
                c = api.get_client(cid)
                d["_client"] = f"{cid} — {c['name']}"
            except Exception:
                d["_client"] = str(cid)
        if did:
            try:
                de = api.get_deal(did)
                d["_deal"] = f"{did} — {de['title']}"
            except Exception:
                d["_deal"] = str(did)
        return d

    def _build_body(self, result: Dict) -> Dict:
        body = {k: v for k, v in result.items() if k not in ("_client", "_deal")}
        body["client_id"] = self._parse_ref(result.get("_client", ""))
        body["deal_id"]   = self._parse_ref(result.get("_deal", ""))
        return body

    def _create_record(self) -> None:
        dlg = FormDialog(self, "Новая задача", self._fields())
        if dlg.result:
            try:
                api.create_task(self._build_body(dlg.result)); self.refresh()
            except Exception as e:
                _err(e)

    def _edit_record(self) -> None:
        tid = self._selected_id("Выберите задачу для редактирования.")
        if tid is None: return
        try:
            all_tasks = api.get_tasks(limit=500)
            task_data = next((t for t in all_tasks if t["id"] == tid), {})
        except Exception as e:
            _err(e); return
        dlg = FormDialog(self, "Редактировать задачу", self._fields(),
                         initial=self._initial_with_refs(task_data))
        if dlg.result:
            try:
                api.update_task(tid, self._build_body(dlg.result)); self.refresh()
            except Exception as e:
                _err(e)

    def _complete(self) -> None:
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Выбор", "Выберите задачу.")
            return
        for tid in ids:
            try:
                api.complete_task(tid)
            except Exception as e:
                _err(e); return
        self._deselect_all()
        self.refresh()

    def _reopen(self) -> None:
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Выбор", "Выберите задачу.")
            return
        for tid in ids:
            try:
                api.reopen_task(tid)
            except Exception as e:
                _err(e); return
        self._deselect_all()
        self.refresh()

    def _delete_record(self) -> None:
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Выбор", "Выберите задачу для удаления.")
            return
        n = len(ids)
        label = f"{n} задач" if n > 1 else "задачу"
        if messagebox.askyesno("Удаление", f"Удалить {label}?"):
            for tid in ids:
                try:
                    api.delete_task(tid)
                except Exception as e:
                    _err(e); return
            self._deselect_all()
            self.refresh()

    def _get_export_data(self) -> tuple:
        rows = self._get_checked_rows()

        status_counts: Dict[str, int] = {}
        for r in rows:
            st = r[4] if len(r) > 4 else "?"
            status_counts[st] = status_counts.get(st, 0) + 1

        sel_label = f"{len(rows)} из {len(self._tree.get_children())}" \
                    if self._checked else "все"
        analysis: List[List] = [["Задач в отчёте", f"{len(rows)} ({sel_label})"]]
        for status, cnt in sorted(status_counts.items()):
            analysis.append([f"  {status}", cnt])

        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        return f"Задачи — {ts}", list(self.HEADERS), rows, analysis


# ══════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА ДАШБОРД
# ══════════════════════════════════════════════════════════════════════════════

class DashboardTab(ttk.Frame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self._build()
        self.after(200, self.refresh)

    def _build(self) -> None:
        ttk.Label(self, text="Сводка", font=("TkDefaultFont", 14, "bold")).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        ttk.Button(self, text="⟳ Обновить", command=self.refresh).pack(
            anchor="w", padx=20, pady=(0, 12)
        )
        self._cards_frame = ttk.Frame(self)
        self._cards_frame.pack(fill="both", expand=True, padx=20)

    def refresh(self) -> None:
        for w in self._cards_frame.winfo_children():
            w.destroy()
        try:
            data = api.get_dashboard()
        except Exception as e:
            ttk.Label(self._cards_frame, text=f"Сервер недоступен: {e}",
                      foreground="red").grid(row=0, column=0, pady=20)
            return

        clients = data.get("clients", {})
        deals   = data.get("deals",   {})
        tasks   = data.get("tasks",   {})

        sections = [
            ("👥 Клиенты", [
                ("Всего",      clients.get("total", 0)),
                ("Лиды",       clients.get("by_status", {}).get("lead",     0)),
                ("Активные",   clients.get("by_status", {}).get("active",   0)),
                ("Неактивные", clients.get("by_status", {}).get("inactive", 0)),
                ("Архив",      clients.get("by_status", {}).get("archived", 0)),
            ]),
            ("💼 Сделки", [
                ("Всего",        deals.get("total", 0)),
                ("Новые",        deals.get("by_status", {}).get("new",         0)),
                ("Переговоры",   deals.get("by_status", {}).get("negotiation", 0)),
                ("Выиграно",     deals.get("by_status", {}).get("won",         0)),
                ("Проиграно",    deals.get("by_status", {}).get("lost",        0)),
                ("Пауза",        deals.get("by_status", {}).get("paused",      0)),
                ("Сумма выигр.", f"{deals.get('won_amount', 0):,.0f} ₽"),
            ]),
            ("✅ Задачи", [
                ("Активных",     tasks.get("pending", 0)),
                ("Просроченных", tasks.get("overdue", 0)),
            ]),
        ]

        for col, (section_title, rows) in enumerate(sections):
            card = ttk.LabelFrame(self._cards_frame, text=section_title, padding=16)
            card.grid(row=0, column=col, padx=12, pady=8, sticky="n")
            for r, (label, value) in enumerate(rows):
                ttk.Label(card, text=label, width=16, anchor="w",
                          foreground="#6B7280").grid(row=r, column=0, sticky="w", pady=3)
                ttk.Label(card, text=str(value), width=14, anchor="e",
                          font=("TkDefaultFont", 11, "bold")).grid(
                    row=r, column=1, sticky="e", pady=3
                )


# ══════════════════════════════════════════════════════════════════════════════
# ГЛАВНОЕ ОКНО
# ══════════════════════════════════════════════════════════════════════════════

class CRMApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Mini CRM")
        self.geometry("1140x700")
        self.minsize(900, 550)
        self._apply_style()
        self._build_ui()
        self._check_server()

    def _apply_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TNotebook",     background="#F0F2F5")
        style.configure("TNotebook.Tab", padding=(14, 6), font=("TkDefaultFont", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", "#FFFFFF"), ("!selected", "#E2E8F0")],
                  foreground=[("selected", "#1C2333"), ("!selected", "#6B7280")])

        style.configure("Treeview",
                        rowheight=24, font=("TkDefaultFont", 10),
                        background="#FFFFFF", fieldbackground="#FFFFFF")
        style.configure("Treeview.Heading",
                        font=("TkDefaultFont", 10, "bold"),
                        background="#F8FAFC", relief="flat")
        style.map("Treeview",
                  background=[("selected", "#DBEAFE")],
                  foreground=[("selected", "#1E40AF")])

        style.configure("TButton",    padding=(8, 4), relief="flat")
        style.configure("TEntry",     padding=(4, 4))
        style.configure("TCombobox",  padding=(4, 4))
        style.configure("TLabelFrame", background="#F0F2F5")

    def _build_ui(self) -> None:
        # ── Заголовок ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg="#1C2333", height=46)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="  Mini CRM",
                 bg="#1C2333", fg="#FFFFFF",
                 font=("TkDefaultFont", 13, "bold")).pack(side="left", padx=10, pady=8)

        # Кнопка настроек Google
        _google_btn = tk.Label(
            header,
            text="  ⚙ Google  ",
            bg="#4F6BED", fg="#FFFFFF",
            font=("TkDefaultFont", 10, "bold"),
            cursor="hand2",
            padx=4, pady=4,
        )
        _google_btn.pack(side="right", padx=12, pady=8)
        _google_btn.bind("<Button-1>", lambda e: self._open_google_settings())
        _google_btn.bind("<Enter>",    lambda e: _google_btn.config(bg="#3B55D4"))
        _google_btn.bind("<Leave>",    lambda e: _google_btn.config(bg="#4F6BED"))

        self._server_lbl = tk.Label(
            header, text="● Подключение...",
            bg="#1C2333", fg="#F59E0B",
            font=("TkDefaultFont", 10),
        )
        self._server_lbl.pack(side="right", padx=16)

        # ── Вкладки ────────────────────────────────────────────────────────────
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        self._dashboard_tab = DashboardTab(nb)
        self._clients_tab   = ClientsTab(nb)
        self._deals_tab     = DealsTab(nb)
        self._tasks_tab     = TasksTab(nb)

        nb.add(self._dashboard_tab, text="  Дашборд  ")
        nb.add(self._clients_tab,   text="  Клиенты  ")
        nb.add(self._deals_tab,     text="  Сделки   ")
        nb.add(self._tasks_tab,     text="  Задачи   ")

        # ── Статусная строка ───────────────────────────────────────────────────
        status_bar = tk.Frame(self, bg="#E2E8F0", height=22)
        status_bar.pack(fill="x", side="bottom")
        self._status_var = tk.StringVar(value=f"Сервер: {BASE_URL}")
        tk.Label(status_bar, textvariable=self._status_var,
                 bg="#E2E8F0", fg="#6B7280",
                 font=("TkDefaultFont", 9)).pack(side="left", padx=8)

    def _open_google_settings(self) -> None:
        GoogleSettingsDialog(self)

    def _check_server(self) -> None:
        def _ping() -> None:
            try:
                api.get_dashboard()
                self.after(0, self._on_connected)
            except Exception as e:
                self.after(0, lambda: self._on_disconnected(str(e)))

        threading.Thread(target=_ping, daemon=True).start()

    def _on_connected(self) -> None:
        self._server_lbl.config(text="● Подключено", fg="#22C55E")
        self._status_var.set(f"Сервер: {BASE_URL}  ✓")

    def _on_disconnected(self, reason: str) -> None:
        self._server_lbl.config(text="● Нет соединения", fg="#EF4444")
        self._status_var.set(f"Сервер недоступен: {reason}")
        messagebox.showwarning(
            "Сервер недоступен",
            f"Не удалось подключиться к {BASE_URL}\n\n"
            f"Запустите сервер командой:\n    docker compose up\n\n"
            f"Ошибка: {reason}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = CRMApp()
    app.mainloop()
