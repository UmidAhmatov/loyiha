"""Umumiy hook testlari. Ishga tushirish: uv run --project OpenJarvis pytest addons/"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HOOK_DIR = str(Path(__file__).parent)


@pytest.fixture
def addon_dir(tmp_path):
    """register() chaqirilganini faylga yozadigan soxta qo'shimcha modullar."""
    (tmp_path / "fake_addon.py").write_text(
        textwrap.dedent(
            """
            import os
            def register():
                with open(os.environ["MARKER"], "a") as f:
                    f.write("registered\\n")
            """
        )
    )
    (tmp_path / "broken_addon.py").write_text(
        "def register():\n    raise RuntimeError('boom')\n"
    )
    return tmp_path


def _run(code: str, addon_dir: Path) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([HOOK_DIR, str(addon_dir)]),
        "MARKER": str(addon_dir / "marker.txt"),
    }
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def _registrations(addon_dir: Path) -> int:
    marker = addon_dir / "marker.txt"
    return marker.read_text().count("registered") if marker.exists() else 0


def test_lazy_until_target_imported(addon_dir):
    out = _run(
        """
        import sys, openjarvis_addon_hook as h
        h.after_import("openjarvis.speech", "fake_addon")
        print("openjarvis" in sys.modules)
        """,
        addon_dir,
    )
    assert out.stdout.strip() == "False"
    assert _registrations(addon_dir) == 0


def test_registers_once_after_target_import(addon_dir):
    _run(
        """
        import openjarvis_addon_hook as h
        h.after_import("openjarvis.speech", "fake_addon")
        h.after_import("openjarvis.speech", "fake_addon")  # takror — e'tiborsiz
        import openjarvis.speech
        import openjarvis.speech.tts
        """,
        addon_dir,
    )
    assert _registrations(addon_dir) == 1


def test_target_already_imported_registers_immediately(addon_dir):
    _run(
        """
        import openjarvis.speech
        import openjarvis_addon_hook as h
        h.after_import("openjarvis.speech", "fake_addon")
        """,
        addon_dir,
    )
    assert _registrations(addon_dir) == 1


def test_broken_addon_does_not_break_target(addon_dir):
    out = _run(
        """
        import openjarvis_addon_hook as h
        h.after_import("openjarvis.tools", "broken_addon")
        import openjarvis.tools
        from openjarvis.core.registry import ToolRegistry
        print(ToolRegistry.contains("calculator"))
        """,
        addon_dir,
    )
    assert out.stdout.strip() == "True"
    assert "broken_addon modulini ulab bo'lmadi" in out.stderr
