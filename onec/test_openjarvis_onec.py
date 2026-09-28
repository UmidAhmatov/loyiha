"""Тесты модуля 1C. Запуск из папки loyiha: uv run --project OpenJarvis pytest onec/"""

import base64
import json
import os
import stat
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
import respx

sys.path.insert(0, str(Path(__file__).parent))

import openjarvis_onec as onec

BASE = "http://1c.local/buh/odata/standard.odata"
USER, PASSWORD = "Бухгалтер", " p@ss=word "
CP_ROMASHKA = "11111111-1111-1111-1111-111111111111"
CP_LUTIK = "22222222-2222-2222-2222-222222222222"
CP_OTHER = "33333333-3333-3333-3333-333333333333"
ONEC_DIR = str(Path(__file__).parent)
ADDONS_DIR = str(Path(__file__).parent.parent / "addons")


def _doc(n, day, amount, cp):
    return {
        "Ref_Key": f"doc-{n:04d}",
        "Number": f"0000-{n:06d}",
        "Date": f"{day}T12:00:00",
        "СуммаДокумента": amount,
        "Контрагент_Key": cp,
    }


SALES = [
    _doc(1, "2026-09-01", 1000.10, CP_ROMASHKA),
    _doc(2, "2026-09-15", 2500, CP_LUTIK),
    _doc(3, "2026-09-30", 499.90, CP_ROMASHKA),
    _doc(4, "2026-10-02", 700, CP_OTHER),
]
RETURNS = [{"Ref_Key": "ret-1", "СуммаДокумента": 300}]
NAMES = {CP_ROMASHKA: "ООО Ромашка", CP_LUTIK: "ИП Лютик", CP_OTHER: "АО Прочие"}


U_IVAN = "aaaaaaaa-0000-0000-0000-000000000001"
U_MARIA = "aaaaaaaa-0000-0000-0000-000000000002"
USERS = {U_IVAN: "Иванов Иван", U_MARIA: "Петрова Мария"}


def _task(n, due, performer, *, done=False, title=None):
    return {
        "Ref_Key": f"task-{n}",
        "Number": f"{n:09d}",
        "Description": title or f"Задача {n}",
        "СрокИсполнения": due,
        "Исполнитель_Key": performer,
        "Executed": done,
        "DeletionMark": False,
    }


TASKS = [
    _task(1, "2026-09-28T10:30:00", U_IVAN, title="Позвонить ООО Ромашка"),
    _task(2, "2026-09-25T00:00:00", U_MARIA, title="Отправить КП"),
    _task(3, "2026-09-28T00:00:00", U_MARIA, title="Подготовить договор"),
    _task(4, "2026-09-28T09:00:00", U_IVAN, done=True),  # выполнена
    _task(5, "2026-09-29T09:00:00", U_IVAN),  # завтра
    _task(6, "0001-01-01T00:00:00", U_IVAN),  # без срока
    # незаполненная ссылка в 1C — нулевой GUID
    _task(7, "2026-09-28T15:00:00", onec.EMPTY_REF, title="Разобрать почту"),
]


def _filter_tasks(params):
    """Эмулирует фильтр OData, который строит модуль (и проверяет, что он такой)."""
    if "$filter" not in params:  # проверка доступа (onec.sh check)
        return TASKS[: int(params.get("$top", len(TASKS)))]
    flt = params["$filter"]
    assert flt.startswith("Executed eq false and DeletionMark eq false and ")
    assert "СрокИсполнения gt datetime'0001-01-01T00:00:00'" in flt
    limit = flt.split("СрокИсполнения le datetime'")[1].split("'")[0]
    assert (
        params["$select"] == "Ref_Key,Number,Description,СрокИсполнения,Исполнитель_Key"
    )
    return [
        t
        for t in TASKS
        if not t["Executed"] and onec.EMPTY_DATE < t["СрокИсполнения"] <= limit
    ]


