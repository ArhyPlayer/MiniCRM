# ── Образ ─────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Не писать .pyc, не буферизировать вывод — удобно для логов в реальном времени
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости устанавливаем отдельным слоем — кешируется
# (сам код НЕ копируем — он монтируется через volume в docker-compose)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Точка входа ───────────────────────────────────────────────────────────────
# --reload       → uvicorn перезапускает воркер при изменении .py файлов
# --reload-dir   → следим только за папкой backend/ (watchfiles)
# --log-level    → подробные логи для отладки
CMD ["uvicorn", "backend.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--reload-dir", "/app/backend", \
     "--log-level", "debug"]
