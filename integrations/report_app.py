"""
Генератор отчётов в Google Таблицы.

Использование: python report_app.py
"""

from __future__ import annotations

import os
import random
import threading
import tkinter as tk
from tkinter import font, ttk
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from google_sheets_client import GoogleSheetsClient

load_dotenv()

# ---------------------------------------------------------------------------
# Конфигурация (из .env или значения по умолчанию)
# ---------------------------------------------------------------------------

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "excel-factory-488906-cd544edd406e.json")
DEFAULT_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "1sRKylkjH-PSqpvnVTOsCvs3l4AJtw3U7XuarvOFiiuQ")

REPORT_TYPES = [
    "Продажи",
    "Производство",
    "Персонал",
]

DEPARTMENTS = [
    "Отдел продаж",
    "Производственный отдел",
    "HR-отдел",
    "Бухгалтерия",
    "IT-отдел",
]

NAMES = [
    "Иванов И.И.", "Петров П.П.", "Сидоров С.С.", "Козлов К.К.", "Новиков Н.Н.",
    "Морозов М.М.", "Волков В.В.", "Соколов С.С.", "Лебедев Л.Л.", "Кузнецов К.К.",
    "Попов П.П.", "Васильев В.В.", "Смирнов С.С.", "Михайлов М.М.", "Федоров Ф.Ф.",
]


def rgb(r: float, g: float, b: float) -> dict:
    """RGB 0–255 → формат API (0–1)."""
    return {"red": r / 255, "green": g / 255, "blue": b / 255}


# ---------------------------------------------------------------------------
# Генераторы случайных данных
# ---------------------------------------------------------------------------

def gen_sales_report(rows: int, start: date, end: date) -> tuple[list[str], list[list[Any]]]:
    headers = ["№", "Сотрудник", "Сделок", "Выручка, ₽", "Средний чек", "Конверсия, %"]
    data = []
    for i in range(1, rows + 1):
        deals = random.randint(5, 50)
        rev = random.randint(100_000, 2_000_000)
        conv = round(random.uniform(12, 45), 1)
        data.append([
            i,
            random.choice(NAMES),
            deals,
            f"{rev:,}".replace(",", " "),
            f"{rev // deals:,}".replace(",", " "),
            conv,
        ])
    return headers, data


def gen_production_report(rows: int, start: date, end: date) -> tuple[list[str], list[list[Any]]]:
    headers = ["№", "Участок", "Выпуск, шт", "Брак, %", "Простой, ч", "Эффективность, %"]
    areas = ["Цех А", "Цех Б", "Участок 1", "Участок 2", "Сборка"]
    data = []
    for i in range(1, rows + 1):
        data.append([
            i,
            random.choice(areas),
            random.randint(500, 2500),
            round(random.uniform(0.5, 4.0), 1),
            random.randint(0, 12),
            round(random.uniform(75, 98), 1),
        ])
    return headers, data


def gen_hr_report(rows: int, start: date, end: date) -> tuple[list[str], list[list[Any]]]:
    headers = ["№", "Сотрудник", "Отработано дней", "Больничные", "Переработки, ч", "Оценка"]
    data = []
    days_range = (end - start).days + 1
    for i in range(1, rows + 1):
        worked = random.randint(max(1, days_range - 5), days_range)
        sick = random.randint(0, 3)
        overtime = random.randint(0, 20)
        grade = random.choice(["Отлично", "Хорошо", "Удовл.", "Требует внимания"])
        data.append([i, random.choice(NAMES), worked, sick, overtime, grade])
    return headers, data


REPORT_GENERATORS = {
    "Продажи": gen_sales_report,
    "Производство": gen_production_report,
    "Персонал": gen_hr_report,
}


# ---------------------------------------------------------------------------
# Построитель отчёта
# ---------------------------------------------------------------------------