class Fake1C:
    """Минимальный OData-сервер 1C: авторизация, $top/$skip, справочник контрагентов."""

    def __init__(self, sales=SALES, returns=RETURNS):
        self.sales, self.returns = sales, returns
        self.requests: list[httpx.Request] = []
        self.user_lookups = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        expected = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
        if request.headers.get("authorization") != expected:
            return httpx.Response(401, text="Unauthorized")
        resource = unquote(request.url.path).removeprefix("/buh/odata/standard.odata/")
        params = request.url.params
        assert params["$format"] == "json"
        if resource.startswith("Catalog_Контрагенты(guid'"):
            key = resource.split("'")[1]
            return httpx.Response(200, json={"Description": NAMES[key]})
        if resource.startswith("Catalog_Пользователи(guid'"):
            self.user_lookups += 1
            return httpx.Response(
                200, json={"Description": USERS[resource.split("'")[1]]}
            )
        if resource == "Task_ЗадачаИсполнителя":
            return httpx.Response(200, json={"value": _filter_tasks(params)})
        rows = {
            "Document_РеализацияТоваровУслуг": self.sales,
            "Document_ВозвратТоваровОтПокупателя": self.returns,
        }.get(resource)
        if rows is None:
            return httpx.Response(
                404, json={"odata.error": {"message": {"value": "Not found"}}}
            )
        # Сервер фильтрует по датам сам — здесь достаточно отбросить октябрь
        if "2026-09-30T23:59:59" in params.get("$filter", ""):
            rows = [r for r in rows if not str(r.get("Date", "")).startswith("2026-10")]
        skip, top = int(params.get("$skip", 0)), int(params.get("$top", 10**6))
        return httpx.Response(200, json={"value": rows[skip : skip + top]})


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    home = tmp_path / "ojhome"
    monkeypatch.setenv("OPENJARVIS_HOME", str(home))
    for key in (
        "ONEC_URL",
        "ONEC_USER",
        "ONEC_PASSWORD",
        "XDG_DATA_HOME",
        *onec.DEFAULTS,
    ):
        monkeypatch.delenv(key, raising=False)
    return home


@pytest.fixture
def fake1c():
    onec.save_credentials(BASE, USER, PASSWORD)
    fake = Fake1C()
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="1c.local").mock(side_effect=fake)
        yield fake


SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def test_revenue_total_and_request(fake1c):
    report = onec.revenue(*SEPT)
    assert report.total == Decimal("4000.00")
    assert report.count == 3
    assert report.returns is None

    params = fake1c.requests[0].url.params
    assert params["$filter"] == (
        "Date ge datetime'2026-09-01T00:00:00' and Date le datetime'2026-09-30T23:59:59' "
        "and Posted eq true and DeletionMark eq false"
    )
    assert params["$select"] == "Ref_Key,Number,Date,СуммаДокумента,Контрагент_Key"


def test_paging_and_duplicates(fake1c, monkeypatch):
    monkeypatch.setattr(onec, "PAGE_SIZE", 2)
    # дубль документа на границе страниц не должен посчитаться дважды
    fake1c.sales = [*SALES[:2], SALES[1], SALES[2]]
    report = onec.revenue(*SEPT)
    assert (report.count, report.total) == (3, Decimal("4000.00"))
    skips = [r.url.params["$skip"] for r in fake1c.requests]
    assert skips == ["0", "2", "4"]


def test_group_by_counterparty_top_and_rest(fake1c):
    report = onec.revenue(*SEPT, group_by="counterparty", top=1)
    assert report.groups == {
        "ИП Лютик": Decimal(2500),
        "остальные (1)": Decimal("1500.00"),
    }


def test_group_by_month_and_day(fake1c):
    assert onec.revenue(*SEPT, group_by="month").groups == {
        "2026-09": Decimal("4000.00")
    }
    days = onec.revenue(*SEPT, group_by="day").groups
    assert list(days) == ["2026-09-01", "2026-09-15", "2026-09-30"]


def test_returns_subtracted(fake1c, monkeypatch):
    monkeypatch.setenv("ONEC_RETURN_DOCUMENT", "Document_ВозвратТоваровОтПокупателя")
    report = onec.revenue(*SEPT)
    assert report.returns == Decimal(300)
    assert report.net == Decimal("3700.00")
    assert "за вычетом возвратов: 3 700,00" in onec.format_report(report)


def test_format_report(fake1c):
    text = onec.format_report(onec.revenue(*SEPT, group_by="counterparty"))
    assert "Выручка за 01.09.2026–30.09.2026" in text
    assert "4 000,00 (документов: 3)" in text
    assert "ИП Лютик — 2 500,00 (62.5%)" in text
    assert "ООО Ромашка — 1 500,00 (37.5%)" in text


def test_wrong_password(fake1c, monkeypatch):
    monkeypatch.setenv("ONEC_PASSWORD", "wrong")
    with pytest.raises(onec.OneCError, match="неверный пользователь или пароль"):
        onec.revenue(*SEPT)


