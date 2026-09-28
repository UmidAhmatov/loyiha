"""ElevenLabs qo'shimcha modulining testlari.

Ishga tushirish (loyiha papkasidan):
    uv run --project OpenJarvis pytest voice/
"""

import io
import json
import os
import stat
import subprocess
import sys
import wave
from pathlib import Path

import httpx
import pytest
import respx

sys.path.insert(0, str(Path(__file__).parent))

import openjarvis_elevenlabs as el

TTS_URL = f"{el.API_BASE}/v1/text-to-speech/{el.DEFAULT_VOICE}"
VOICE_DIR = str(Path(__file__).parent)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path / "ojhome"))
    for name in (
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_MODEL",
        "ELEVENLABS_API_BASE",
        "XDG_DATA_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / "ojhome"


@respx.mock
def test_synthesize_mp3_request():
    route = respx.post(TTS_URL).mock(
        return_value=httpx.Response(200, content=b"ID3mp3")
    )
    result = el.ElevenLabsTTSBackend(api_key="sk_test").synthesize("Salom")

    req = route.calls.last.request
    assert req.headers["xi-api-key"] == "sk_test"
    assert req.url.params["output_format"] == "mp3_44100_128"
    assert json.loads(req.content) == {"text": "Salom", "model_id": el.DEFAULT_MODEL}
    assert result.audio == b"ID3mp3"
    assert (result.format, result.sample_rate, result.voice_id) == (
        "mp3",
        44100,
        el.DEFAULT_VOICE,
    )


@respx.mock
def test_synthesize_wav_wraps_pcm_and_clamps_speed():
    pcm = b"\x01\x00" * 2400  # 0.1 s
    route = respx.post(TTS_URL).mock(return_value=httpx.Response(200, content=pcm))
    result = el.ElevenLabsTTSBackend(api_key="k").synthesize(
        "Salom", output_format="wav", speed=1.5
    )

    req = route.calls.last.request
    assert req.url.params["output_format"] == "pcm_24000"
    assert json.loads(req.content)["voice_settings"] == {"speed": 1.2}
    with wave.open(io.BytesIO(result.audio)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
        assert w.readframes(w.getnframes()) == pcm
    assert result.sample_rate == 24000


@respx.mock
def test_kokoro_voice_id_falls_back_to_default():
    route = respx.post(TTS_URL).mock(return_value=httpx.Response(200, content=b"x"))
    el.ElevenLabsTTSBackend(api_key="k").synthesize("a", voice_id="bm_george")
    assert route.called


@respx.mock
def test_custom_voice_id_is_used():
    route = respx.post(f"{el.API_BASE}/v1/text-to-speech/AbCdEfGhIjKlMnOpQrSt").mock(
        return_value=httpx.Response(200, content=b"x")
    )
    el.ElevenLabsTTSBackend(api_key="k").synthesize(
        "a", voice_id="AbCdEfGhIjKlMnOpQrSt"
    )
    assert route.called


@respx.mock
def test_api_error_message_does_not_leak_key():
    respx.post(TTS_URL).mock(
        return_value=httpx.Response(
            401,
            json={
                "detail": {"status": "invalid_api_key", "message": "Invalid API key"}
            },
        )
    )
    with pytest.raises(RuntimeError) as exc:
        el.ElevenLabsTTSBackend(api_key="sk_secret").synthesize("a")
    assert "401" in str(exc.value) and "Invalid API key" in str(exc.value)
    assert "sk_secret" not in str(exc.value)


def test_unsupported_format():
    with pytest.raises(ValueError):
        el.ElevenLabsTTSBackend(api_key="k").synthesize("a", output_format="ogg")


def test_key_lookup_env_then_file(monkeypatch):
    assert not el.ElevenLabsTTSBackend().health()
    el.save_key("sk_from_file\n")
    assert el.ElevenLabsTTSBackend()._api_key == "sk_from_file"
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_from_env")
    assert el.ElevenLabsTTSBackend()._api_key == "sk_from_env"


def test_save_key_permissions_and_keeps_other_settings(_isolated_home):
    _isolated_home.mkdir(parents=True)
    el.key_file().write_text(
        "ELEVENLABS_MODEL=eleven_flash_v2_5\nELEVENLABS_API_KEY=old\n"
    )
    path = el.save_key("sk_new")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    values = el._read_env_file(path)
    assert values == {
        "ELEVENLABS_MODEL": "eleven_flash_v2_5",
        "ELEVENLABS_API_KEY": "sk_new",
    }
    assert el.ElevenLabsTTSBackend()._model == "eleven_flash_v2_5"


def test_save_key_rejects_empty():
    with pytest.raises(ValueError):
        el.save_key("  \n")


def test_configure_updates_config_and_keeps_rest(_isolated_home):
    import tomlkit

    _isolated_home.mkdir(parents=True)
    cfg = _isolated_home / "config.toml"
    cfg.write_text(
        '# mening izohim\n[intelligence]\ndefault_model = "qwen3.5:2b"\n\n'
        '[speech]\ntts_backend = "kokoro"\nvoice_id = "bm_george"\nvoice_speed = 1.1\n'
    )
    el.configure()
    text = cfg.read_text()
    doc = tomlkit.parse(text)
    assert "# mening izohim" in text
    assert doc["intelligence"]["default_model"] == "qwen3.5:2b"
    assert doc["speech"]["tts_backend"] == "elevenlabs"
    assert doc["speech"]["voice_id"] == el.DEFAULT_VOICE
    assert doc["speech"]["voice_speed"] == 1.1
    assert "digest" not in doc

    cfg.write_text(text + '\n[digest]\ntts_backend = "cartesia"\n')
    el.configure("AbCdEfGhIjKlMnOpQrSt")
    doc = tomlkit.parse(cfg.read_text())
    assert doc["speech"]["voice_id"] == "AbCdEfGhIjKlMnOpQrSt"
    assert doc["digest"]["tts_backend"] == "elevenlabs"
    assert doc["digest"]["voice_id"] == "AbCdEfGhIjKlMnOpQrSt"

    # setup.sh qayta ishga tushirilganda tanlangan ovoz saqlanadi
    el.configure()
    doc = tomlkit.parse(cfg.read_text())
    assert doc["speech"]["voice_id"] == "AbCdEfGhIjKlMnOpQrSt"
    assert doc["digest"]["voice_id"] == "AbCdEfGhIjKlMnOpQrSt"


def test_config_loader_accepts_elevenlabs(_isolated_home):
    from openjarvis.core.config import load_config
    from openjarvis.speech._tts_discovery import voice_preferences

    el.configure()
    backend, voice, _ = voice_preferences(load_config(_isolated_home / "config.toml"))
    assert (backend, voice) == ("elevenlabs", el.DEFAULT_VOICE)


@respx.mock
def test_registered_backend_used_by_discovery_and_tool(monkeypatch, tmp_path):
    from openjarvis.core.registry import TTSRegistry
    from openjarvis.speech._tts_discovery import default_voice_for, get_tts_backend
    from openjarvis.tools.text_to_speech import TextToSpeechTool

    el.register()
    el.register()  # qayta chaqirish xavfsiz
    assert TTSRegistry.contains("elevenlabs")
    assert default_voice_for("elevenlabs") == el.DEFAULT_VOICE

    fallback = get_tts_backend("elevenlabs")  # kalitsiz — ElevenLabs tanlanmaydi
    assert fallback is None or fallback.backend_id != "elevenlabs"
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert get_tts_backend("elevenlabs").backend_id == "elevenlabs"

    respx.post(TTS_URL).mock(return_value=httpx.Response(200, content=b"ID3mp3"))
    result = TextToSpeechTool().execute(
        text="Salom", backend="elevenlabs", output_dir=str(tmp_path)
    )
    assert result.success, result.content
    assert next(tmp_path.glob("*.mp3")).read_bytes() == b"ID3mp3"


def _run_python(code: str, **env: str) -> str:
    full_env = {**os.environ, "PYTHONPATH": VOICE_DIR, **env}
    out = subprocess.run(
        [sys.executable, "-c", code],
        env=full_env,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def test_hook_is_lazy():
    code = "import openjarvis_elevenlabs_hook, sys; print('openjarvis' in sys.modules)"
    assert _run_python(code) == "False"


def test_hook_registers_on_speech_import(_isolated_home):
    code = (
        "import openjarvis_elevenlabs_hook\n"
        "from openjarvis.speech._tts_discovery import get_tts_backend\n"
        "print(get_tts_backend('elevenlabs').backend_id)\n"
    )
    out = _run_python(code, ELEVENLABS_API_KEY="k", OPENJARVIS_HOME=str(_isolated_home))
    assert out == "elevenlabs"