class ReportBuilder:
    """Создаёт отформатированный отчёт в Google Таблице."""

    COLORS = {
        "title_bg": rgb(31, 78, 120),
        "title_fg": rgb(255, 255, 255),
        "info_bg": rgb(240, 240, 240),
        "header_bg": rgb(68, 114, 196),
        "header_fg": rgb(255, 255, 255),
        "row_alt": rgb(217, 225, 242),
        "total_bg": rgb(182, 215, 168),
        "border": rgb(180, 180, 180),
    }

    def __init__(self, client: GoogleSheetsClient, sheet: str):
        self.client = client
        self.sheet = sheet

    def build(
        self,
        org: str,
        department: str,
        report_type: str,
        start: date,
        end: date,
        author: str,
        row_count: int = 10,
    ) -> None:
        gen = REPORT_GENERATORS.get(report_type, gen_sales_report)
        headers, data = gen(row_count, start, end)

        start_fmt = start.strftime("%d.%m.%Y")
        end_fmt = end.strftime("%d.%m.%Y")
        period = f"{start_fmt} – {end_fmt}"
        today = date.today().strftime("%d.%m.%Y")

        # Строим грид значений
        values = [
            [f"ОТЧЁТ: {report_type}"],
            [],
            ["Организация:", org, "", "Подразделение:", department],
            ["Период:", period, "", "Дата составления:", today],
            ["Составитель:", author],
            [],
            headers,
            *data,
        ]

        # Строка итогов
        totals = ["ИТОГО"]
        for col in range(1, len(headers)):
            nums = []
            for r in data:
                if col >= len(r):
                    continue
                s = str(r[col]).replace(" ", "").replace("%", "")
                try:
                    nums.append(float(s))
                except (ValueError, TypeError):
                    pass
            if nums:
                total_val = sum(nums)
                totals.append(f"{int(total_val):,}".replace(",", " ") if total_val == int(total_val) else f"{total_val:.1f}")
            else:
                totals.append("")
        values.append(totals)
        values.append([])
        values.append(["Руководитель: _____________________"])

        # Нормализуем длины строк
        max_cols = max(len(r) for r in values)
        for row in values:
            while len(row) < max_cols:
                row.append("")

        # Записываем данные
        self.client.default_sheet = self.sheet
        self.client.clear_all(self.sheet)
        self.client.write_range("A1", values, value_input_option="USER_ENTERED")

        # Форматирование через batchUpdate
        sheet_id = self.client.get_sheet_id(self.sheet)
        reqs = []

        def grid(sr: int, sc: int, er: int = None, ec: int = None) -> dict:
            r = {"sheetId": sheet_id, "startRowIndex": sr, "startColumnIndex": sc}
            if er is not None:
                r["endRowIndex"] = er
            if ec is not None:
                r["endColumnIndex"] = ec
            return r

        def repeat_cell(rng: dict, fmt: dict, fields: list[str]) -> dict:
            return {
                "repeatCell": {
                    "range": rng,
                    "cell": {"userEnteredFormat": fmt},
                    "fields": "userEnteredFormat(" + ",".join(fields) + ")",
                }
            }

        # Заголовок отчёта (A1, merge на всю ширину)
        reqs.append({
            "mergeCells": {
                "mergeType": "MERGE_ALL",
                "range": grid(0, 0, 1, max_cols),
            }
        })
        reqs.append(repeat_cell(
            grid(0, 0, 1, max_cols),
            {
                "backgroundColor": self.COLORS["title_bg"],
                "textFormat": {"foregroundColor": self.COLORS["title_fg"], "bold": True, "fontSize": 14},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            },
            ["backgroundColor", "textFormat", "horizontalAlignment", "verticalAlignment"],
        ))
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 36},
            "fields": "pixelSize",
        }})

        # Блок информации (строки 2–6)
        for r in range(2, 6):
            reqs.append(repeat_cell(
                grid(r, 0, r + 1, max_cols),
                {"backgroundColor": self.COLORS["info_bg"]},
                ["backgroundColor"],
            ))

        # Заголовок таблицы (строка 7)
        reqs.append(repeat_cell(
            grid(7, 0, 8, max_cols),
            {
                "backgroundColor": self.COLORS["header_bg"],
                "textFormat": {"foregroundColor": self.COLORS["header_fg"], "bold": True},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            },
            ["backgroundColor", "textFormat", "horizontalAlignment", "verticalAlignment"],
        ))

        # Чередование строк данных (8 .. 7+len(data))
        data_start = 8
        data_end = data_start + len(data)
        for i in range(data_start, data_end):
            if (i - data_start) % 2 == 1:
                reqs.append(repeat_cell(grid(i, 0, i + 1, max_cols), {"backgroundColor": self.COLORS["row_alt"]}, ["backgroundColor"]))

        # Строка итогов
        reqs.append(repeat_cell(
            grid(data_end, 0, data_end + 1, max_cols),
            {"backgroundColor": self.COLORS["total_bg"], "textFormat": {"bold": True}},
            ["backgroundColor", "textFormat"],
        ))

        # Рамки вокруг таблицы
        reqs.append({
            "updateBorders": {
                "range": grid(7, 0, data_end + 1, max_cols),
                "top": {"style": "SOLID", "width": 1, "color": self.COLORS["border"]},
                "bottom": {"style": "SOLID", "width": 1, "color": self.COLORS["border"]},
                "left": {"style": "SOLID", "width": 1, "color": self.COLORS["border"]},
                "right": {"style": "SOLID", "width": 1, "color": self.COLORS["border"]},
                "innerHorizontal": {"style": "SOLID", "width": 1, "color": self.COLORS["border"]},
                "innerVertical": {"style": "SOLID", "width": 1, "color": self.COLORS["border"]},
            }
        })

        # Ширина колонок
        for c in range(max_cols):
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1},
                "properties": {"pixelSize": 120},
                "fields": "pixelSize",
            }})

        self.client.batch_update(reqs)


