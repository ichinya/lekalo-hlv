# lekalo-hlv

Bridge между [Lekalo](https://github.com/ichinya/lekalo) и [HLV](https://github.com/lee-to/hlv): сопоставление требований, trace и фактических результатов исполнения с контрактами HLV external execution evidence.

- Языконезависимый: один bridge обслуживает PHP-, TypeScript- и Python-проекты.
- HLV остаётся необязательным для Lekalo; становится обязательным для проекта, если политика приёмки требует его gate.
- Задача сопоставления — [#1](https://github.com/ichinya/lekalo-hlv/issues/1); общий план отделения — [ichinya/lekalo#241](https://github.com/ichinya/lekalo/issues/241).

## Реализация

`src/lib.rs` владеет HLV-политикой однозначного сопоставления test/gate с внешней ревизией. Отсутствие, несколько соответствий и устаревшая ревизия возвращаются отдельно. Общий граф, проверка trace manifest и коды диагностики принадлежат ядру.

Проверка: `cargo test --locked`. Это перенос уже существующей HLV-политики. Сопоставление доступно через внешний процесс и выбирается в конфиге. Исполнение самого HLV-трейсера остаётся отдельной задачей #1.

`ci/package-workflow.yml` — неактивный шаблон CI. Для автоматического запуска его нужно установить в `.github/workflows/` учётными данными с правом `workflow`; текущая публикация проверена локально.

## Процессный сервис

```sh
cargo install --locked --path . --root /your/tools
```

Добавьте `/your/tools/bin` в PATH, укажите `services.trace: {command: [lekalo-hlv]}` в `lekalo.yaml` и выполните `lekalo runtime lock`. Процесс реализует `describe` и `trace.mappings` в оболочке `lekalo/runtime/v1`. Ядро не компилирует этот пакет и не содержит его копии. [Схемы и ограничения](https://github.com/ichinya/lekalo/blob/feat/external-services-241/docs/external-services.md). Сборка использует `debug=0`, `incremental=false`.

После установки бинарника в PATH можно указать `gh/ichinya/lekalo-hlv` в services. При lock ядро сверяет идентичность и версию исполняемого сервиса с Git-манифестом.
