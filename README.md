# OpenJarvis — kompyuterga o'rnatish qo'llanmasi

[OpenJarvis](https://github.com/open-jarvis/OpenJarvis) — Stanford'da ishlab chiqilgan
**shaxsiy AI yordamchi** freymvorki. Asosiy g'oya: sun'iy intellekt modeli sizning
kompyuteringizning o'zida ishlaydi (internetdagi serverga yuborilmaydi), bulutga
faqat kerak bo'lganda murojaat qilinadi.

Bu repoda OpenJarvis'ni o'rnatish uchun tayyor skriptlar bor:

| Fayl | Nima qiladi |
|---|---|
| [`setup.sh`](setup.sh) | OpenJarvis'ni to'liq o'rnatadi: uv, Python paketlar, Rust kengaytmasi, Ollama, model, konfiguratsiya |
| [`jarvis.sh`](jarvis.sh) | O'rnatilgan OpenJarvis'ni ishga tushiradi (kerak bo'lsa Ollama'ni ham) |
| [`voice.sh`](voice.sh) | ElevenLabs ovozini boshqaradi: kalit, ovoz tanlash, sinov |
| [`voice/`](voice/) | OpenJarvis uchun ElevenLabs ovoz moduli (OpenJarvis'da ElevenLabs yo'q) |

---

## 1. Talablar

| | Minimal | Tavsiya etiladi |
|---|---|---|
| Operatsion tizim | Linux, macOS, Windows 10/11 (WSL2 orqali) | Ubuntu 22.04+ / macOS 13+ |
| Operativ xotira (RAM) | 8 GB | 16 GB+ |
| Bo'sh disk joyi | 10 GB | 20 GB+ (katta modellar uchun) |
| Internet | Birinchi o'rnatishda kerak (≈3–5 GB yuklanadi) | — |

`git` va `curl` bo'lishi kerak. Qolgan hamma narsani (Python, uv, Rust, Ollama)
skript o'zi o'rnatadi.

Ubuntu/Debian'da `git` va `curl` yo'q bo'lsa, shuningdek Rust kengaytmasini qurish uchun:

```bash
sudo apt update && sudo apt install -y git curl build-essential
```

macOS'da:

```bash
xcode-select --install
```

---

## 2. O'rnatish

### A usul — shu repodagi skript bilan (tavsiya etiladi)

**Linux, macOS yoki WSL2 (Ubuntu) terminalida:**

```bash
git clone https://github.com/UmidAhmatov/loyiha.git
cd loyiha
./setup.sh
```

Skript quyidagilarni bajaradi:

1. `uv` (Python paket menejeri) ni o'rnatadi — kerakli Python versiyasini ham o'zi yuklaydi;
2. OpenJarvis kodini `loyiha/OpenJarvis/` papkasiga klonlaydi;
3. Python paketlarini `OpenJarvis/.venv` ichiga o'rnatadi (tizimdagi Python'ga tegmaydi);
4. Rust kengaytmasini quradi (xotira va xavfsizlik funksiyalari uchun, 3–10 daqiqa);
5. Ollama'ni o'rnatadi, ishga tushiradi va `qwen3.5:2b` modelini (~1.5 GB) yuklaydi;
6. `~/.openjarvis/config.toml` konfiguratsiyasini yozadi (mavjud bo'lsa, tegmaydi);
7. Node.js/npm versiyasini tekshiradi (grafik interfeys uchun);
8. `jarvis doctor` bilan hammasini tekshiradi.

Qo'shimcha parametrlar:

```bash
./setup.sh --model qwen3.5:4b   # boshqa (kattaroq) model
./setup.sh --no-ollama          # Ollama'siz (faqat bulutli API bilan ishlash uchun)
./setup.sh --no-rust            # Rust kengaytmasisiz (tezroq, lekin xotira funksiyalari o'chadi)
./setup.sh --dev                # dasturchilar uchun: pytest, ruff, pre-commit
./setup.sh --elevenlabs         # ElevenLabs ovozi (5-bo'limga qarang)
```

Skriptni istalgancha qayta ishga tushirish mumkin: u kodni yangilaydi (`git pull`)
va faqat yetishmayotgan qismlarni o'rnatadi.

### B usul — rasmiy bir qatorli o'rnatuvchi

Agar grafik interfeys va manba kodi kerak bo'lmasa, OpenJarvis jamoasining rasmiy skripti:

```bash
curl -fsSL https://open-jarvis.github.io/OpenJarvis/install.sh | bash
```

U hamma narsani `~/.openjarvis/` ga o'rnatadi va `jarvis` buyrug'ini PATH ga qo'shadi.
(Eslatma: rasmiy skript `root`/`sudo` bilan ishlamaydi va o'rnatish jarayoni haqida
anonim statistika yuboradi.)

### Windows

**Tavsiya etiladi — WSL2 (Windows ichidagi Linux):**

1. PowerShell'ni **administrator** sifatida oching va bajaring:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

2. Kompyuterni qayta yoqing, "Ubuntu" ilovasini oching, foydalanuvchi nomi/parol yarating.
3. Ubuntu terminalida yuqoridagi **A usul**ni bajaring.

**Muqobil — native Windows (PowerShell):**

Python 3.10–3.13 va `git` o'rnatilgan bo'lishi kerak (Python 3.14 hali ishlamaydi).

```powershell
irm https://open-jarvis.github.io/OpenJarvis/install.ps1 | iex
cd "$env:LOCALAPPDATA\OpenJarvis\src"
uv run jarvis
```

Ollama'ni alohida o'rnating: <https://ollama.com/download>, so'ng `ollama pull qwen3.5:2b`.

**Eng oson — desktop ilova:** `.exe` / `.dmg` / `.deb` / `.AppImage` faylini
[Releases](https://github.com/open-jarvis/OpenJarvis/releases) sahifasidan yuklab oling.

---

## 3. Ishga tushirish

```bash
./jarvis.sh                     # terminalda suhbat
./jarvis.sh gui                 # brauzerda grafik interfeys (http://127.0.0.1:5173)
./jarvis.sh ask "Salom, sen kimsan?"   # bitta savol berish
./jarvis.sh doctor              # nima ishlayapti, nima yo'qligini tekshirish
./jarvis.sh --help              # barcha buyruqlar
```

`jarvis.sh` ni istalgan papkadan chaqirish mumkin. Uni `jarvis` nomi bilan har
joydan ishlatish uchun (ixtiyoriy):

```bash
mkdir -p ~/.local/bin
ln -sf "$PWD/jarvis.sh" ~/.local/bin/jarvis
```

### Tayyor rejimlar (preset)

```bash
./jarvis.sh init --preset chat-simple --force      # oddiy suhbat, asboblarsiz
./jarvis.sh init --preset code-assistant --force   # kod yozish/ishga tushirish, fayllar, shell
./jarvis.sh init --preset deep-research --force    # hujjatlar bo'yicha chuqur tadqiqot
```

### Grafik interfeys (`gui`) uchun

Node.js **22.22+** va npm **11.19+** kerak. npm eski bo'lsa:

```bash
npm install -g npm@11
```

---

## 4. Modelni tanlash

Model qancha katta bo'lsa, shuncha aqlli, lekin ko'proq RAM talab qiladi:

| RAM | Model | Buyruq |
|---|---|---|
| 8 GB | `qwen3.5:2b` (standart) | `ollama pull qwen3.5:2b` |
| 16 GB | `qwen3.5:4b` | `ollama pull qwen3.5:4b` |
| 32 GB | `qwen3.5:9b` | `ollama pull qwen3.5:9b` |
| 64 GB | `qwen3.5:27b` | `ollama pull qwen3.5:27b` |

Yuklab olgach, `~/.openjarvis/config.toml` faylida modelni almashtiring:

```toml
[intelligence]
default_model = "qwen3.5:4b"
```

yoki suhbat paytida modelni tanlang: `./jarvis.sh --pick-model`.

### Bulutli model (ixtiyoriy)

Kompyuter kuchsiz bo'lsa, bulutli API kalitidan foydalanish mumkin. **Birinchi
o'rnatishdan oldin** kalitni o'rnating — `setup.sh` konfiguratsiyani avtomatik
bulutga sozlaydi:

```bash
export ANTHROPIC_API_KEY="..."      # yoki OPENAI_API_KEY / OPENROUTER_API_KEY / GOOGLE_API_KEY
./setup.sh --no-ollama
```

Keyinroq o'tish uchun: `./jarvis.sh init --force` (konfiguratsiyani qayta yaratadi).

---

## 5. Ovoz (ElevenLabs)

OpenJarvis'ning o'zida ElevenLabs yo'q (faqat Kokoro, OpenAI va Cartesia bor).
Shu repodagi [`voice/`](voice/) moduli uni `elevenlabs` nomi bilan qo'shadi:
OpenJarvis kodiga tegilmaydi, shuning uchun yangilanishlardan keyin ham ishlaydi.

### Sozlash

```bash
./setup.sh --elevenlabs
```

Skript API kalitini **yashirin** holda so'raydi: yozganingiz ekranda ko'rinmaydi va
buyruqlar tarixiga tushmaydi. Kalitni [elevenlabs.io](https://elevenlabs.io) saytida
(Settings → API Keys) yaratasiz. Keyin skript:

- kalitni `~/.openjarvis/elevenlabs.env` ga yozadi (faqat sizga o'qish huquqi, `chmod 600`);
- `config.toml` da `[speech] tts_backend = "elevenlabs"` qiladi (standart ovoz: George);
- mikrofon va karnay uchun paketlarni o'rnatadi;
- qisqa namuna yaratib, kalit ishlashini tekshiradi.

> **Kalit — parol kabi.** Uni chatga, repoga yoki skrinshotga qo'ymang. Tasodifan
> ko'rinib qolsa, ElevenLabs sahifasida o'chirib, yangisini yarating va
> `./voice.sh key` bilan almashtiring.

Keyingi `./setup.sh` ishga tushirishlarida ElevenLabs sozlamasi saqlanib qoladi.

### Ishlatish

```bash
./jarvis.sh chat --voice        # ovozli suhbat: mikrofon orqali gapirasiz, Jarvis ElevenLabs ovozida javob beradi
./jarvis.sh gui                 # grafik interfeysdagi ovoz ham ElevenLabs'dan foydalanadi
./voice.sh voices               # akkauntingizdagi ovozlar (ID va nomi)
./voice.sh voice <ID>           # Jarvis ovozini almashtirish
./voice.sh test "Salom!"        # namuna: ~/.openjarvis/elevenlabs-test.mp3
./voice.sh key                  # kalitni almashtirish
```

Qo'shimcha sozlamalar (`~/.openjarvis/elevenlabs.env` ga qator qo'shing):

```bash
ELEVENLABS_MODEL=eleven_multilingual_v2    # standart; boshqa model tanlash mumkin
ELEVENLABS_API_BASE=https://api.eu.residency.elevenlabs.io   # faqat EU hududidagi akkauntlar uchun
```

Eslatmalar:

- Har bir javob ElevenLabs tarifingizdagi belgilar limitidan sarflanadi (sinov namunasi ≈40 belgi).
- Qaysi model qaysi tillarni qo'llashini (jumladan, o'zbek tilini)
  [ElevenLabs hujjatlarida](https://elevenlabs.io/docs) tekshiring.
- Mikrofondagi gapni kompyuterning o'zidagi Whisper matnga aylantiradi (birinchi
  ishlatishda model yuklab olinadi). Aniqroq tanish uchun `config.toml` da
  `[speech]` bo'limiga `model = "small"` qo'shing.
- Linux'da mikrofon/karnay uchun: `sudo apt install -y libportaudio2`.

---

## 6. Muammolarni hal qilish

| Belgi | Yechim |
|---|---|
| `No inference engine available` | Ollama ishlamayapti: `ollama serve` (yoki `./jarvis.sh` o'zi ishga tushiradi). Model yuklanganini tekshiring: `ollama list` |
| `uv: command not found` | Yangi terminal oching yoki `export PATH="$HOME/.local/bin:$PATH"` |
| `npm error code EBADENGINE` (`gui` da) | `npm install -g npm@11`, Node.js 22.22+ ekanini tekshiring |
| Rust kengaytmasi qurilmadi | Ubuntu: `sudo apt install -y build-essential`, macOS: `xcode-select --install`, so'ng `./setup.sh` ni qayta ishga tushiring |
| `memory features unavailable` | Rust kengaytmasi yo'q — yuqoridagi qatorga qarang |
| Javob juda sekin | Kichikroq model tanlang (`qwen3.5:2b`) yoki bulutli modelga o'ting |
| `ElevenLabs xatosi 401: Invalid API key` | Kalit noto'g'ri yoki o'chirilgan: `./voice.sh key` |
| Xato xabarida `quota` so'zi bor | ElevenLabs belgilar limiti tugagan — tarifingizni tekshiring |
| `ElevenLabs xatosi 429` | Bir vaqtda juda ko'p so'rov — biroz kutib qayta urining |
| `PortAudio library not found` | `sudo apt install -y libportaudio2` |

Har qanday holatda birinchi qadam: `./jarvis.sh doctor`.

### Maxfiylik

OpenJarvis standart holatda anonim foydalanish statistikasini (suhbat matnisiz)
yuboradi. O'chirish uchun `~/.openjarvis/config.toml` ga qo'shing:

```toml
[analytics]
enabled = false
```

---

## 7. Yangilash va o'chirish

**Yangilash:**

```bash
./setup.sh
```

**O'chirish:**

```bash
rm -rf OpenJarvis ~/.openjarvis
```

(`~/.openjarvis` bilan birga ElevenLabs kaliti fayli ham o'chadi.)

Ollama va uv o'z joyida qoladi (ular boshqa dasturlar uchun ham kerak bo'lishi mumkin).
Modellarni o'chirish: `ollama rm qwen3.5:2b`.

---

## Sinovdan o'tkazilgan

Skriptlar toza Linux muhitida (Python 3.11, Node.js 22.22, uv 0.8) sinab ko'rildi:

- `setup.sh` noldan: kod klonlandi, Python paketlari va Rust kengaytmasi o'rnatildi,
  konfiguratsiya yozildi, `jarvis doctor` — 0 ta xato (≈3 daqiqa);
- `setup.sh` qayta ishga tushirilganda — 7 soniya, konfiguratsiyaga tegilmadi;
- `jarvis.sh gui` — grafik interfeys `http://127.0.0.1:5173` da ochildi (npm 11 bilan);
- OpenJarvis testlari: 8907 ta o'tdi; 3 tasi internet cheklovi tufayli o'tmadi
  (sinov muhitida tashqi saytlar yopiq edi).

ElevenLabs moduli: 14 ta test (`uv run --project OpenJarvis pytest voice/`), hamda
soxta ElevenLabs serveri bilan to'liq zanjir tekshirildi: `setup.sh --elevenlabs`,
`voice.sh` buyruqlari, `jarvis serve` ning `/v1/speech/synthesize` endpointi (GUI shu
orqali gapiradi) ElevenLabs'dan to'g'ri WAV qaytardi. Haqiqiy ElevenLabs API bilan
sinalmagan: `api.elevenlabs.io` sinov muhitida yopiq edi.

Sinov muhitida `ollama.com` va `huggingface.co` yopiq edi, shuning uchun Ollama'ni
haqiqatda yuklab olish va model bilan suhbat u yerda sinalmagan. Skriptlarning
Ollama bilan ishlash mantig'i (ishga tushirish, modelni yuklash, konfiguratsiyaga
yozish) soxta Ollama bilan tekshirildi. Buyruqlarning o'zi rasmiy OpenJarvis
o'rnatuvchisidagi bilan bir xil.

## Havolalar

- Rasmiy hujjatlar: <https://open-jarvis.github.io/OpenJarvis/>
- GitHub: <https://github.com/open-jarvis/OpenJarvis>
- Discord: <https://discord.gg/CMVBmDQ5Fj>
