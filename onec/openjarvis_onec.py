"""Модуль 1C для OpenJarvis: выручка и задачи CRM через OData.

Добавляет в OpenJarvis инструменты:
  ``onec_revenue`` — выручка по документам реализации за период. Суммы
                     считает модуль, поэтому цифры точные (модель ничего не складывает);
  ``onec_tasks``   — невыполненные задачи со сроком на дату (и просроченные).
Подключается через ``openjarvis_addon_hook`` (``setup.sh --onec``).

Настройки — ``~/.openjarvis/onec.env`` (права 600):
  ONEC_URL                  http://сервер/база/odata/standard.odata
  ONEC_USER, ONEC_PASSWORD  пользователь 1C с правом чтения
  ONEC_SALES_DOCUMENT       Document_РеализацияТоваровУслуг (УНФ: Document_РасходнаяНакладная)
  ONEC_AMOUNT_FIELD         СуммаДокумента
  ONEC_COUNTERPARTY_FIELD   Контрагент
  ONEC_COUNTERPARTY_CATALOG Catalog_Контрагенты
  ONEC_RETURN_DOCUMENT      (необязательно) Document_ВозвратТоваровОтПокупателя
  ONEC_CA_BUNDLE            (необязательно) сертификат для https с собственным CA
  ONEC_TASK_OBJECT          Task_ЗадачаИсполнителя
  ONEC_TASK_DUE_FIELD       СрокИсполнения
  ONEC_TASK_DONE_FIELD      Executed
  ONEC_TASK_PERFORMER_FIELD Исполнитель
  ONEC_USERS_CATALOG        Catalog_Пользователи

Команды (``python -m openjarvis_onec <команда>``):
  save-credentials          читает из stdin три строки: URL, пользователь, пароль
  check                     проверяет подключение
  revenue [С] [ПО] [--by counterparty|month|day]
  tasks [ДАТА] [--who ИМЯ]  задачи на дату (по умолчанию сегодня) и просроченные
  configure                 добавляет инструменты в [tools] enabled
"""

from __future__ import annotations

import calendar
import os
import sys
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from openjarvis.core.paths import get_config_dir, get_config_path
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

TOOL_NAME = "onec_revenue"
TASKS_TOOL_NAME = "onec_tasks"
EMPTY_DATE = "0001-01-01T00:00:00"  # так 1C отдаёт незаполненную дату
EMPTY_REF = "00000000-0000-0000-0000-000000000000"  # и незаполненную ссылку
SETTINGS_FILE_NAME = "onec.env"
PAGE_SIZE = 1000
GROUPINGS = ("none", "counterparty", "month", "day")

DEFAULTS = {
    "ONEC_SALES_DOCUMENT": "Document_РеализацияТоваровУслуг",
    "ONEC_AMOUNT_FIELD": "СуммаДокумента",
    "ONEC_COUNTERPARTY_FIELD": "Контрагент",
    "ONEC_COUNTERPARTY_CATALOG": "Catalog_Контрагенты",
    "ONEC_RETURN_DOCUMENT": "",
    "ONEC_CA_BUNDLE": "",
    "ONEC_TASK_OBJECT": "Task_ЗадачаИсполнителя",
    "ONEC_TASK_DUE_FIELD": "СрокИсполнения",
    "ONEC_TASK_DONE_FIELD": "Executed",
    "ONEC_TASK_PERFORMER_FIELD": "Исполнитель",
    "ONEC_USERS_CATALOG": "Catalog_Пользователи",
}


class OneCError(RuntimeError):
    """Понятная пользователю ошибка обращения к 1C."""


# --- настройки ---------------------------------------------------------------


def settings_file() -> Path:
    return get_config_dir() / SETTINGS_FILE_NAME


def _read_settings_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw in text.splitlines():
        if raw.strip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        # пароль не обрезаем: пробелы по краям могут быть его частью
        values[key] = value.rstrip("\r") if key == "ONEC_PASSWORD" else value.strip()
    return values


