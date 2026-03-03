"""
Заполнение CRM реалистичными тестовыми данными.

Создаёт ~1000 клиентов, ~1000 сделок, ~1000 задач через REST API.

Использование:
    python seed_data.py                  # 1000 записей на таблицу
    python seed_data.py --count 500      # 500 записей на таблицу
    python seed_data.py --url http://localhost:9000
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone

import requests

# ── Настройки ─────────────────────────────────────────────────────────────────

DEFAULT_URL   = "http://localhost:8000"
DEFAULT_COUNT = 1000

# ── Словари для генерации ─────────────────────────────────────────────────────

FIRST_NAMES_M = [
    "Александр", "Дмитрий", "Максим", "Сергей", "Андрей", "Алексей",
    "Артём", "Илья", "Кирилл", "Михаил", "Никита", "Роман", "Евгений",
    "Виктор", "Павел", "Николай", "Игорь", "Владимир", "Денис", "Антон",
    "Тимур", "Руслан", "Олег", "Вадим", "Глеб", "Константин", "Иван",
    "Фёдор", "Григорий", "Степан", "Леонид", "Анатолий", "Борис", "Юрий",
]

FIRST_NAMES_F = [
    "Анна", "Мария", "Елена", "Ольга", "Наталья", "Татьяна", "Ирина",
    "Светлана", "Екатерина", "Юлия", "Алина", "Дарья", "Полина", "Виктория",
    "Ксения", "Валерия", "Анастасия", "Диана", "Людмила", "Галина",
    "Тамара", "Вероника", "Надежда", "Инна", "Жанна", "Алёна", "Маргарита",
]

LAST_NAMES_M = [
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров",
    "Соколов", "Михайлов", "Новиков", "Фёдоров", "Морозов", "Волков",
    "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов",
    "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Никитин",
    "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев",
    "Романов", "Воробьёв", "Сергеев", "Кузьмин", "Фролов", "Александров",
    "Дмитриев", "Королёв", "Гусев", "Титов", "Кириллов", "Марков",
]

LAST_NAMES_F = [ln + "а" for ln in LAST_NAMES_M]

PATRONYMICS_M = [
    "Александрович", "Дмитриевич", "Сергеевич", "Андреевич", "Алексеевич",
    "Михайлович", "Николаевич", "Иванович", "Владимирович", "Павлович",
    "Юрьевич", "Евгеньевич", "Олегович", "Витальевич", "Геннадьевич",
    "Анатольевич", "Борисович", "Игоревич", "Константинович", "Вячеславович",
]

PATRONYMICS_F = [
    "Александровна", "Дмитриевна", "Сергеевна", "Андреевна", "Алексеевна",
    "Михайловна", "Николаевна", "Ивановна", "Владимировна", "Павловна",
    "Юрьевна", "Евгеньевна", "Олеговна", "Витальевна", "Геннадьевна",
    "Анатольевна", "Борисовна", "Игоревна", "Константиновна", "Вячеславовна",
]

COMPANY_PREFIXES = [
    "ООО", "ЗАО", "АО", "ПАО", "ИП", "ГК", "ФГУ",
]

COMPANY_NAMES = [
    "Стройград", "ТехноСервис", "МегаТорг", "ПромСнаб", "АльфаГрупп",
    "ДельтаСистемс", "КапиталИнвест", "РусТех", "НовоСтрой", "АвтоПлюс",
    "ЛогистикПро", "МедиаСофт", "АгроПром", "ЭнергоСбыт", "БизнесЛайн",
    "ТрансРегион", "ЦифроТех", "СтальПром", "ФинансГрупп", "ТоргСеть",
    "Горизонт", "Меридиан", "Сфера", "Апекс", "Вектор", "Синтез",
    "Прогресс", "Импульс", "Альянс", "Континент", "Эталон", "Оптима",
    "Максимум", "Профит", "Рубеж", "Статус", "Партнёр", "Формула",
    "Ресурс", "Перспектива", "Горизонт", "Феникс", "Лидер", "Компас",
    "Маяк", "Атлант", "Нептун", "Тритон", "Альта", "Прайм",
]

DEAL_VERBS = [
    "Поставка", "Разработка", "Внедрение", "Обслуживание", "Аренда",
    "Монтаж", "Проектирование", "Консультация", "Аудит", "Оптимизация",
    "Модернизация", "Техническое обслуживание", "Интеграция", "Сопровождение",
    "Настройка", "Обучение персонала по", "Тестирование", "Реализация",
]

DEAL_OBJECTS = [
    "программного обеспечения", "серверного оборудования", "CRM-системы",
    "корпоративной сети", "системы видеонаблюдения", "складского ПО",
    "бухгалтерской системы", "производственной линии", "торгового оборудования",
    "систем безопасности", "облачной инфраструктуры", "мобильного приложения",
    "веб-платформы", "ERP-системы", "системы аналитики", "сайта компании",
    "документооборота", "корпоративного портала", "телефонии VoIP",
    "системы мониторинга", "автоматизации склада", "кассового оборудования",
    "IP-камер", "СКУД", "резервного копирования",
]

DEAL_DESCRIPTIONS = [
    "Клиент заинтересован в долгосрочном сотрудничестве.",
    "Требуется демонстрация решения перед финальным решением.",
    "Тендерная процедура. Конкурируем с двумя поставщиками.",
    "Срочный проект, дедлайн — конец квартала.",
    "Повторный заказ от постоянного клиента.",
    "Необходимо согласование с IT-отделом заказчика.",
    "Пилотный проект на 3 месяца с возможностью расширения.",
    "Бюджет утверждён, ожидаем подписания договора.",
    "Клиент сравнивает с зарубежными аналогами.",
    "Проект включён в план цифровизации компании на год.",
    "Требуется интеграция с существующей инфраструктурой.",
    "Инициатива исходит от нового IT-директора.",
    "Запрос пришёл через партнёрский канал.",
    None,
]

TASK_TITLES = [
    "Позвонить клиенту и уточнить детали",
    "Отправить коммерческое предложение",
    "Подготовить техническое задание",
    "Провести онлайн-демонстрацию продукта",
    "Согласовать условия договора",
    "Выставить счёт на оплату",
    "Подписать NDA с клиентом",
    "Подготовить презентацию для ЛПР",
    "Уточнить бюджет и сроки",
    "Провести встречу с техническим отделом",
    "Отправить образцы продукции",
    "Проверить статус оплаты счёта",
    "Подготовить акт выполненных работ",
    "Запросить обратную связь после внедрения",
    "Сформировать отчёт по проекту",
    "Организовать обучение пользователей",
    "Согласовать план-график работ",
    "Провести аудит текущей инфраструктуры",
    "Подготовить инструкцию для пользователей",
    "Отправить напоминание о продлении",
    "Связаться с техподдержкой по обращению",
    "Провести ретроспективу проекта",
    "Обновить данные в CRM",
    "Отработать возражения клиента",
    "Запросить реквизиты для договора",
    "Согласовать техническое решение",
    "Провести тестирование после обновления",
    "Передать проект на поддержку",
    "Запланировать повторный звонок",
    "Подготовить сравнительный анализ",
]

TASK_DESCRIPTIONS = [
    "Важно сделать до конца недели.",
    "Клиент ожидает ответа в течение 24 часов.",
    "Согласовано с руководителем.",
    "Требуется участие технического специалиста.",
    "Срочно! Клиент недоволен задержкой.",
    "Перенесено с прошлой недели.",
    "Повторное напоминание — клиент не отвечает.",
    "Зависит от получения документов от клиента.",
    None,
    None,
]

EMAIL_DOMAINS = [
    "gmail.com", "mail.ru", "yandex.ru", "bk.ru", "inbox.ru",
    "rambler.ru", "outlook.com", "icloud.com", "proton.me",
]

CLIENT_STATUSES = ["lead", "lead", "active", "active", "active", "inactive", "archived"]
DEAL_STATUSES   = ["new", "new", "negotiation", "negotiation", "won", "won", "lost", "paused"]
TASK_STATUSES   = ["pending", "pending", "pending", "in_progress", "done", "done", "cancelled"]
CURRENCIES      = ["RUB", "RUB", "RUB", "RUB", "RUB", "USD", "EUR"]


# ══════════════════════════════════════════════════════════════════════════════
# ГЕНЕРАТОРЫ
# ══════════════════════════════════════════════════════════════════════════════

def _phone() -> str:
    return "+7" + "".join(str(random.randint(0, 9)) for _ in range(10))


_TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu',
    'я':'ya',
}

def _translit(text: str) -> str:
    return "".join(_TRANSLIT.get(c.lower(), c) for c in text if c.isalpha())


def _email(first: str, last: str) -> str:
    f = _translit(first)[:3]
    l = _translit(last)[:6]
    n = random.randint(1, 99)
    domain = random.choice(EMAIL_DOMAINS)
    patterns = [f"{f}{l}@{domain}", f"{l}{n}@{domain}", f"{f}.{l}@{domain}"]
    return random.choice(patterns)


def _company() -> str:
    return f"{random.choice(COMPANY_PREFIXES)} «{random.choice(COMPANY_NAMES)}»"


def _person() -> tuple[str, str, str]:
    """Возвращает (имя, фамилия, отчество)."""
    if random.random() < 0.5:
        return (
            random.choice(FIRST_NAMES_M),
            random.choice(LAST_NAMES_M),
            random.choice(PATRONYMICS_M),
        )
    return (
        random.choice(FIRST_NAMES_F),
        random.choice(LAST_NAMES_F),
        random.choice(PATRONYMICS_F),
    )


def _future_date(days_min: int = 1, days_max: int = 90) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=random.randint(days_min, days_max))
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _past_or_future_date() -> str:
    offset = random.randint(-30, 60)
    dt = datetime.now(timezone.utc) + timedelta(days=offset)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _amount() -> float:
    tiers = [
        (0.3, lambda: round(random.uniform(10_000,    100_000),    -3)),
        (0.4, lambda: round(random.uniform(100_000,   1_000_000),  -3)),
        (0.2, lambda: round(random.uniform(1_000_000, 10_000_000), -3)),
        (0.1, lambda: round(random.uniform(10_000_000, 50_000_000), -3)),
    ]
    r = random.random()
    cumulative = 0.0
    for prob, gen in tiers:
        cumulative += prob
        if r < cumulative:
            return gen()
    return 500_000.0


# ══════════════════════════════════════════════════════════════════════════════
# СИДЕР
# ══════════════════════════════════════════════════════════════════════════════

class Seeder:
    def __init__(self, base_url: str, count: int) -> None:
        self.base  = base_url.rstrip("/")
        self.count = count
        self._s    = requests.Session()
        self._s.headers["Content-Type"] = "application/json"

    def _post(self, path: str, body: dict) -> dict:
        r = self._s.post(f"{self.base}{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()

    def _progress(self, label: str, i: int, total: int) -> None:
        pct  = (i + 1) / total * 100
        bar  = "█" * int(pct // 2) + "░" * (50 - int(pct // 2))
        print(f"\r{label}  [{bar}]  {i + 1}/{total} ({pct:.0f}%)", end="", flush=True)

    # ── Клиенты ───────────────────────────────────────────────────────────────

    def seed_clients(self) -> list[int]:
        print(f"\n▶  Клиенты ({self.count})")
        ids: list[int] = []
        for i in range(self.count):
            first, last, patron = _person()
            full_name = f"{last} {first} {patron}"
            has_company = random.random() < 0.75
            payload: dict = {
                "name":    full_name,
                "email":   _email(first, last) if random.random() < 0.85 else None,
                "phone":   _phone()            if random.random() < 0.90 else None,
                "company": _company()          if has_company else None,
                "status":  random.choice(CLIENT_STATUSES),
            }
            if random.random() < 0.3:
                payload["notes"] = random.choice([
                    "Крупный клиент, работаем с 2021 года.",
                    "Пришёл по рекомендации партнёра.",
                    "Интересует расширенная поддержка.",
                    "Требует особого внимания.",
                    "Рассматривает несколько поставщиков.",
                    "Бюджет ограничен.",
                    "VIP-клиент.",
                ])
            payload = {k: v for k, v in payload.items() if v is not None}
            try:
                obj = self._post("/clients", payload)
                ids.append(obj["id"])
            except Exception as e:
                print(f"\n  ⚠  Клиент #{i}: {e}")
            self._progress("Клиенты  ", i, self.count)
        print(f"\n  ✓  Создано: {len(ids)}")
        return ids

    # ── Сделки ────────────────────────────────────────────────────────────────

    def seed_deals(self, client_ids: list[int]) -> list[int]:
        print(f"\n▶  Сделки ({self.count})")
        ids: list[int] = []
        for i in range(self.count):
            title = f"{random.choice(DEAL_VERBS)} {random.choice(DEAL_OBJECTS)}"
            desc  = random.choice(DEAL_DESCRIPTIONS)
            cid   = random.choice(client_ids) if client_ids and random.random() < 0.80 else None
            status = random.choice(DEAL_STATUSES)
            payload: dict = {
                "title":       title,
                "status":      status,
                "amount":      _amount(),
                "currency":    random.choice(CURRENCIES),
            }
            if desc:
                payload["description"] = desc
            if cid:
                payload["client_id"] = cid
            try:
                obj = self._post("/deals", payload)
                ids.append(obj["id"])
            except Exception as e:
                print(f"\n  ⚠  Сделка #{i}: {e}")
            self._progress("Сделки   ", i, self.count)
        print(f"\n  ✓  Создано: {len(ids)}")
        return ids

    # ── Задачи ────────────────────────────────────────────────────────────────

    def seed_tasks(self, client_ids: list[int], deal_ids: list[int]) -> None:
        print(f"\n▶  Задачи ({self.count})")
        created = 0
        for i in range(self.count):
            status = random.choice(TASK_STATUSES)
            desc   = random.choice(TASK_DESCRIPTIONS)
            cid    = random.choice(client_ids) if client_ids and random.random() < 0.70 else None
            did    = random.choice(deal_ids)   if deal_ids   and random.random() < 0.50 else None
            due    = None
            if status in ("pending", "in_progress"):
                due = _past_or_future_date() if random.random() < 0.75 else None
            payload: dict = {
                "title":  random.choice(TASK_TITLES),
                "status": status,
            }
            if desc:
                payload["description"] = desc
            if cid:
                payload["client_id"] = cid
            if did:
                payload["deal_id"] = did
            if due:
                payload["due_date"] = due
            try:
                self._post("/tasks", payload)
                created += 1
            except Exception as e:
                print(f"\n  ⚠  Задача #{i}: {e}")
            self._progress("Задачи   ", i, self.count)
        print(f"\n  ✓  Создано: {created}")

    # ── Точка входа ───────────────────────────────────────────────────────────

    def run(self) -> None:
        print("=" * 60)
        print(f"  Mini CRM — заполнение тестовыми данными")
        print(f"  Сервер : {self.base}")
        print(f"  Кол-во : ~{self.count} записей на таблицу")
        print("=" * 60)

        try:
            requests.get(f"{self.base}/dashboard", timeout=3).raise_for_status()
        except Exception as e:
            print(f"\n❌  Сервер недоступен: {e}")
            print("   Запустите сервер: docker compose up")
            sys.exit(1)

        client_ids = self.seed_clients()
        deal_ids   = self.seed_deals(client_ids)
        self.seed_tasks(client_ids, deal_ids)

        print("\n" + "=" * 60)
        print(f"  ✅  Готово! Добавлено:")
        print(f"      Клиенты : {len(client_ids)}")
        print(f"      Сделки  : {len(deal_ids)}")
        print(f"      Задачи  : {self.count}")
        print("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Заполнить CRM тестовыми данными")
    parser.add_argument("--url",   default=DEFAULT_URL,   help="URL бэкенда")
    parser.add_argument("--count", default=DEFAULT_COUNT, type=int,
                        help="Количество записей на таблицу (по умолчанию 1000)")
    args = parser.parse_args()

    Seeder(args.url, args.count).run()
