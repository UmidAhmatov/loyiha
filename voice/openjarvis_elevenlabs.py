"""OpenJarvis uchun ElevenLabs ovoz (TTS) backend'i — qo'shimcha modul.

OpenJarvis'da ElevenLabs yo'q, shuning uchun bu modul uni ``TTSRegistry`` ga
``"elevenlabs"`` nomi bilan qo'shadi. Ro'yxatga olishni
``openjarvis_elevenlabs_hook`` bajaradi (``setup.sh --elevenlabs`` ikkalasini
ham OpenJarvis'ning .venv iga o'rnatadi).

API kaliti tartib bo'yicha qidiriladi:
  1. ``ELEVENLABS_API_KEY`` muhit o'zgaruvchisi;
  2. ``~/.openjarvis/elevenlabs.env`` fayli (``ELEVENLABS_API_KEY=...`` qatori).

Buyruqlar (``python -m openjarvis_elevenlabs <buyruq>``):
  save-key          kalitni stdin'dan o'qib, elevenlabs.env ga yozadi (chmod 600)
  configure [ID]    config.toml da ``[speech] tts_backend = "elevenlabs"`` qiladi
  voices            akkauntdagi ovozlar ro'yxati
  test [MATN]       qisqa namuna yaratib, mp3 faylga saqlaydi
"""

from __future__ import annotations

import io
import os
import re
import sys
import wave
from pathlib import Path

import httpx
from openjarvis.core.paths import get_config_dir, get_config_path
from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

BACKEND_ID = "elevenlabs"
API_BASE = "https://api.elevenlabs.io"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "George" — iliq, britancha erkak ovozi
DEFAULT_MODEL = "eleven_multilingual_v2"
KEY_FILE_NAME = "elevenlabs.env"

# OpenJarvis formati -> (ElevenLabs output_format, sample rate)
_FORMATS = {
    "mp3": ("mp3_44100_128", 44100),
    "wav": ("pcm_24000", 24000),  # xom PCM keladi, WAV sarlavhasini o'zimiz qo'shamiz
    "pcm": ("pcm_24000", 24000),
}
# Kokoro ovoz nomlari (masalan "bm_george") — OpenJarvis'ning standart voice_id si
_KOKORO_VOICE = re.compile(r"^[a-z]{2}_[a-z]+$")


def key_file() -> Path:
    return get_config_dir() / KEY_FILE_NAME


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text()
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip("'\"")
    return values


def _setting(name: str, default: str = "") -> str:
    return os.environ.get(name) or _read_env_file(key_file()).get(name) or default


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit little-endian
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    try:
        detail = resp.json().get("detail")
        message = detail.get("message") if isinstance(detail, dict) else detail
    except ValueError:  # javob JSON emas
        message = resp.text[:200]
    raise RuntimeError(f"ElevenLabs xatosi {resp.status_code}: {message}")


class ElevenLabsTTSBackend(TTSBackend):
    """ElevenLabs REST API orqali matnni ovozga aylantirish."""

    backend_id = BACKEND_ID

    def __init__(self, *, api_key: str = "", model: str = "") -> None:
        self._api_key = api_key or _setting("ELEVENLABS_API_KEY")
        self._model = model or _setting("ELEVENLABS_MODEL", DEFAULT_MODEL)
        # Masalan, EU hududi uchun: https://api.eu.residency.elevenlabs.io
        self._base = _setting("ELEVENLABS_API_BASE", API_BASE).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self._api_key}

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
    ) -> TTSResult:
        if not self._api_key:
            raise RuntimeError("ELEVENLABS_API_KEY topilmadi")
        if output_format not in _FORMATS:
            raise ValueError(f"Qo'llab-quvvatlanmaydigan format: {output_format!r}")
        if not voice_id or _KOKORO_VOICE.match(voice_id):
            voice_id = DEFAULT_VOICE

        el_format, sample_rate = _FORMATS[output_format]
        body: dict[str, object] = {"text": text, "model_id": self._model}
        if speed and speed != 1.0:
            # ElevenLabs faqat 0.7–1.2 oralig'ini qabul qiladi
            body["voice_settings"] = {"speed": min(max(speed, 0.7), 1.2)}

        resp = httpx.post(
            f"{self._base}/v1/text-to-speech/{voice_id}",
            params={"output_format": el_format},
            headers=self._headers(),
            json=body,
            timeout=120.0,
        )
        _raise_for_status(resp)
        audio = resp.content
        if output_format == "wav":
            audio = _pcm_to_wav(audio, sample_rate)

        return TTSResult(
            audio=audio,
            format=output_format,
            voice_id=voice_id,
            sample_rate=sample_rate,
            metadata={"backend": BACKEND_ID, "model": self._model},
        )

    def voices(self) -> list[dict[str, str]]:
        """``[{"voice_id": ..., "name": ...}, ...]`` ro'yxati."""
        if not self._api_key:
            return []
        resp = httpx.get(
            f"{self._base}/v1/voices", headers=self._headers(), timeout=30.0
        )
        _raise_for_status(resp)
        return [
            {"voice_id": v["voice_id"], "name": v.get("name", "")}
            for v in resp.json().get("voices", [])
        ]

    def available_voices(self) -> list[str]:
        return [v["voice_id"] for v in self.voices()]

    def health(self) -> bool:
        return bool(self._api_key)


