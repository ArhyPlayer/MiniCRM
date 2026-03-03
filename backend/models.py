"""
SQLite DDL-схемы и Pydantic-модели для мини-CRM.

Таблицы:
  clients  — клиенты с поддержкой статуса (lead / active / inactive / archived)
  deals    — сделки/заказы, опционально привязанные к клиенту
  tasks    — задачи/напоминания, опционально связанные с клиентом и/или сделкой
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ── SQLite DDL ─────────────────────────────────────────────────────────────────

SQL_CREATE_CLIENTS = """
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT,
    phone       TEXT,
    company     TEXT,
    notes       TEXT,
    status      TEXT    NOT NULL DEFAULT 'lead',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
)
"""

SQL_CREATE_DEALS = """
CREATE TABLE IF NOT EXISTS deals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    client_id   INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    status      TEXT    NOT NULL DEFAULT 'new',
    amount      REAL    NOT NULL DEFAULT 0.0,
    currency    TEXT    NOT NULL DEFAULT 'RUB',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
)
"""

SQL_CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    client_id   INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    deal_id     INTEGER REFERENCES deals(id)   ON DELETE SET NULL,
    status      TEXT    NOT NULL DEFAULT 'pending',
    due_date    TEXT,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
)
"""

# ── Индексы для ускорения поиска ───────────────────────────────────────────────

SQL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_clients_status  ON clients (status)",
    "CREATE INDEX IF NOT EXISTS idx_deals_status    ON deals   (status)",
    "CREATE INDEX IF NOT EXISTS idx_deals_client    ON deals   (client_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status    ON tasks   (status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_client    ON tasks   (client_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_deal      ON tasks   (deal_id)",
]

# ── Enums ──────────────────────────────────────────────────────────────────────


class ClientStatus(str, Enum):
    LEAD     = "lead"
    ACTIVE   = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class DealStatus(str, Enum):
    NEW         = "new"
    NEGOTIATION = "negotiation"
    WON         = "won"
    LOST        = "lost"
    PAUSED      = "paused"


class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    CANCELLED   = "cancelled"


# ── Client schemas ─────────────────────────────────────────────────────────────


class ClientCreate(BaseModel):
    name:    str               = Field(..., min_length=1, max_length=255)
    email:   Optional[str]    = None
    phone:   Optional[str]    = None
    company: Optional[str]    = None
    notes:   Optional[str]    = None
    status:  ClientStatus     = ClientStatus.LEAD


class ClientUpdate(BaseModel):
    name:    Optional[str]          = Field(None, min_length=1, max_length=255)
    email:   Optional[str]          = None
    phone:   Optional[str]          = None
    company: Optional[str]          = None
    notes:   Optional[str]          = None
    status:  Optional[ClientStatus] = None


class ClientResponse(BaseModel):
    id:         int
    name:       str
    email:      Optional[str]
    phone:      Optional[str]
    company:    Optional[str]
    notes:      Optional[str]
    status:     str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Deal schemas ───────────────────────────────────────────────────────────────


class DealCreate(BaseModel):
    title:       str              = Field(..., min_length=1, max_length=255)
    description: Optional[str]   = None
    client_id:   Optional[int]   = None
    status:      DealStatus      = DealStatus.NEW
    amount:      float           = Field(default=0.0, ge=0)
    currency:    str             = Field(default="RUB", max_length=10)


class DealUpdate(BaseModel):
    title:       Optional[str]         = Field(None, min_length=1, max_length=255)
    description: Optional[str]         = None
    client_id:   Optional[int]         = None
    status:      Optional[DealStatus]  = None
    amount:      Optional[float]       = Field(None, ge=0)
    currency:    Optional[str]         = Field(None, max_length=10)


class DealResponse(BaseModel):
    id:          int
    title:       str
    description: Optional[str]
    client_id:   Optional[int]
    status:      str
    amount:      float
    currency:    str
    created_at:  str
    updated_at:  str

    model_config = {"from_attributes": True}


# ── Task schemas ───────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    title:       str             = Field(..., min_length=1, max_length=255)
    description: Optional[str]  = None
    client_id:   Optional[int]  = None
    deal_id:     Optional[int]  = None
    status:      TaskStatus     = TaskStatus.PENDING
    due_date:    Optional[str]  = Field(None, description="ISO 8601, например 2026-03-15T10:00:00")


class TaskUpdate(BaseModel):
    title:       Optional[str]        = Field(None, min_length=1, max_length=255)
    description: Optional[str]        = None
    client_id:   Optional[int]        = None
    deal_id:     Optional[int]        = None
    status:      Optional[TaskStatus] = None
    due_date:    Optional[str]        = None


class TaskResponse(BaseModel):
    id:          int
    title:       str
    description: Optional[str]
    client_id:   Optional[int]
    deal_id:     Optional[int]
    status:      str
    due_date:    Optional[str]
    created_at:  str
    updated_at:  str

    model_config = {"from_attributes": True}
