# GTA5RP Helper

Универсальный бизнес-помощник для предпринимателей GTA5 RP.

## Возможности

- **EMS Трекер** — отслеживание ПМП ($1650), мед. осмотров ($188), уколов ($3000/прибыль $1650) за смену
- **Перекуп Калькулятор** — расчёт прибыли с учётом комиссии, инвентарь покупок/продаж
- **Трекер Заработка** — учёт дохода с любых работ (начальные + EMS)

## Запуск

```bash
pip install pywebview
python app.py
```

## Сборка .exe (Windows)

```powershell
pip install nuitka ordered-set zstandard
.\build.ps1
```

## Стек

- Python + pywebview (desktop)
- SQLite (хранение данных)
- Vanilla HTML/CSS/JS (UI)
