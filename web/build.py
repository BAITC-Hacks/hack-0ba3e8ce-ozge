"""Собирает web/index.html: шаблон + данные проекта одним файлом.

Запуск из корня проекта:  python3 web/build.py

Результат — самостоятельная HTML-страница без сервера и без установки:
её можно открыть с телефона или выложить по ссылке. Подбор на странице
считает тот же алгоритм, что и приложение на Streamlit.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build():
    data = {
        "contractors": json.loads((ROOT / "data/contractors.json").read_text(encoding="utf-8")),
        "requests": json.loads((ROOT / "data/requests.json").read_text(encoding="utf-8")),
        "examples": json.loads((ROOT / "data/demo_examples.json").read_text(encoding="utf-8")),
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = (ROOT / "web/template.html").read_text(encoding="utf-8")
    page = template.replace("__DATA__", blob)
    out = ROOT / "web/index.html"
    out.write_text(page, encoding="utf-8")
    print(f"Готово: {out} ({len(page)} символов, "
          f"{len(data['contractors'])} подрядчиков, {len(data['requests'])} заявок)")


if __name__ == "__main__":
    build()
