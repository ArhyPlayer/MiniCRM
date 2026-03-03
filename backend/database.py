"""
CRMDatabase — единая точка доступа к SQLite.

При инициализации автоматически создаёт все таблицы и индексы,
если они ещё не существуют.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import (
    SQL_CREATE_CLIENTS,
    SQL_CREATE_DEALS,
    SQL_CREATE_TASKS,
    SQL_INDEXES,
    ClientCreate,
    ClientUpdate,
    DealCreate,
    DealUpdate,
    TaskCreate,
    TaskUpdate,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _serialize(data: Any) -> Dict[str, Any]:
    """Pydantic model → dict, enum → str, None-поля отброшены."""
    return {
        k: (v.value if hasattr(v, "value") else v)
        for k, v in data.model_dump().items()
        if v is not None
    }


class CRMDatabase:
    """
    CRUD-операции для трёх сущностей: клиенты, сделки, задачи.

    Параметры
    ----------
    db_path : путь к файлу SQLite (создаётся автоматически).
    """

    def __init__(self, db_path: str = "data/crm.db") -> None:
        self.db_path = db_path
        self._init_db()

    # ── внутренние ────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(SQL_CREATE_CLIENTS)
            conn.execute(SQL_CREATE_DEALS)
            conn.execute(SQL_CREATE_TASKS)
            for idx_sql in SQL_INDEXES:
                conn.execute(idx_sql)
            conn.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # CLIENTS
    # ══════════════════════════════════════════════════════════════════════════

    def create_client(self, data: ClientCreate) -> Dict[str, Any]:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO clients
                    (name, email, phone, company, notes, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.name,
                    data.email,
                    data.phone,
                    data.company,
                    data.notes,
                    data.status.value,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_client(cur.lastrowid)  # type: ignore[arg-type]

    def get_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM clients WHERE id = ?", (client_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_clients(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM clients
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM clients
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def search_clients(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Поиск по имени, email, телефону, компании (LIKE, регистронезависимо)."""
        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM clients
                WHERE  name    LIKE ? COLLATE NOCASE
                   OR  email   LIKE ? COLLATE NOCASE
                   OR  phone   LIKE ? COLLATE NOCASE
                   OR  company LIKE ? COLLATE NOCASE
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_client(
        self, client_id: int, data: ClientUpdate
    ) -> Optional[Dict[str, Any]]:
        fields = _serialize(data)
        if not fields:
            return self.get_client(client_id)
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [client_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE clients SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
        return self.get_client(client_id)

    def archive_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            conn.execute(
                "UPDATE clients SET status = 'archived', updated_at = ? WHERE id = ?",
                (_now(), client_id),
            )
            conn.commit()
        return self.get_client(client_id)

    def delete_client(self, client_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM clients WHERE id = ?", (client_id,)
            )
            conn.commit()
        return cur.rowcount > 0

    def count_clients(self, status: Optional[str] = None) -> int:
        with self._connect() as conn:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) FROM clients WHERE status = ?", (status,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM clients").fetchone()
        return row[0]

    # ══════════════════════════════════════════════════════════════════════════
    # DEALS
    # ══════════════════════════════════════════════════════════════════════════

    def create_deal(self, data: DealCreate) -> Dict[str, Any]:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO deals
                    (title, description, client_id, status, amount, currency,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.title,
                    data.description,
                    data.client_id,
                    data.status.value,
                    data.amount,
                    data.currency,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_deal(cur.lastrowid)  # type: ignore[arg-type]

    def get_deal(self, deal_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM deals WHERE id = ?", (deal_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_deals(
        self,
        status: Optional[str] = None,
        client_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if client_id is not None:
            conditions.append("client_id = ?")
            params.append(client_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params += [limit, offset]
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM deals
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def search_deals(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Поиск по заголовку и описанию сделки."""
        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM deals
                WHERE  title       LIKE ? COLLATE NOCASE
                   OR  description LIKE ? COLLATE NOCASE
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_deal(
        self, deal_id: int, data: DealUpdate
    ) -> Optional[Dict[str, Any]]:
        fields = _serialize(data)
        if not fields:
            return self.get_deal(deal_id)
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [deal_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE deals SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
        return self.get_deal(deal_id)

    def delete_deal(self, deal_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
            conn.commit()
        return cur.rowcount > 0

    def count_deals(
        self, status: Optional[str] = None, client_id: Optional[int] = None
    ) -> int:
        conditions: List[str] = []
        params: List[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if client_id is not None:
            conditions.append("client_id = ?")
            params.append(client_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM deals {where}", params
            ).fetchone()
        return row[0]

    # ══════════════════════════════════════════════════════════════════════════
    # TASKS
    # ══════════════════════════════════════════════════════════════════════════

    def create_task(self, data: TaskCreate) -> Dict[str, Any]:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks
                    (title, description, client_id, deal_id, status,
                     due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.title,
                    data.description,
                    data.client_id,
                    data.deal_id,
                    data.status.value,
                    data.due_date,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_task(cur.lastrowid)  # type: ignore[arg-type]

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_tasks(
        self,
        status: Optional[str] = None,
        client_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if client_id is not None:
            conditions.append("client_id = ?")
            params.append(client_id)
        if deal_id is not None:
            conditions.append("deal_id = ?")
            params.append(deal_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params += [limit, offset]
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM tasks
                {where}
                ORDER BY due_date ASC NULLS LAST, created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_task(
        self, task_id: int, data: TaskUpdate
    ) -> Optional[Dict[str, Any]]:
        fields = _serialize(data)
        if not fields:
            return self.get_task(task_id)
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
        return self.get_task(task_id)

    def complete_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Отметить задачу выполненной (статус → done)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'done', updated_at = ? WHERE id = ?",
                (_now(), task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def reopen_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Вернуть задачу в работу (статус → pending)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'pending', updated_at = ? WHERE id = ?",
                (_now(), task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return cur.rowcount > 0

    def count_tasks(
        self,
        status: Optional[str] = None,
        client_id: Optional[int] = None,
        deal_id: Optional[int] = None,
    ) -> int:
        conditions: List[str] = []
        params: List[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if client_id is not None:
            conditions.append("client_id = ?")
            params.append(client_id)
        if deal_id is not None:
            conditions.append("deal_id = ?")
            params.append(deal_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM tasks {where}", params
            ).fetchone()
        return row[0]

    # ══════════════════════════════════════════════════════════════════════════
    # Дашборд / сводка
    # ══════════════════════════════════════════════════════════════════════════

    def dashboard(self) -> Dict[str, Any]:
        """Краткая сводка по всем трём сущностям."""
        with self._connect() as conn:
            clients_total = conn.execute(
                "SELECT COUNT(*) FROM clients"
            ).fetchone()[0]
            clients_by_status = {
                row["status"]: row["cnt"]
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS cnt FROM clients GROUP BY status"
                ).fetchall()
            }
            deals_total = conn.execute(
                "SELECT COUNT(*) FROM deals"
            ).fetchone()[0]
            deals_by_status = {
                row["status"]: row["cnt"]
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS cnt FROM deals GROUP BY status"
                ).fetchall()
            }
            deals_amount = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM deals WHERE status = 'won'"
            ).fetchone()[0]
            tasks_pending = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status IN ('pending', 'in_progress')"
            ).fetchone()[0]
            tasks_overdue = conn.execute(
                """
                SELECT COUNT(*) FROM tasks
                WHERE status IN ('pending', 'in_progress')
                  AND due_date IS NOT NULL
                  AND due_date < ?
                """,
                (_now(),),
            ).fetchone()[0]
        return {
            "clients": {"total": clients_total, "by_status": clients_by_status},
            "deals": {
                "total": deals_total,
                "by_status": deals_by_status,
                "won_amount": deals_amount,
            },
            "tasks": {"pending": tasks_pending, "overdue": tasks_overdue},
        }
