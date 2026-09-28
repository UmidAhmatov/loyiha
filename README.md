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
| [`onec.sh`](onec.sh), [`onec/`](onec/) | 1C: выручка через OData — команда и инструмент для Jarvis |
| [`addons/`](addons/) | Qo'shimcha modullarni OpenJarvis'ga ulaydigan umumiy hook |

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
./setup.sh --onec               # 1C: выручка (раздел 6)
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

## 6. 1C: выручка и задачи CRM

В OpenJarvis нет подключения к 1C, поэтому модуль [`onec/`](onec/) добавляет два
инструмента. Оба работают через стандартный интерфейс OData:

- `onec_revenue` — выручка. Читает проведённые документы реализации и **сам считает
  суммы**: модель получает готовые цифры и ничего не складывает, поэтому числа точные.
- `onec_tasks` — задачи CRM. Показывает невыполненные задачи со сроком на сегодня (или
  на указанную дату) и просроченные, с исполнителями.

### Что нужно в 1C

1. База опубликована на веб-сервере (Apache или IIS) с включённым OData. Адрес вида
   `http://сервер/база/odata/standard.odata`.
2. В состав стандартного интерфейса OData включены документ реализации, справочник
   контрагентов, а для задач — задача `ЗадачаИсполнителя` и справочник `Пользователи`. Это делает администратор 1C, например обработкой «Настройка
   автоматического REST-сервиса» или методом `УстановитьСоставСтандартногоИнтерфейсаOData`.
3. Отдельный пользователь 1C с правами **только на чтение**. Не используйте
   администратора.

Проверить вручную: откройте в браузере
`http://сервер/база/odata/standard.odata/Document_РеализацияТоваровУслуг?$top=1&$format=json`
— после ввода логина должен появиться JSON.

### Подключение

```bash
./setup.sh --onec
```

Скрипт спросит адрес OData, пользователя и пароль (пароль на экране не отображается).
Данные сохраняются в `~/.openjarvis/onec.env` с правами `600` и никуда не
отправляются. Затем скрипт проверяет подключение.

### Использование

```bash
./onec.sh revenue                                           # текущий месяц
./onec.sh revenue 01.09.2026 30.09.2026                     # период
./onec.sh revenue 01.09.2026 30.09.2026 --by counterparty   # по контрагентам (также month, day)
./onec.sh tasks                                             # задачи на сегодня + просроченные
./onec.sh tasks 29.09.2026 --who Иванов                     # на дату, только одного сотрудника
./onec.sh ask "Какая выручка за сентябрь и кто главный клиент?"   # вопрос Jarvis
./onec.sh ask "Что у меня на сегодня?"
./onec.sh login                                             # сменить адрес/пользователя/пароль
```

`./onec.sh revenue` и `./onec.sh tasks` не используют модель и всегда дают точный ответ.
`./onec.sh ask` передаёт вопрос агенту Jarvis с инструментами `onec_revenue` и `onec_tasks`. Маленькая локальная
модель (`qwen3.5:2b`) вызывает инструменты ненадёжно, поэтому для таких вопросов
лучше подойдёт модель покрупнее (`qwen3.5:9b`) или облачная.

### Настройки для вашей конфигурации

Добавьте строки в `~/.openjarvis/onec.env`:

| Настройка | По умолчанию | Когда менять |
|---|---|---|
| `ONEC_SALES_DOCUMENT` | `Document_РеализацияТоваровУслуг` | УНФ: `Document_РасходнаяНакладная` |
| `ONEC_AMOUNT_FIELD` | `СуммаДокумента` | если сумма хранится в другом реквизите |
| `ONEC_RETURN_DOCUMENT` | (пусто) | вычитать возвраты: `Document_ВозвратТоваровОтПокупателя` |
| `ONEC_COUNTERPARTY_FIELD` / `ONEC_COUNTERPARTY_CATALOG` | `Контрагент` / `Catalog_Контрагенты` | другая конфигурация |
| `ONEC_CA_BUNDLE` | (пусто) | https с сертификатом собственного центра |
| `ONEC_TASK_OBJECT` | `Task_ЗадачаИсполнителя` | задачи CRM хранятся в другом объекте |
| `ONEC_TASK_DUE_FIELD` | `СрокИсполнения` | другой реквизит срока |
| `ONEC_TASK_DONE_FIELD` | `Executed` (стандартный признак «Выполнена») | если «выполнено» — отдельный реквизит |
| `ONEC_TASK_PERFORMER_FIELD` / `ONEC_USERS_CATALOG` | `Исполнитель` / `Catalog_Пользователи` | исполнитель — сотрудник, а не пользователь |

`./onec.sh check` отдельно сообщает, доступны ли задачи. Если нет — проверьте
название объекта задач в вашей конфигурации (раздел «Задачи» в Конфигураторе).

Важно:
- Выручка — это сумма документов реализации, обычно **с НДС**. Это не бухгалтерский
  отчёт: корректировки и ручные операции не учитываются.
- Задачи без срока и с ролевой адресацией (без конкретного исполнителя) показываются
  как «(не назначен)» или не показываются вовсе, если срок не заполнен.
- Если 1C доступна по `http://` (без `s`), пароль идёт по сети открытым текстом.
  Для доступа не из локальной сети используйте `https://`.

---

## 7. Muammolarni hal qilish

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
| `1C отклонила вход` | Неверный пользователь или пароль: `./onec.sh login` |
| `В OData нет объекта ...` | Объект не включён в состав OData или называется иначе (раздел 6, настройки) |
| `1C ответила не JSON` | Адрес должен заканчиваться на `/odata/standard.odata` |

Har qanday holatda birinchi qadam: `./jarvis.sh doctor`.

### Maxfiylik

OpenJarvis standart holatda anonim foydalanish statistikasini (suhbat matnisiz)
yuboradi. O'chirish uchun `~/.openjarvis/config.toml` ga qo'shing:

```toml
[analytics]
enabled = false
```

---

## 8. Yangilash va o'chirish

**Yangilash:**

```bash
./setup.sh
```

**O'chirish:**

```bash
rm -rf OpenJarvis ~/.openjarvis
```

(`~/.openjarvis` bilan birga ElevenLabs kaliti va 1C sozlamalari fayllari ham o'chadi.)

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

Qo'shimcha modullar testlari: `uv run --project OpenJarvis pytest voice/ onec/ addons/`
(46 ta test).

Модуль 1C проверен на тестовом сервере OData: `setup.sh --onec` (с вводом пароля в
терминале), `onec.sh revenue`, `onec.sh tasks`, `jarvis tool list`. Вся цепочка
`onec.sh ask` тоже прошла: агент Jarvis вызвал `onec_revenue` и `onec_tasks`, получил
данные из 1C и вернул их в ответе. Настоящая база 1C и настоящая модель в тесте не участвовали.

ElevenLabs moduli (`voice/`) soxta ElevenLabs serveri bilan ham
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
