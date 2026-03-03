"""
FastAPI-приложение мини-CRM.

Запуск:
    uvicorn backend.api:app --reload --port 8000

Документация:
    http://localhost:8000/docs      — Swagger UI
    http://localhost:8000/redoc     — ReDoc
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import CRMDatabase
from .models import (
    ClientCreate,
    ClientResponse,
    ClientStatus,
    ClientUpdate,
    DealCreate,
    DealResponse,
    DealStatus,
    DealUpdate,
    TaskCreate,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)

# ── Приложение ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Mini CRM",
    version="1.0.0",
    description="Минимально рабочая CRM: клиенты, сделки, задачи.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_DB_PATH = os.getenv("CRM_DB_PATH", "data/crm.db")
db = CRMDatabase(db_path=_DB_PATH)

# ── Вспомогательные ────────────────────────────────────────────────────────────


def _or_404(obj: Optional[Any], detail: str = "Запись не найдена") -> Any:
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════


@app.get(
    "/dashboard",
    response_model=Dict[str, Any],
    tags=["dashboard"],
    summary="Сводка: клиенты, сделки, задачи",
)
def get_dashboard() -> Dict[str, Any]:
    return db.dashboard()


# ══════════════════════════════════════════════════════════════════════════════
# CLIENTS
# ══════════════════════════════════════════════════════════════════════════════


@app.post(
    "/clients",
    response_model=ClientResponse,
    status_code=201,
    tags=["clients"],
    summary="Создать клиента",
)
def create_client(data: ClientCreate) -> Any:
    return db.create_client(data)


@app.get(
    "/clients",
    response_model=List[ClientResponse],
    tags=["clients"],
    summary="Список клиентов с фильтром по статусу",
)
def list_clients(
    status: Optional[ClientStatus] = Query(None, description="Фильтр по статусу"),
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0,  ge=0),
) -> Any:
    return db.list_clients(
        status=status.value if status else None,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/clients/search",
    response_model=List[ClientResponse],
    tags=["clients"],
    summary="Поиск клиентов по имени / email / телефону / компании",
)
def search_clients(
    q:     str = Query(..., min_length=1, description="Строка поиска"),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    return db.search_clients(query=q, limit=limit)


@app.get(
    "/clients/{client_id}",
    response_model=ClientResponse,
    tags=["clients"],
    summary="Получить клиента по ID",
)
def get_client(client_id: int) -> Any:
    return _or_404(db.get_client(client_id), "Клиент не найден")


@app.patch(
    "/clients/{client_id}",
    response_model=ClientResponse,
    tags=["clients"],
    summary="Обновить данные клиента (частичное обновление)",
)
def update_client(client_id: int, data: ClientUpdate) -> Any:
    _or_404(db.get_client(client_id), "Клиент не найден")
    return db.update_client(client_id, data)


@app.patch(
    "/clients/{client_id}/archive",
    response_model=ClientResponse,
    tags=["clients"],
    summary="Архивировать клиента",
)
def archive_client(client_id: int) -> Any:
    return _or_404(db.archive_client(client_id), "Клиент не найден")


@app.delete(
    "/clients/{client_id}",
    status_code=204,
    tags=["clients"],
    summary="Удалить клиента",
)
def delete_client(client_id: int) -> None:
    if not db.delete_client(client_id):
        raise HTTPException(status_code=404, detail="Клиент не найден")


# ══════════════════════════════════════════════════════════════════════════════
# DEALS
# ══════════════════════════════════════════════════════════════════════════════


@app.post(
    "/deals",
    response_model=DealResponse,
    status_code=201,
    tags=["deals"],
    summary="Создать сделку",
)
def create_deal(data: DealCreate) -> Any:
    if data.client_id is not None:
        _or_404(db.get_client(data.client_id), "Клиент не найден")
    return db.create_deal(data)


@app.get(
    "/deals",
    response_model=List[DealResponse],
    tags=["deals"],
    summary="Список сделок с фильтрами по статусу и клиенту",
)
def list_deals(
    status:    Optional[DealStatus] = Query(None, description="Фильтр по статусу"),
    client_id: Optional[int]        = Query(None, description="Фильтр по клиенту"),
    limit:     int = Query(50, ge=1, le=200),
    offset:    int = Query(0,  ge=0),
) -> Any:
    return db.list_deals(
        status=status.value if status else None,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/deals/search",
    response_model=List[DealResponse],
    tags=["deals"],
    summary="Поиск сделок по заголовку и описанию",
)
def search_deals(
    q:     str = Query(..., min_length=1, description="Строка поиска"),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    return db.search_deals(query=q, limit=limit)


@app.get(
    "/deals/{deal_id}",
    response_model=DealResponse,
    tags=["deals"],
    summary="Получить сделку по ID",
)
def get_deal(deal_id: int) -> Any:
    return _or_404(db.get_deal(deal_id), "Сделка не найдена")


@app.patch(
    "/deals/{deal_id}",
    response_model=DealResponse,
    tags=["deals"],
    summary="Обновить сделку (частичное обновление)",
)
def update_deal(deal_id: int, data: DealUpdate) -> Any:
    _or_404(db.get_deal(deal_id), "Сделка не найдена")
    if data.client_id is not None:
        _or_404(db.get_client(data.client_id), "Клиент не найден")
    return db.update_deal(deal_id, data)


@app.delete(
    "/deals/{deal_id}",
    status_code=204,
    tags=["deals"],
    summary="Удалить сделку",
)
def delete_deal(deal_id: int) -> None:
    if not db.delete_deal(deal_id):
        raise HTTPException(status_code=404, detail="Сделка не найдена")


# ══════════════════════════════════════════════════════════════════════════════
# TASKS
# ══════════════════════════════════════════════════════════════════════════════


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=201,
    tags=["tasks"],
    summary="Создать задачу / напоминание",
)
def create_task(data: TaskCreate) -> Any:
    if data.client_id is not None:
        _or_404(db.get_client(data.client_id), "Клиент не найден")
    if data.deal_id is not None:
        _or_404(db.get_deal(data.deal_id), "Сделка не найдена")
    return db.create_task(data)


@app.get(
    "/tasks",
    response_model=List[TaskResponse],
    tags=["tasks"],
    summary="Список задач с фильтрами по статусу, клиенту, сделке",
)
def list_tasks(
    status:    Optional[TaskStatus] = Query(None, description="Фильтр по статусу"),
    client_id: Optional[int]        = Query(None, description="Фильтр по клиенту"),
    deal_id:   Optional[int]        = Query(None, description="Фильтр по сделке"),
    limit:     int = Query(50, ge=1, le=200),
    offset:    int = Query(0,  ge=0),
) -> Any:
    return db.list_tasks(
        status=status.value if status else None,
        client_id=client_id,
        deal_id=deal_id,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["tasks"],
    summary="Получить задачу по ID",
)
def get_task(task_id: int) -> Any:
    return _or_404(db.get_task(task_id), "Задача не найдена")


@app.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["tasks"],
    summary="Обновить задачу (частичное обновление)",
)
def update_task(task_id: int, data: TaskUpdate) -> Any:
    _or_404(db.get_task(task_id), "Задача не найдена")
    if data.client_id is not None:
        _or_404(db.get_client(data.client_id), "Клиент не найден")
    if data.deal_id is not None:
        _or_404(db.get_deal(data.deal_id), "Сделка не найдена")
    return db.update_task(task_id, data)


@app.patch(
    "/tasks/{task_id}/done",
    response_model=TaskResponse,
    tags=["tasks"],
    summary="Отметить задачу выполненной",
)
def complete_task(task_id: int) -> Any:
    return _or_404(db.complete_task(task_id), "Задача не найдена")


@app.patch(
    "/tasks/{task_id}/reopen",
    response_model=TaskResponse,
    tags=["tasks"],
    summary="Вернуть задачу в работу (pending)",
)
def reopen_task(task_id: int) -> Any:
    return _or_404(db.reopen_task(task_id), "Задача не найдена")


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    tags=["tasks"],
    summary="Удалить задачу",
)
def delete_task(task_id: int) -> None:
    if not db.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