def test_unknown_document(fake1c, monkeypatch):
    monkeypatch.setenv("ONEC_SALES_DOCUMENT", "Document_РасходнаяНакладная")
    with pytest.raises(onec.OneCError, match="нет объекта Document_РасходнаяНакладная"):
        onec.revenue(*SEPT)


def test_not_configured():
    with pytest.raises(onec.OneCError, match="./onec.sh login"):
        onec.revenue(*SEPT)


@respx.mock
def test_connection_error_and_non_json():
    onec.save_credentials(BASE, USER, PASSWORD)
    respx.get(url__startswith=BASE).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(onec.OneCError, match="Не удалось подключиться"):
        onec.revenue(*SEPT)
    respx.get(url__startswith=BASE).mock(
        return_value=httpx.Response(200, text="<html>")
    )
    with pytest.raises(onec.OneCError, match="odata/standard.odata"):
        onec.revenue(*SEPT)


def test_invalid_period_and_grouping(fake1c):
    with pytest.raises(onec.OneCError, match="позже"):
        onec.revenue(date(2026, 9, 30), date(2026, 9, 1))
    with pytest.raises(onec.OneCError, match="group_by"):
        onec.revenue(*SEPT, group_by="week")


def test_save_credentials_file(_home):
    path = onec.save_credentials(BASE + "/", " " + USER + " ", PASSWORD)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    settings = onec.load_settings()
    assert settings["ONEC_URL"] == BASE
    assert settings["ONEC_USER"] == USER
    assert settings["ONEC_PASSWORD"] == PASSWORD  # пробелы и "=" сохранены
    with pytest.raises(ValueError):
        onec.save_credentials("1c.local", USER, PASSWORD)
    with pytest.raises(ValueError):
        onec.save_credentials(BASE, USER, "")


def test_save_credentials_keeps_custom_settings(_home):
    onec.save_credentials(BASE, USER, PASSWORD)
    with onec.settings_file().open("a", encoding="utf-8") as f:
        f.write("ONEC_SALES_DOCUMENT=Document_РасходнаяНакладная \n")
    onec.save_credentials(BASE, "Директор", "x")
    settings = onec.load_settings()
    assert settings["ONEC_SALES_DOCUMENT"] == "Document_РасходнаяНакладная"
    assert settings["ONEC_USER"] == "Директор"


def test_parse_date_and_current_month():
    assert (
        onec.parse_date("2026-09-05")
        == onec.parse_date("05.09.2026")
        == date(2026, 9, 5)
    )
    with pytest.raises(onec.OneCError):
        onec.parse_date("сентябрь")
    assert onec.current_month(date(2028, 2, 10)) == (
        date(2028, 2, 1),
        date(2028, 2, 29),
    )


def test_tool_success_and_error(fake1c):
    tool = onec.OneCRevenueTool()
    assert tool.spec.name == "onec_revenue"
    result = tool.execute(date_from="2026-09-01", date_to="2026-09-30")
    assert result.success
    assert result.metadata["total"] == "4000.00"
    assert "4 000,00" in result.content

    bad = tool.execute(date_from="вчера")
    assert not bad.success and bad.content.startswith("Ошибка 1C:")


def test_configure_tools_enabled(_home):
    import tomlkit

    _home.mkdir(parents=True)
    cfg = _home / "config.toml"
    cfg.write_text('# моё\n[tools]\nenabled = ["web_search", "file_read"]\n')
    onec.configure()
    onec.configure()  # повторно — без дублей
    doc = tomlkit.parse(cfg.read_text())
    assert list(doc["tools"]["enabled"]) == [
        "web_search",
        "file_read",
        "onec_revenue",
        "onec_tasks",
    ]
    assert "# моё" in cfg.read_text()


def test_configure_without_tools_section_keeps_defaults(_home):
    import tomlkit
    from openjarvis.core.config import load_config

    defaults = list(load_config().tools.enabled or [])
    onec.configure()
    enabled = list(
        tomlkit.parse((_home / "config.toml").read_text())["tools"]["enabled"]
    )
    assert enabled == [*defaults, "onec_revenue", "onec_tasks"]


def test_cli_revenue(fake1c, capsys):
    assert onec._main(["revenue", "01.09.2026", "30.09.2026", "--by", "month"]) == 0
    out = capsys.readouterr().out
    assert "По месяцам:" in out and "2026-09 — 4 000,00" in out