# ---------------------------------------------------------------------------
# Tkinter UI
# ---------------------------------------------------------------------------

class ReportApp(tk.Tk):
    # Цветовая палитра
    BG = "#f8f9fa"
    CARD_BG = "#ffffff"
    HEADER_BG = "#1a73e8"
    HEADER_FG = "#ffffff"
    ACCENT = "#1a73e8"
    ACCENT_HOVER = "#1557b0"
    TEXT = "#202124"
    TEXT_MUTED = "#5f6368"
    BORDER = "#dadce0"

    def __init__(self):
        super().__init__()
        self.title("Генератор отчётов")
        self.geometry("520x560")
        self.minsize(460, 480)
        self.resizable(True, True)
        self.configure(bg=self.BG)
        self._fonts = {}
        try:
            self._fonts["title"] = font.Font(family="Segoe UI", size=16, weight="bold")
            self._fonts["card"] = font.Font(family="Segoe UI", size=10, weight="bold")
            self._fonts["body"] = font.Font(family="Segoe UI", size=9)
            self._fonts["small"] = font.Font(family="Segoe UI", size=8)
            self._fonts["btn"] = font.Font(family="Segoe UI", size=11, weight="bold")
        except Exception:
            f = font.Font()
            self._fonts = {"title": f, "card": f, "body": f, "small": f, "btn": f}

        self.var_spreadsheet = tk.StringVar(value=DEFAULT_SPREADSHEET_ID)
        self.var_sheet = tk.StringVar()
        self.var_department = tk.StringVar(value=DEPARTMENTS[0])
        self.var_report = tk.StringVar(value=REPORT_TYPES[0])
        self.var_org = tk.StringVar(value="ООО «Пример»")
        self.var_author = tk.StringVar()
        self.var_date_from = tk.StringVar()
        self.var_date_to = tk.StringVar()
        self.var_rows = tk.StringVar(value="10")

        end = date.today()
        start = end - timedelta(days=30)
        self.var_date_from.set(start.strftime("%d.%m.%Y"))
        self.var_date_to.set(end.strftime("%d.%m.%Y"))

        self._build_ui()

    def _parse_date(self, s: str) -> date | None:
        try:
            d, m, y = s.strip().split(".")
            return date(int(y), int(m), int(d))
        except (ValueError, AttributeError):
            return None

    def _build_ui(self):
        main = tk.Frame(self, bg=self.BG, padx=20, pady=16)
        main.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        header = tk.Frame(main, bg=self.HEADER_BG, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="📊 Генератор отчётов",
            bg=self.HEADER_BG, fg=self.HEADER_FG, font=self._fonts["title"],
        ).pack(side=tk.LEFT, padx=20, pady=14)
        tk.Label(
            header, text="→ Google Таблицы",
            bg=self.HEADER_BG, fg="#c5dafb", font=self._fonts["body"],
        ).pack(side=tk.LEFT, pady=14)

        # Карточка: Подключение
        card_conn = tk.LabelFrame(
            main, text="Подключение к Google Таблице",
            bg=self.CARD_BG, fg=self.TEXT, font=self._fonts["card"],
            padx=12, pady=10,
        )
        card_conn.pack(fill=tk.X, pady=(16, 10))

        tk.Label(card_conn, text="ID таблицы:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=0, column=0, sticky=tk.W, pady=4)
        tk.Entry(card_conn, textvariable=self.var_spreadsheet, width=48, font=self._fonts["body"]).grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=4)

        tk.Label(card_conn, text="Лист:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=1, column=0, sticky=tk.W, pady=4)
        tk.Entry(card_conn, textvariable=self.var_sheet, width=30).grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=4)
        tk.Label(card_conn, text="(пусто = первый)", bg=self.CARD_BG, fg=self.TEXT_MUTED, font=self._fonts["small"]).grid(row=1, column=2, sticky=tk.W, padx=(6, 0), pady=4)

        card_conn.columnconfigure(1, weight=1)

        # Карточка: Параметры отчёта
        card_report = tk.LabelFrame(
            main, text="Параметры отчёта",
            bg=self.CARD_BG, fg=self.TEXT, font=self._fonts["card"],
            padx=12, pady=10,
        )
        card_report.pack(fill=tk.X, pady=(0, 10))

        row = 0
        tk.Label(card_report, text="Организация:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, pady=4)
        tk.Entry(card_report, textvariable=self.var_org, width=35).grid(row=row, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        row += 1

        tk.Label(card_report, text="Подразделение:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(card_report, textvariable=self.var_department, values=DEPARTMENTS, state="readonly", width=32).grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=4)
        row += 1

        tk.Label(card_report, text="Тип отчёта:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(card_report, textvariable=self.var_report, values=REPORT_TYPES, state="readonly", width=32).grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=4)
        row += 1

        tk.Label(card_report, text="Период:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, pady=4)
        period_f = tk.Frame(card_report, bg=self.CARD_BG)
        period_f.grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=4)
        tk.Entry(period_f, textvariable=self.var_date_from, width=10).pack(side=tk.LEFT)
        tk.Label(period_f, text=" — ", bg=self.CARD_BG, fg=self.TEXT_MUTED).pack(side=tk.LEFT, padx=2)
        tk.Entry(period_f, textvariable=self.var_date_to, width=10).pack(side=tk.LEFT)
        tk.Label(period_f, text=" ДД.ММ.ГГГГ", bg=self.CARD_BG, fg=self.TEXT_MUTED, font=self._fonts["small"]).pack(side=tk.LEFT)
        row += 1

        tk.Label(card_report, text="Составитель:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, pady=4)
        tk.Entry(card_report, textvariable=self.var_author, width=35).grid(row=row, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        row += 1

        tk.Label(card_report, text="Строк в отчёте:", bg=self.CARD_BG, fg=self.TEXT, width=14, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, pady=4)
        tk.Spinbox(card_report, textvariable=self.var_rows, from_=3, to=50, width=10).grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=4)

        card_report.columnconfigure(1, weight=1)

        # Кнопка
        btn = tk.Button(
            main, text="Создать отчёт",
            command=self._on_generate,
            bg=self.ACCENT, fg="white", font=self._fonts["btn"],
            activebackground=self.ACCENT_HOVER, activeforeground="white",
            cursor="hand2", relief=tk.FLAT, padx=24, pady=10,
        )
        btn.pack(pady=(8, 8))
        btn.bind("<Enter>", lambda e: btn.config(bg=self.ACCENT_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=self.ACCENT))

        # Статус
        self.lbl_status = tk.Label(main, text="", bg=self.BG, fg=self.TEXT_MUTED, font=self._fonts["body"])
        self.lbl_status.pack(anchor=tk.W)

    def _on_generate(self):
        sid = self.var_spreadsheet.get().strip()
        if not sid:
            self.lbl_status.config(text="Укажите ID таблицы.", fg="red")
            return

        date_from = self._parse_date(self.var_date_from.get())
        date_to = self._parse_date(self.var_date_to.get())
        if not date_from or not date_to:
            self.lbl_status.config(text="Проверьте даты (формат ДД.ММ.ГГГГ).", fg="red")
            return
        if date_from > date_to:
            self.lbl_status.config(text="Дата «с» не может быть позже даты «по».", fg="red")
            return

        try:
            rows = int(self.var_rows.get())
            rows = max(3, min(50, rows))
        except (ValueError, TypeError):
            rows = 10

        author = self.var_author.get().strip() or "Не указан"

        self.lbl_status.config(text="Создаю отчёт…", fg="#333")

        def run():
            try:
                creds_path = CREDENTIALS_PATH.strip()
                if not os.path.isabs(creds_path):
                    creds_path = str(Path(__file__).parent / creds_path)
                if not os.path.isfile(creds_path):
                    raise FileNotFoundError(
                        f"Файл учётных данных не найден: {creds_path}\n"
                        "Проверьте GOOGLE_CREDENTIALS_PATH в .env"
                    )
                client = GoogleSheetsClient(
                    spreadsheet_id=sid,
                    credentials_path=creds_path,
                )
                sheet = self.var_sheet.get().strip()
                if not sheet:
                    sheet = client.get_sheet_names()[0]
                    client.default_sheet = sheet

                builder = ReportBuilder(client, sheet)
                builder.build(
                    org=self.var_org.get().strip() or "Организация",
                    department=self.var_department.get(),
                    report_type=self.var_report.get(),
                    start=date_from,
                    end=date_to,
                    author=author,
                    row_count=rows,
                )
                url = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
                self.after(0, lambda: self.lbl_status.config(text=f"Готово! Таблица: {url}", fg="green"))
            except Exception as e:
                self.after(0, lambda err=e: self.lbl_status.config(text=f"Ошибка: {err}", fg="red"))

        threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = ReportApp()
    app.mainloop()
