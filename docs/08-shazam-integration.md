# 08. Интеграция Shazam

## Краткий ответ
Официального публичного бесплатного API у Shazam **нет**. Apple владеет Shazam и предоставляет:
- **ShazamKit** — официальный SDK **только для нативных приложений** (iOS / macOS / Android). Подходит для нашего iOS-клиента, но **не** для backend на Python.
- На стороне сервера прямого SDK нет.

## Варианты

### Вариант A: ShazamKit в iOS-приложении (рекомендуется для iOS)
- Используем `ShazamKit.framework` прямо в SwiftUI-клиенте.
- Распознавание происходит на устройстве, результат (title/artist/isrc) отправляется на наш backend → `POST /search?query=<artist> <title>` → пользователь добавляет в библиотеку как обычно.
- Лицензия ShazamKit: использование разрешено и для индивидуальных разработчиков (по Apple Developer Agreement).
- **Минусы:** работает только на Apple-устройствах; недоступно в web и Android.

### Вариант B: Сторонние API-обёртки (RapidAPI «Shazam»)
- Существуют посредники (например, `shazam.p.rapidapi.com`). Не официальные. Могут перестать работать в любой момент.
- Принимают base64-аудио/URL → возвращают распознавание.
- Удобно для backend-эндпоинта `/shazam/recognize`.
- В `.env` есть переменные `SHAZAM_RAPIDAPI_KEY`, `SHAZAM_RAPIDAPI_HOST` (отключено если ключ пуст).

### Вариант C: AcoustID / Chromaprint (open-source)
- Полностью бесплатно, open-source. База AcoustID связана с MusicBrainz.
- Хорошо для распознавания **студийных треков**; хуже для живых записей и шума.
- Требует бинарь `fpcalc` (chromaprint) — добавляется в Docker-образ backend.
- Backend-эндпоинт: пользователь шлёт фрагмент → `fpcalc` → отпечаток → запрос к AcoustID API (нужен бесплатный API-key) → mbid → метаданные.

### Вариант D: Свой fingerprinting на C++
- Долго и сложно. Имеет смысл только как учебная задача.
- Использует БД отпечатков из своей библиотеки (распознавание «своих» же треков на пользовательских записях).

## Решение для проекта
- **MVP:** не делаем. Эндпоинт `/shazam/recognize` зарезервирован в [`05-api-spec.md`](05-api-spec.md:1), но возвращает 501.
- **Phase 2 (web/backend):** AcoustID + Chromaprint. Бесплатно, open-source, надёжно для студийной музыки.
- **Phase 2 (iOS):** ShazamKit нативно в приложении.
- **Phase 3 (опц.):** RapidAPI-обёртка как fallback.

## Поток для iOS (ShazamKit)
1. Пользователь жмёт «Распознать».
2. `SHSession.matchStreamingFor(audio buffer)` запускает запись с микрофона.
3. При успехе получаем `SHMediaItem` с `title`, `artist`, `isrc`, `shazamID`.
4. Клиент шлёт `POST /api/v1/search` с запросом `<artist> <title>` (или ISRC, если backend научится их обрабатывать).
5. Бэкенд возвращает кандидатов, пользователь добавляет нужный.

## Поток для backend (AcoustID, phase 2)
1. `POST /api/v1/shazam/recognize` multipart: фрагмент 5-10 сек.
2. Сохраняем во временный wav.
3. `fpcalc -json /tmp/x.wav` → `{duration, fingerprint}`.
4. `GET https://api.acoustid.org/v2/lookup?...&fingerprint=...&duration=...&meta=recordings`.
5. Парсим, возвращаем top-1 кандидата в едином формате.

## Требования к Docker
- Если идём по пути AcoustID: добавить в backend образ: `apk add chromaprint` (alpine) / `apt-get install libchromaprint-tools` (debian).
- Переменная `ACOUSTID_API_KEY` в `.env`.

## Резюме
Лучший практический путь — комбинация:
- **iOS:** ShazamKit (нативно, точно, бесплатно).
- **Backend/Web:** AcoustID + Chromaprint (open-source, кросс-платформенно).
