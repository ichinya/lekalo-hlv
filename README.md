# lekalo-hlv

Bridge между [Lekalo](https://github.com/ichinya/lekalo) и [HLV](https://github.com/lee-to/hlv): сопоставление требований, trace и фактических результатов исполнения с контрактами HLV external execution evidence.

- Языконезависимый: один bridge обслуживает PHP-, TypeScript- и Python-проекты.
- HLV остаётся необязательным для Lekalo; становится обязательным для проекта, если политика приёмки требует его gate.
- Задача сопоставления — [#1](https://github.com/ichinya/lekalo-hlv/issues/1); общий план отделения — [ichinya/lekalo#241](https://github.com/ichinya/lekalo/issues/241).