def register() -> None:
    """Backend'ni OpenJarvis'ga qo'shish (qayta chaqirish xavfsiz)."""
    if not TTSRegistry.contains(BACKEND_ID):
        TTSRegistry.register_value(BACKEND_ID, ElevenLabsTTSBackend)
    # Boshqa backend'dan ElevenLabs'ga o'tilganda qaysi ovoz ishlatilishi
    from openjarvis.speech import _tts_discovery

    _tts_discovery.BACKEND_DEFAULT_VOICE.setdefault(BACKEND_ID, DEFAULT_VOICE)


# --- buyruqlar ---------------------------------------------------------------


def save_key(key: str) -> Path:
    key = key.strip()
    if not key:
        raise ValueError("Kalit bo'sh")
    path = key_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    values = _read_env_file(path)
    values["ELEVENLABS_API_KEY"] = key
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("# OpenJarvis ElevenLabs sozlamalari — bu faylni hech kimga bermang\n")
        for k, v in values.items():
            f.write(f"{k}={v}\n")
    path.chmod(0o600)
    return path


def configure(voice_id: str = "") -> Path:
    """config.toml da ElevenLabs'ni asosiy ovoz qilib belgilash.

    ``voice_id`` berilmasa va ElevenLabs allaqachon tanlangan bo'lsa,
    foydalanuvchi tanlagan ovoz saqlanib qoladi.
    """
    import tomlkit

    path = get_config_path()
    doc = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()
    speech = doc.get("speech")
    if speech is None:
        speech = tomlkit.table()
        doc["speech"] = speech
    # Morning digest o'z sozlamasiga ega — bo'lim mavjud bo'lsa, uni ham o'tkazamiz
    digest = doc.get("digest")
    for section in (speech, digest):
        if section is None:
            continue
        if voice_id or section.get("tts_backend") != BACKEND_ID:
            section["voice_id"] = voice_id or DEFAULT_VOICE
        section["tts_backend"] = BACKEND_ID
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc))
    return path


def _main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    args = argv[1:]
    if cmd == "save-key":
        path = save_key(sys.stdin.read())
        print(f"Kalit saqlandi: {path}")
        return 0
    if cmd == "configure":
        path = configure(args[0] if args else "")
        print(f"config.toml yangilandi: {path}")
        return 0
    backend = ElevenLabsTTSBackend()
    if not backend.health():
        print(f"ELEVENLABS_API_KEY topilmadi ({key_file()})", file=sys.stderr)
        return 1
    if cmd == "voices":
        for v in backend.voices():
            print(f"{v['voice_id']}  {v['name']}")
        return 0
    if cmd == "test":
        text = " ".join(args) or "Salom! Men Jarvisman. Ovoz sozlandi."
        from openjarvis.core.config import load_config

        speech = getattr(load_config(), "speech", None)
        voice = getattr(speech, "voice_id", "") if speech else ""
        result = backend.synthesize(text, voice_id=voice)
        out = get_config_dir() / "elevenlabs-test.mp3"
        out.write_bytes(result.audio)
        print(f"Namuna saqlandi: {out} (ovoz: {result.voice_id})")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main(sys.argv[1:]))
    except (RuntimeError, ValueError, httpx.HTTPError) as exc:
        print(f"Xato: {exc}", file=sys.stderr)
        sys.exit(1)