def test_hook_registers_tool_on_tools_import(_home):
    # setup.sh yozadigan .pth qatori bilan bir xil
    code = (
        "import openjarvis_addon_hook; "
        "openjarvis_addon_hook.after_import('openjarvis.tools', 'openjarvis_onec')\n"
        "import openjarvis.tools\n"
        "from openjarvis.core.registry import ToolRegistry\n"
        "print(ToolRegistry.contains('onec_revenue'))\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([ONEC_DIR, ADDONS_DIR]),
        "OPENJARVIS_HOME": str(_home),
    }
    out = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "True"


def test_spec_is_valid_json_schema():
    json.dumps(onec.OneCRevenueTool().spec.parameters)  # сериализуется для LLM
    fn = onec.OneCRevenueTool().to_openai_function()
    assert fn["function"]["name"] == "onec_revenue"


# --- задачи CRM ---------------------------------------------------------------

DAY = date(2026, 9, 28)


def test_tasks_due_today_and_overdue(fake1c):
    items = onec.tasks_due(DAY)
    assert [t.title for t in items] == [
        "Отправить КП",  # просрочена (25.09)
        "Подготовить договор",  # сегодня, без времени
        "Позвонить ООО Ромашка",  # сегодня 10:30
        "Разобрать почту",  # сегодня 15:00, без исполнителя
    ]
    assert [t.overdue_on(DAY) for t in items] == [True, False, False, False]
    assert items[-1].performer == "(не назначен)"
    assert fake1c.user_lookups == 2  # имя каждого пользователя — один запрос


def test_tasks_filter_by_performer(fake1c):
    items = onec.tasks_due(DAY, performer="петрова")
    assert {t.performer for t in items} == {"Петрова Мария"}
    assert len(items) == 2


def test_format_tasks(fake1c):
    text = onec.format_tasks(onec.tasks_due(DAY), DAY)
    assert text.splitlines()[0] == "Задачи на 28.09.2026: на сегодня 3, просрочено 1."
    assert "Просрочено:\n  [25.09.2026] Отправить КП №000000002 — Петрова Мария" in text
    assert "  [в течение дня] Подготовить договор №000000003 — Петрова Мария" in text
    assert "  [10:30] Позвонить ООО Ромашка №000000001 — Иванов Иван" in text
    assert "Задача 5" not in text and "Задача 4" not in text and "Задача 6" not in text


def test_format_no_tasks():
    assert onec.format_tasks([], DAY, "Иванов") == (
        "На 28.09.2026 (Иванов) невыполненных задач нет, просроченных тоже."
    )


def test_tasks_custom_object_missing(fake1c, monkeypatch):
    monkeypatch.setenv("ONEC_TASK_OBJECT", "Task_ЗадачаCRM")
    with pytest.raises(onec.OneCError, match="нет объекта Task_ЗадачаCRM"):
        onec.tasks_due(DAY)


def test_tasks_tool(fake1c, monkeypatch):
    tool = onec.OneCTasksTool()
    assert tool.to_openai_function()["function"]["name"] == "onec_tasks"
    result = tool.execute(date="2026-09-28")
    assert result.success
    assert result.metadata == {"date": "2026-09-28", "today": 3, "overdue": 1}

    monkeypatch.setattr(onec, "today", lambda: DAY)
    assert tool.execute().metadata["date"] == "2026-09-28"  # по умолчанию — сегодня
    assert not tool.execute(date="завтра").success


def test_register_both_tools():
    from openjarvis.core.registry import ToolRegistry

    onec.register()
    onec.register()
    assert ToolRegistry.contains("onec_revenue")
    assert ToolRegistry.contains("onec_tasks")


def test_cli_tasks_and_check(fake1c, capsys):
    assert onec._main(["tasks", "28.09.2026", "--who", "Иванов"]) == 0
    out = capsys.readouterr().out
    assert "на сегодня 1, просрочено 0" in out and "Позвонить ООО Ромашка" in out

    assert onec._main(["check"]) == 0
    out = capsys.readouterr().out
    assert "Подключение к 1C работает" in out and "Задачи доступны" in out


def test_check_without_tasks_object(fake1c, capsys, monkeypatch):
    monkeypatch.setenv("ONEC_TASK_OBJECT", "Task_Нет")
    assert onec._main(["check"]) == 0  # выручка работает — это не ошибка
    assert "Задачи недоступны" in capsys.readouterr().out
