"""Ядро проекта: база подрядчиков, правила подбора и сборка брифа.

Этот модуль не ходит в интернет и не требует ключа API.
Всё, что здесь есть, работает и в демо-режиме, и в режиме с ИИ.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Поля брифа, которые мы стараемся заполнить
BRIEF_FIELDS = [
    "service", "city", "budget", "budget_unit", "deadline_days",
    "formats", "styles", "language", "goal", "volume",
]

HUMAN_FIELD_NAMES = {
    "service": "услуга",
    "city": "город",
    "budget": "бюджет",
    "deadline_days": "срок",
    "formats": "формат работы",
    "styles": "стиль",
    "language": "язык материалов",
    "goal": "цель",
    "volume": "объём",
}

# Вопросы, которые задаём заказчику, если поле не заполнено
FOLLOW_UP_QUESTIONS = {
    "service": "Какая именно услуга нужна: съёмка, монтаж, дизайн, реклама, что-то другое?",
    "city": "В каком городе нужен подрядчик? Или подойдёт работа онлайн?",
    "budget": "Какой у вас бюджет в тенге? Достаточно вилки «от и до».",
    "deadline_days": "К какой дате нужен результат? Через сколько дней?",
    "formats": "В каком формате нужен результат: например, ролик для инстаграма, логотип, лендинг?",
    "goal": "Для чего это нужно: продажи, узнаваемость, обучение, отчёт?",
    "volume": "Какой объём работы: сколько роликов, страниц, макетов?",
}


def load_contractors():
    """Читает базу подрядчиков из data/contractors.json."""
    with open(DATA_DIR / "contractors.json", encoding="utf-8") as f:
        return json.load(f)


def load_demo_examples():
    """Читает заготовленные примеры для демо-режима."""
    with open(DATA_DIR / "demo_examples.json", encoding="utf-8") as f:
        return json.load(f)


def all_services(contractors):
    return sorted({c["service"] for c in contractors})


def all_cities(contractors):
    return sorted({c["city"] for c in contractors})


# --------------------------------------------------------------------------
# Разбор запроса без ИИ (работает в демо-режиме и как страховка)
# --------------------------------------------------------------------------

SERVICE_KEYWORDS = {
    "Видеопродакшн": ["снять видео", "видеосъёмка", "видеосъемка", "продакшн", "рекламный ролик", "имиджевое видео", "съёмка ролика"],
    "Видеомонтаж": ["монтаж", "смонтировать", "склеить", "нарезать видео", "рилс", "reels", "шортс"],
    "Фотосъёмка": ["фото", "фотограф", "фотосессия", "предметная съёмка", "каталог"],
    "Брендинг и логотип": ["логотип", "лого", "брендинг", "фирменный стиль", "брендбук", "айдентика"],
    "Графический дизайн": ["макет", "полиграфия", "баннер", "презентация", "листовка", "афиша"],
    "SMM и контент": ["смм", "smm", "соцсети", "инстаграм", "instagram", "вести аккаунт", "контент-план"],
    "Таргетированная реклама": ["таргет", "реклама в инстаграм", "трафик", "лиды", "заявки"],
    "Копирайтинг": ["текст", "копирайт", "статья", "сценарий", "рассылка"],
    "Веб-дизайн и сайты": ["сайт", "лендинг", "landing", "интернет-магазин", "веб"],
    "Моушн-дизайн": ["анимация", "моушн", "motion", "инфографика", "анимационный ролик"],
    "Озвучка и звук": ["озвучка", "диктор", "звук", "сведение"],
    "Иллюстрация": ["иллюстрац", "рисунок", "персонаж", "иконки"],
    "3D и визуализация": ["3d", "3д", "визуализац", "рендер"],
    "Аренда студии": ["студи", "павильон", "циклорама", "арендовать"],
    "Организация мероприятий": ["мероприят", "ивент", "event", "корпоратив", "форум"],
    "Аэросъёмка": ["дрон", "аэросъёмка", "аэросъемка", "с воздуха", "квадрокоптер"],
    "Субтитры и перевод": ["субтитры", "перевод", "расшифровк"],
    "Подкасты": ["подкаст"],
}

CITY_KEYWORDS = {
    "Астана": ["астан", "нур-султан"],
    "Алматы": ["алмат"],
    "Шымкент": ["шымкент"],
    "Караганда": ["караганд"],
    "онлайн": ["онлайн", "удалённо", "удаленно", "неважно где", "дистанционно"],
}

STYLE_KEYWORDS = [
    "динамично", "спокойный темп", "минимализм", "премиум", "кинематографично",
    "яркий", "бюджетно", "быстро", "трендово", "деловой", "тёплый", "живой",
]


def _find_budget(text):
    """Достаёт бюджет из текста: «300 тысяч», «150000», «до 1 млн»."""
    t = text.lower().replace(" ", " ")

    m = re.search(r"(\d[\d\s]{2,})\s*(?:тг|тенге|₸)?", t)
    numbers = []

    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(млн|миллион|тыс|тысяч|к\b|k\b)?", t):
        raw, suffix = match.group(1), match.group(2)
        value = float(raw.replace(",", "."))
        if suffix in ("млн", "миллион"):
            value *= 1_000_000
        elif suffix in ("тыс", "тысяч", "к", "k"):
            value *= 1_000
        if value >= 5_000:
            numbers.append(int(value))

    if numbers:
        return max(numbers)
    if m:
        cleaned = int(re.sub(r"\s", "", m.group(1)))
        if cleaned >= 5_000:
            return cleaned
    return None


def _find_deadline(text):
    """Достаёт срок в днях: «за 3 дня», «через неделю», «к пятнице»."""
    t = text.lower()
    m = re.search(r"(\d+)\s*(дн|день|дня|дней)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(недел)", t)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r"(\d+)\s*(месяц)", t)
    if m:
        return int(m.group(1)) * 30
    if "срочно" in t or "завтра" in t or "вчера" in t:
        return 2
    if "недел" in t:
        return 7
    if "месяц" in t:
        return 30
    return None


def parse_request_offline(text):
    """Разбирает свободный запрос по ключевым словам. Без ИИ."""
    t = text.lower()

    service = None
    best_hits = 0
    for name, keys in SERVICE_KEYWORDS.items():
        hits = sum(1 for k in keys if k in t)
        if hits > best_hits:
            service, best_hits = name, hits

    city = None
    for name, keys in CITY_KEYWORDS.items():
        if any(k in t for k in keys):
            city = name
            break

    formats = []
    for word in ["рилс", "шортс", "лендинг", "логотип", "презентация", "подкаст",
                 "интервью", "каталог", "портрет", "репортаж", "субтитры"]:
        if word in t:
            formats.append(word)

    styles = [s for s in STYLE_KEYWORDS if s.split()[0] in t]

    language = None
    if "казах" in t or "қазақ" in t or " каз " in t:
        language = "каз"
    elif "англ" in t:
        language = "англ"
    elif "русск" in t:
        language = "рус"

    return {
        "service": service,
        "city": city,
        "budget": _find_budget(text),
        "budget_unit": None,
        "deadline_days": _find_deadline(text),
        "formats": formats,
        "styles": styles,
        "language": language,
        "goal": None,
        "volume": None,
        "source": "offline",
    }


def missing_fields(brief):
    """Какие важные поля брифа остались пустыми."""
    important = ["service", "city", "budget", "deadline_days", "formats", "goal", "volume"]
    missing = []
    for field in important:
        value = brief.get(field)
        if value in (None, "", [], 0):
            missing.append(field)
    return missing


def follow_up_questions(brief, limit=4):
    """Вопросы заказчику по пустым полям брифа."""
    return [FOLLOW_UP_QUESTIONS[f] for f in missing_fields(brief) if f in FOLLOW_UP_QUESTIONS][:limit]


def brief_completeness(brief):
    """Насколько бриф заполнен, в процентах."""
    important = ["service", "city", "budget", "deadline_days", "formats", "goal", "volume"]
    filled = sum(1 for f in important if brief.get(f) not in (None, "", [], 0))
    return round(filled / len(important) * 100)


# --------------------------------------------------------------------------
# Подбор подрядчиков
# --------------------------------------------------------------------------

def _budget_score(brief_budget, c):
    """Сколько баллов за бюджет (максимум 25) и текстовое пояснение."""
    if not brief_budget:
        return 12, None

    low, high = c["price_min"], c["price_max"]
    if low <= brief_budget <= high:
        return 25, f"бюджет попадает в вилку {low:,} – {high:,} ₸".replace(",", " ")
    if brief_budget > high:
        return 22, f"бюджета хватает с запасом (их потолок {high:,} ₸)".replace(",", " ")

    gap = (low - brief_budget) / low
    if gap <= 0.2:
        return 12, f"чуть ниже их минимума ({low:,} ₸) — можно торговаться".replace(",", " ")
    if gap <= 0.5:
        return 4, f"бюджет заметно ниже их минимума ({low:,} ₸)".replace(",", " ")
    return 0, f"бюджета не хватает: у них от {low:,} ₸".replace(",", " ")


def _text_overlap(words, haystack):
    """Сколько слов из списка встречается в тексте."""
    h = haystack.lower()
    return sum(1 for w in words if w and w.lower() in h)


def score_contractor(brief, c):
    """Считает баллы подрядчика под бриф. Возвращает (баллы, причины, риски)."""
    score = 0
    reasons = []
    risks = []

    # 1. Услуга — до 40 баллов
    service = brief.get("service")
    if service and c["service"] == service:
        score += 40
        reasons.append(f"профиль совпадает: {c['service']}")
    elif service:
        haystack = c["portfolio"] + " " + " ".join(c["formats"]) + " " + c["service"]
        if _text_overlap(service.lower().split(), haystack):
            score += 18
            reasons.append(f"смежная услуга: {c['service']}")
        else:
            score += 0
    else:
        score += 15  # услуга не названа — не наказываем никого

    # 2. Бюджет — до 25 баллов
    budget_points, budget_note = _budget_score(brief.get("budget"), c)
    score += budget_points
    if budget_note:
        if budget_points >= 20:
            reasons.append(budget_note)
        else:
            risks.append(budget_note)

    # 3. Город — до 15 баллов
    city = brief.get("city")
    if not city:
        score += 8
    elif c["city"] == city:
        score += 15
        reasons.append(f"работает в городе {c['city']}")
    elif c["city"] == "онлайн" or city == "онлайн":
        score += 11
        reasons.append("работает онлайн")
    else:
        score += 2
        risks.append(f"находится в другом городе ({c['city']})")

    # 4. Формат — до 10 баллов
    formats = brief.get("formats") or []
    if formats:
        hits = _text_overlap(formats, " ".join(c["formats"]) + " " + c["portfolio"])
        if hits:
            score += min(10, hits * 5)
            reasons.append("делает нужный формат: " + ", ".join(c["formats"][:2]))
    else:
        score += 5

    # 5. Стиль — до 10 баллов
    styles = brief.get("styles") or []
    if styles:
        hits = _text_overlap(styles, " ".join(c["styles"]) + " " + c["portfolio"])
        if hits:
            score += min(10, hits * 5)
            reasons.append("стиль близок: " + ", ".join(c["styles"][:2]))
    else:
        score += 5

    # 6. Срок — до 10 баллов
    deadline = brief.get("deadline_days")
    if not deadline:
        score += 5
    elif c["lead_time_days"] <= deadline:
        score += 10
        reasons.append(f"успевает: обычный срок {c['lead_time_days']} дн.")
    else:
        risks.append(f"может не успеть: их срок {c['lead_time_days']} дн., а нужно за {deadline}")

    # 7. Язык — до 5 баллов
    language = brief.get("language")
    if language:
        if language in c["languages"]:
            score += 5
            reasons.append(f"работает на языке: {language}")
        else:
            risks.append(f"не заявляют язык «{language}»")
    else:
        score += 3

    # 8. Репутация — до 10 баллов
    rating_points = (c["rating"] - 4.0) / 1.0 * 7
    volume_points = min(3, c["reviews"] / 30)
    score += max(0, rating_points) + volume_points
    if c["rating"] >= 4.7:
        reasons.append(f"рейтинг {c['rating']} по {c['reviews']} отзывам")

    return round(min(score, 100)), reasons, risks


def match(brief, contractors, top_n=5):
    """Возвращает топ подрядчиков под бриф."""
    results = []
    for c in contractors:
        score, reasons, risks = score_contractor(brief, c)
        results.append({
            "contractor": c,
            "score": score,
            "reasons": reasons,
            "risks": risks,
        })
    results.sort(key=lambda r: (-r["score"], -r["contractor"]["rating"]))
    return results[:top_n]


# --------------------------------------------------------------------------
# Готовый бриф для отправки подрядчику
# --------------------------------------------------------------------------

def render_brief_text(brief, original_request=""):
    """Собирает текст брифа, который заказчик отправляет подрядчику."""
    def val(key, default="не указано"):
        v = brief.get(key)
        if v in (None, "", [], 0):
            return default
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v)

    budget = brief.get("budget")
    budget_line = f"{budget:,} ₸".replace(",", " ") if budget else "не указан"
    if brief.get("budget_unit"):
        budget_line += f" ({brief['budget_unit']})"

    deadline = brief.get("deadline_days")
    deadline_line = f"{deadline} дн." if deadline else "не указан"

    lines = [
        "БРИФ НА РАБОТУ",
        "",
        f"1. Услуга: {val('service')}",
        f"2. Что нужно сделать: {val('goal', 'уточняется')}",
        f"3. Объём: {val('volume')}",
        f"4. Формат результата: {val('formats')}",
        f"5. Стиль и настроение: {val('styles')}",
        f"6. Язык материалов: {val('language')}",
        f"7. Город / формат работы: {val('city')}",
        f"8. Бюджет: {budget_line}",
        f"9. Срок: {deadline_line}",
    ]
    if original_request:
        lines += ["", "Исходный запрос заказчика:", f"«{original_request.strip()}»"]

    gaps = missing_fields(brief)
    if gaps:
        lines += ["", "Заказчик пока не определился по пунктам: " +
                  ", ".join(HUMAN_FIELD_NAMES.get(g, g) for g in gaps) + "."]
    return "\n".join(lines)
