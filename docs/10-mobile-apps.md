# 10. Мобильные приложения

## iOS

### Стек
- Swift 5.10+, SwiftUI, минимальный iOS 16.
- `AVPlayer` + `MPNowPlayingInfoCenter` + `MPRemoteCommandCenter` для фонового воспроизведения и Control Center.
- `URLSession` + `async/await` + `Codable`.
- Хранение токенов — Keychain (`KeychainAccess` или ручной wrapper).
- DI — обычные init-инъекции, без тяжёлых фреймворков.
- (Опц.) `ShazamKit` для распознавания.

### Структура
```
ios/LocalMusic/
  App/
    LocalMusicApp.swift
  Core/
    Networking/        // APIClient, эндпоинты
    Auth/              // токены, keychain
    Player/            // PlayerService (AVPlayer wrapper)
  Features/
    Login/
    Catalog/
    Player/
    Playlists/
    Vibe/
    Shazam/
  Resources/
    Assets.xcassets
```

### Клиент в репозитории
Проект: [`ios/LocalMusic.xcodeproj`](../ios/LocalMusic.xcodeproj). На Mac: `open ios/LocalMusic.xcodeproj`, выбрать свою Team (бесплатный Apple ID подходит) и Run на свой iPhone. Адрес сервера вводится на экране входа, например `http://192.168.1.10:8000`.

Срез этапа 6: логин, токены в Keychain, каталог, плейлисты, `AVPlayer` со стримом `/tracks/{id}/stream` и заголовком `Authorization`. `UIBackgroundModes = audio`, Now Playing и кнопки Control Center. Экранов «Моя волна» и Shazam нет: их нет в чек-листе базового клиента.

ATS: в `Info.plist` включены `NSAllowsLocalNetworking` и `NSAllowsArbitraryLoads`, потому что адрес домашнего сервера задаётся при входе и часто бывает `http` в локальной сети. Для публичного HTTPS это послабление можно убрать.

Установка на iPhone и TestFlight остаются на владельце: в этой среде нет Xcode, поэтому сборка здесь не проверялась. XCTest `LocalMusicTests` декодирует ответы каталога и плейлистов и запускается из Xcode (`Product → Test`).

### Особенности
- Background audio: в Capabilities включить `Audio, AirPlay, and Picture in Picture` + `Background Modes: Audio`.
- Стриминг по HTTPS обязателен (ATS). Если backend на http в локалке — добавить временно `NSAppTransportSecurity` для своего домена.
- `Range` запросы поддерживаются `AVPlayer` из коробки.

---

## Распространение iOS-приложения: варианты

Это ключевой вопрос для «личного» сервиса. Apple ограничивает sideload, но есть несколько способов.

### 1. **TestFlight** — рекомендованный путь
- Требуется Apple Developer Program: $99/год (платный аккаунт).
- Залить сборку в App Store Connect → TestFlight.
- **Internal Testing** — до 100 человек, приглашение по Apple ID. Используется команда Apple Developer (можно добавить друзей).
- **External Testing** — до 10 000 человек, по email или публичной ссылке. Требует **Beta App Review** (упрощённое ревью, обычно 1-2 дня). Тут уже могут зарубить за функционал «загрузка музыки из интернета» — нужно подавать аккуратно (например, описывать как «личный медиаплеер для собственных файлов»).
- Срок жизни сборки в TestFlight: **90 дней**, потом надо перезалить.
- Плюсы: легко устанавливается, можно обновлять, удобно для друзей.
- Минусы: ежегодная плата, риск Beta App Review для external, ограничение 90 дней.

### 2. **Прямая установка через Xcode** (бесплатно)
- Бесплатный Apple ID + Xcode.
- Подключаем iPhone по кабелю → Xcode → `Run` на устройство.
- Срок жизни сборки: **7 дней** (для бесплатного аккаунта). Через неделю надо переподписать.
- Free-аккаунт: 3 устройства, 10 App ID за 7 дней.
- Плюсы: бесплатно, никакого ревью.
- Минусы: переподпись каждую неделю; нет фоновых пушей и некоторых entitlements.

### 3. **AltStore / SideStore**
- Сторонний инсталлятор: подписывает IPA вашим Apple ID и обновляет каждые 7 дней автоматически, пока работает фоновый сервис (AltServer на компе, AltStore на телефоне).
- Подходит для постоянного личного использования без $99.
- Минусы: нужен Mac/PC в одной сети, чтобы перепеподписывать; иногда требует JIT/возни.

### 4. **Свой Developer ID (Enterprise / iOS Developer Enterprise Program)**
- $299/год, но Apple жёстко выдаёт только зарегистрированным юрлицам с >100 сотрудников. Для частного лица недоступно. **Не наш путь.**

### 5. **EU sideload (с iOS 17.4)**
- В Евросоюзе на iOS 17.4+ можно ставить через альтернативные магазины (AltStore PAL и др.). Если устройство и Apple ID — в EU, это рабочий вариант без $99.

### Рекомендация
- **На старте:** установка через Xcode на свой iPhone (бесплатно, для проверки).
- **Когда стабилизируется:** TestFlight + Apple Developer Program ($99/год). Это и для друзей, и для удобных обновлений.
- **Альтернатива:** AltStore — если не хочется платить.

---

## Android (фаза после MVP)

### Стек
- Kotlin, Jetpack Compose, Media3 (ExoPlayer).
- Retrofit / Ktor client.
- DataStore + EncryptedSharedPreferences для токенов.
- Минимальный SDK 26 (Android 8).

### Распространение
- **APK напрямую** — бесплатно. Раздаём APK через сайт сервиса или GitHub Releases. Установка с «Неизвестных источников».
- **Google Play Internal Testing** — до 100 тестеров, требуется одноразовая оплата Google Play Console ($25).
- **F-Droid** — open-source каталог, если захочется публичности.

Для «личного сервиса» проще всего собирать APK в CI (`./gradlew assembleRelease`) и раздавать друзьям ссылку.

---

## Общая стратегия клиентов

| Платформа | Способ доставки | Когда |
|---|---|---|
| Web | Caddy + статика | Этап 3 (MVP) |
| iOS | Xcode install / TestFlight | Этап 6 |
| Android | APK / Google Play Internal | Этап 7 (опц.) |

## Согласованный API
Все клиенты используют один и тот же REST API (см. [`05-api-spec.md`](05-api-spec.md:1)). Желательно поддерживать OpenAPI и генерировать модели:
- Swift: `swift-openapi-generator` или ручные `Codable`.
- Kotlin: `openapi-generator`.