def load_settings() -> dict[str, str]:
    """Файл настроек, поверх него — переменные окружения."""
    values = {**DEFAULTS, **_read_settings_file(settings_file())}
    for key in ("ONEC_URL", "ONEC_USER", "ONEC_PASSWORD", *DEFAULTS):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def save_credentials(url: str, user: str, password: str) -> Path:
    url, user = url.strip(), user.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Адрес должен начинаться с http:// или https://")
    if not user or not password:
        raise ValueError("Пользователь и пароль не могут быть пустыми")
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    values = _read_settings_file(path)
    values.update(ONEC_URL=url.rstrip("/"), ONEC_USER=user, ONEC_PASSWORD=password)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("# Подключение OpenJarvis к 1C — не передавайте этот файл никому\n")
        for key, value in values.items():
            f.write(f"{key}={value}\n")
    path.chmod(0o600)
    return path


# --- клиент OData ------------------------------------------------------------


class OneCClient:
    def __init__(self, settings: dict[str, str]) -> None:
        missing = [
            k for k in ("ONEC_URL", "ONEC_USER", "ONEC_PASSWORD") if not settings.get(k)
        ]
        if missing:
            raise OneCError(
                f"Не настроено подключение к 1C ({', '.join(missing)}): ./onec.sh login"
            )
        self._base = settings["ONEC_URL"].rstrip("/")
        self._auth = httpx.BasicAuth(settings["ONEC_USER"], settings["ONEC_PASSWORD"])
        self._verify: Any = settings.get("ONEC_CA_BUNDLE") or True

    def get(
        self, resource: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # Кириллицу в имени объекта кодируем, скобки и кавычки guid'...' оставляем
        url = self._base + "/" + quote(resource, safe="()'=,-")
        try:
            resp = httpx.get(
                url,
                params={**(params or {}), "$format": "json"},
                auth=self._auth,
                verify=self._verify,
                timeout=60.0,
            )
        except httpx.HTTPError as exc:
            raise OneCError(
                f"Не удалось подключиться к 1C ({self._base}): {exc}"
            ) from exc
        if resp.status_code == 401:
            raise OneCError("1C отклонила вход: неверный пользователь или пароль")
        if resp.status_code == 404:
            raise OneCError(
                f"В OData нет объекта {resource}. Проверьте название в настройках или "
                "включите объект в состав стандартного интерфейса OData"
            )
        if not resp.is_success:
            raise OneCError(
                f"1C вернула ошибку {resp.status_code}: {_odata_error(resp)}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise OneCError(
                "1C ответила не JSON — проверьте, что адрес заканчивается на "
                "/odata/standard.odata"
            ) from exc

    def iter_entities(
        self, entity: str, *, filter: str, select: str
    ) -> Iterator[dict[str, Any]]:
        """Все записи постранично; дубли на границах страниц отбрасываются."""
        seen: set[str] = set()
        skip = 0
        while True:
            page = self.get(
                entity,
                {
                    "$filter": filter,
                    "$select": select,
                    "$orderby": "Ref_Key",
                    "$top": PAGE_SIZE,
                    "$skip": skip,
                },
            ).get("value", [])
            for row in page:
                key = row.get("Ref_Key", "")
                if key and key in seen:
                    continue
                seen.add(key)
                yield row
            if len(page) < PAGE_SIZE:
                return
            skip += PAGE_SIZE

    def description(self, catalog: str, ref_key: str) -> str:
        data = self.get(f"{catalog}(guid'{ref_key}')", {"$select": "Description"})
        return data.get("Description", "") or ref_key


def _odata_error(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("odata.error", {})
        return err.get("message", {}).get("value") or resp.text[:200]
    except (ValueError, AttributeError):
        return resp.text[:200]


# --- выручка -----------------------------------------------------------------


@dataclass
class RevenueReport:
    date_from: date
    date_to: date
    document: str
    total: Decimal = Decimal(0)
    count: int = 0
    returns: Decimal | None = None
    groups: dict[str, Decimal] = field(default_factory=dict)
    group_by: str = "none"

    @property
    def net(self) -> Decimal:
        return self.total - (self.returns or 0)


def _period_filter(date_from: date, date_to: date) -> str:
    return (
        f"Date ge datetime'{date_from.isoformat()}T00:00:00' and "
        f"Date le datetime'{date_to.isoformat()}T23:59:59' and "
        "Posted eq true and DeletionMark eq false"
    )


def _group_key(row: dict[str, Any], group_by: str, cp_field: str) -> str:
    if group_by == "counterparty":
        key = row.get(f"{cp_field}_Key") or ""
        return "" if key == EMPTY_REF else key
    day = str(row.get("Date", ""))[:10]
    return day[:7] if group_by == "month" else day


def revenue(
    date_from: date,
    date_to: date,
    *,
    group_by: str = "none",
    top: int = 10,
    settings: dict[str, str] | None = None,
) -> RevenueReport:
    if date_from > date_to:
        raise OneCError("Начало периода позже конца")
    if group_by not in GROUPINGS:
        raise OneCError(f"group_by должен быть одним из: {', '.join(GROUPINGS)}")
    settings = settings or load_settings()
    client = OneCClient(settings)
    doc, amount = settings["ONEC_SALES_DOCUMENT"], settings["ONEC_AMOUNT_FIELD"]
    cp_field = settings["ONEC_COUNTERPARTY_FIELD"]
    period = _period_filter(date_from, date_to)

    report = RevenueReport(date_from, date_to, doc, group_by=group_by)
    groups: dict[str, Decimal] = defaultdict(Decimal)
    for row in client.iter_entities(
        doc, filter=period, select=f"Ref_Key,Number,Date,{amount},{cp_field}_Key"
    ):
        value = Decimal(str(row.get(amount) or 0))
        report.total += value
        report.count += 1
        if group_by != "none":
            groups[_group_key(row, group_by, cp_field)] += value

    if settings.get("ONEC_RETURN_DOCUMENT"):
        report.returns = sum(
            (
                Decimal(str(row.get(amount) or 0))
                for row in client.iter_entities(
                    settings["ONEC_RETURN_DOCUMENT"],
                    filter=period,
                    select=f"Ref_Key,{amount}",
                )
            ),
            Decimal(0),
        )

    if group_by == "counterparty":
        # Имена — только для топа, чтобы не делать лишних запросов
        ranked = sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
        report.groups = {}
        catalog = settings["ONEC_COUNTERPARTY_CATALOG"]
        for key, value in ranked[:top]:
            name = client.description(catalog, key) if key else "(без контрагента)"
            report.groups[name] = report.groups.get(name, Decimal(0)) + value
        rest = sum((v for _, v in ranked[top:]), Decimal(0))
        if rest:
            report.groups[f"остальные ({len(ranked) - top})"] = rest
    else:
        report.groups = dict(sorted(groups.items()))
    return report


def _money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _kopecks(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def format_report(report: RevenueReport) -> str:
    period = f"{report.date_from:%d.%m.%Y}–{report.date_to:%d.%m.%Y}"
    lines = [
        (
            f"Выручка за {period} ({report.document}): {_money(report.total)} "
            f"(документов: {report.count})"
        )
    ]
    if report.returns is not None:
        lines.append(
            f"Возвраты: {_money(report.returns)}; за вычетом возвратов: {_money(report.net)}"
        )
    if report.groups:
        titles = {
            "counterparty": "По контрагентам",
            "month": "По месяцам",
            "day": "По дням",
        }
        lines.append(f"{titles[report.group_by]}:")
        for name, value in report.groups.items():
            share = f" ({value / report.total * 100:.1f}%)" if report.total else ""
            lines.append(f"  {name} — {_money(value)}{share}")
    lines.append(
        "Суммы по полю документа (обычно с НДС); учтены только проведённые документы."
    )
    return "\n".join(lines)


def parse_date(text: str) -> date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            # календарная дата без часового пояса — так и задумано
            return datetime.strptime(text.strip(), fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    raise OneCError(f"Не понял дату {text!r}: нужен формат ГГГГ-ММ-ДД или ДД.ММ.ГГГГ")


def current_month(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()  # noqa: DTZ011 — «текущий месяц» по местному времени
    last = calendar.monthrange(today.year, today.month)[1]
    return today.replace(day=1), today.replace(day=last)


# --- задачи CRM ----------------------------------------------------------------


@dataclass
class TaskItem:
    title: str
    due: datetime
    performer: str
    number: str = ""

    def overdue_on(self, day: date) -> bool:
        return self.due.date() < day


def tasks_due(
    day: date, *, performer: str = "", settings: dict[str, str] | None = None
) -> list[TaskItem]:
    """Невыполненные задачи со сроком не позже ``day`` (просроченные тоже)."""
    settings = settings or load_settings()
    client = OneCClient(settings)
    due, done = settings["ONEC_TASK_DUE_FIELD"], settings["ONEC_TASK_DONE_FIELD"]
    perf = settings["ONEC_TASK_PERFORMER_FIELD"]
    rows = client.iter_entities(
        settings["ONEC_TASK_OBJECT"],
        filter=(
            f"{done} eq false and DeletionMark eq false and "
            f"{due} gt datetime'{EMPTY_DATE}' and "
            f"{due} le datetime'{day.isoformat()}T23:59:59'"
        ),
        select=f"Ref_Key,Number,Description,{due},{perf}_Key",
    )
    names: dict[str, str] = {}
    items = []
    for row in rows:
        if str(row.get(due) or EMPTY_DATE).startswith(EMPTY_DATE[:10]):
            continue  # срок не задан (на случай, если сервер не отфильтровал)
        key = row.get(f"{perf}_Key") or ""
        if key == EMPTY_REF:
            key = ""
        if key and key not in names:
            names[key] = client.description(settings["ONEC_USERS_CATALOG"], key)
        items.append(
            TaskItem(
                title=(row.get("Description") or "(без названия)").strip(),
                due=datetime.fromisoformat(str(row[due])),
                performer=names.get(key, "(не назначен)"),
                number=str(row.get("Number") or "").strip(),
            )
        )
    if performer:
        needle = performer.casefold()
        items = [t for t in items if needle in t.performer.casefold()]
    return sorted(items, key=lambda t: (t.due, t.performer, t.title))


def format_tasks(items: list[TaskItem], day: date, performer: str = "") -> str:
    who = f" ({performer})" if performer else ""
    if not items:
        return f"На {day:%d.%m.%Y}{who} невыполненных задач нет, просроченных тоже."
    overdue = [t for t in items if t.overdue_on(day)]
    today = [t for t in items if not t.overdue_on(day)]
    lines = [
        (
            f"Задачи на {day:%d.%m.%Y}{who}: на сегодня {len(today)}, "
            f"просрочено {len(overdue)}."
        )
    ]
    for title, group, fmt in (
        ("Просрочено", overdue, "%d.%m.%Y"),
        ("На сегодня", today, "%H:%M"),
    ):
        if not group:
            continue
        lines.append(f"{title}:")
        for t in group:
            when = t.due.strftime(fmt)
            if when == "00:00":
                when = "в течение дня"
            number = f" №{t.number}" if t.number else ""
            lines.append(f"  [{when}] {t.title}{number} — {t.performer}")
    return "\n".join(lines)


def today() -> date:
    return date.today()  # noqa: DTZ011 — «сегодня» по местному времени


# --- инструменты для агентов Jarvis -------------------------------------------


class OneCRevenueTool(BaseTool):
    """Точная выручка из 1C за период."""

    tool_id = TOOL_NAME
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=TOOL_NAME,
            description=(
                "Get exact sales revenue from the user's 1C accounting system for a "
                "date range (sum of posted sales documents). Use it for any question "
                "about revenue, sales or 'выручка'. Report the numbers exactly as returned."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "date_from": {
                        "type": "string",
                        "description": "Start date YYYY-MM-DD (default: first day of this month).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End date YYYY-MM-DD, inclusive (default: last day of this month).",
                    },
                    "group_by": {
                        "type": "string",
                        "enum": list(GROUPINGS),
                        "description": "Optional breakdown: counterparty, month or day.",
                    },
                },
            },
            category="finance",
            timeout_seconds=120.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            default_from, default_to = current_month()
            date_from = (
                parse_date(params["date_from"])
                if params.get("date_from")
                else default_from
            )
            date_to = (
                parse_date(params["date_to"]) if params.get("date_to") else default_to
            )
            report = revenue(
                date_from, date_to, group_by=params.get("group_by") or "none"
            )
        except OneCError as exc:
            return ToolResult(
                tool_name=TOOL_NAME, content=f"Ошибка 1C: {exc}", success=False
            )
        return ToolResult(
            tool_name=TOOL_NAME,
            content=format_report(report),
            metadata={
                "total": _kopecks(report.total),
                "count": report.count,
                "returns": None if report.returns is None else _kopecks(report.returns),
                "date_from": report.date_from.isoformat(),
                "date_to": report.date_to.isoformat(),
            },
        )


class OneCTasksTool(BaseTool):
    """Задачи из CRM в 1C на дату."""

    tool_id = TASKS_TOOL_NAME
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=TASKS_TOOL_NAME,
            description=(
                "List open (not completed) tasks from the user's 1C CRM that are due "
                "on a given day, plus overdue ones. Use it for questions like 'what "
                "are my tasks today', 'задачи на сегодня', 'что просрочено'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Day YYYY-MM-DD (default: today).",
                    },
                    "performer": {
                        "type": "string",
                        "description": "Optional: only tasks of this person (part of the name).",
                    },
                },
            },
            category="crm",
            timeout_seconds=120.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        performer = (params.get("performer") or "").strip()
        try:
            day = parse_date(params["date"]) if params.get("date") else today()
            items = tasks_due(day, performer=performer)
        except OneCError as exc:
            return ToolResult(
                tool_name=TASKS_TOOL_NAME, content=f"Ошибка 1C: {exc}", success=False
            )
        return ToolResult(
            tool_name=TASKS_TOOL_NAME,
            content=format_tasks(items, day, performer),
            metadata={
                "date": day.isoformat(),
                "today": sum(not t.overdue_on(day) for t in items),
                "overdue": sum(t.overdue_on(day) for t in items),
            },
        )


TOOLS = {TOOL_NAME: OneCRevenueTool, TASKS_TOOL_NAME: OneCTasksTool}


def register() -> None:
    """Добавить инструменты в OpenJarvis (повторный вызов безопасен)."""
    for name, cls in TOOLS.items():
        if not ToolRegistry.contains(name):
            ToolRegistry.register_value(name, cls)


def configure() -> Path:
    """Добавить инструменты 1C в [tools] enabled, сохранив остальные."""
    import tomlkit
    from openjarvis.core.config import load_config

    path = get_config_path()
    doc = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()
    tools = doc.get("tools")
    if tools is None:
        tools = tomlkit.table()
        doc["tools"] = tools
    if "enabled" not in tools:
        tools["enabled"] = list(load_config().tools.enabled or [])
    for name in TOOLS:
        if name not in tools["enabled"]:
            tools["enabled"].append(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc))
    return path


# --- командная строка ----------------------------------------------------------


def _main(argv: list[str]) -> int:
    cmd, args = (argv[0] if argv else ""), argv[1:]
    if cmd == "save-credentials":
        lines = sys.stdin.read().split("\n")
        if len(lines) < 3:
            raise ValueError("Нужно три строки: URL, пользователь, пароль")
        path = save_credentials(lines[0], lines[1], lines[2])
        print(f"Настройки 1C сохранены: {path}")
        return 0
    if cmd == "configure":
        print(f"config.toml обновлён: {configure()}")
        return 0
    if cmd == "check":
        settings = load_settings()
        client = OneCClient(settings)
        probe = {"$top": 1, "$select": "Ref_Key"}
        client.get(settings["ONEC_SALES_DOCUMENT"], probe)
        print(f"Подключение к 1C работает ({settings['ONEC_URL']})")
        try:
            client.get(settings["ONEC_TASK_OBJECT"], probe)
            print(f"Задачи доступны ({settings['ONEC_TASK_OBJECT']})")
        except OneCError as exc:
            # выручка работает и без задач — не считаем это ошибкой подключения
            print(f"Задачи недоступны: {exc}")
        return 0
    if cmd == "revenue":
        group_by = "none"
        if "--by" in args:
            i = args.index("--by")
            group_by = args[i + 1] if i + 1 < len(args) else ""
            args = args[:i] + args[i + 2 :]
        date_from, date_to = current_month()
        if args:
            date_from = parse_date(args[0])
            date_to = parse_date(args[1]) if len(args) > 1 else date_from
        print(format_report(revenue(date_from, date_to, group_by=group_by)))
        return 0
    if cmd == "tasks":
        performer = ""
        if "--who" in args:
            i = args.index("--who")
            performer = args[i + 1] if i + 1 < len(args) else ""
            args = args[:i] + args[i + 2 :]
        day = parse_date(args[0]) if args else today()
        print(format_tasks(tasks_due(day, performer=performer), day, performer))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main(sys.argv[1:]))
    except (OneCError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        sys.exit(1)
