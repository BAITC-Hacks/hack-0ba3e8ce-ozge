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

# Ключевые слова на русском и казахском: рынок в Казахстане двуязычный,
# и заказчик вполне может написать запрос по-казахски.
SERVICE_KEYWORDS = {
    "Видеопродакшн": ["снять видео", "видеосъёмка", "видеосъемка", "продакшн", "рекламный ролик",
                      "имиджевое видео", "съёмка ролика",
                      "бейне түсір", "видео түсір", "жарнама ролик", "түсірілім", "бейнеролик"],
    "Видеомонтаж": ["монтаж", "смонтировать", "склеить", "нарезать видео", "рилс", "reels", "шортс",
                    "бейнемонтаж", "монтаждау", "қию"],
    "Фотосъёмка": ["фото", "фотограф", "фотосессия", "предметная съёмка", "каталог",
                   "фотосурет", "суретке түсір"],
    "Брендинг и логотип": ["логотип", "лого", "брендинг", "фирменный стиль", "брендбук", "айдентика",
                           "фирмалық стиль", "логотип жасау"],
    "Графический дизайн": ["макет", "полиграфия", "баннер", "презентация", "листовка", "афиша",
                           "баннер жасау", "презентация жасау"],
    "SMM и контент": ["смм", "smm", "соцсети", "инстаграм", "instagram", "вести аккаунт", "контент-план",
                      "әлеуметтік желі", "парақша жүргіз", "парақшаны жүргіз"],
    "Таргетированная реклама": ["таргет", "реклама в инстаграм", "трафик", "лиды", "заявки",
                                "жарнама беру", "таргеттелген жарнама"],
    "Копирайтинг": ["текст", "копирайт", "статья", "сценарий", "рассылка",
                    "мәтін жаз", "мақала жаз"],
    "Веб-дизайн и сайты": ["сайт", "лендинг", "landing", "интернет-магазин", "веб",
                           "сайт жасау", "сайт құру"],
    "Моушн-дизайн": ["анимация", "моушн", "motion", "инфографика", "анимационный ролик"],
    "Озвучка и звук": ["озвучка", "диктор", "звук", "сведение", "дауыстандыру", "дыбыстау"],
    "Иллюстрация": ["иллюстрац", "рисунок", "персонаж", "иконки", "сурет салу"],
    "3D и визуализация": ["3d", "3д", "визуализац", "рендер"],
    "Аренда студии": ["студи", "павильон", "циклорама", "арендовать", "студия жалға"],
    "Организация мероприятий": ["мероприят", "ивент", "event", "корпоратив", "форум",
                                "іс-шара", "той", "ашылу салтанаты"],
    "Аэросъёмка": ["дрон", "аэросъёмка", "аэросъемка", "с воздуха", "квадрокоптер", "ұшқышсыз"],
    "Субтитры и перевод": ["субтитры", "перевод", "расшифровк", "субтитр", "аудар"],
    "Подкасты": ["подкаст"],
}

# Смежные услуги: кто может закрыть задачу, если точного профиля нет
RELATED_SERVICES = {
    "Видеопродакшн": ["Видеомонтаж", "Аэросъёмка", "Подкасты", "Фотосъёмка"],
    "Видеомонтаж": ["Видеопродакшн", "Моушн-дизайн", "Субтитры и перевод", "Подкасты"],
    "Фотосъёмка": ["Видеопродакшн", "Аренда студии", "3D и визуализация"],
    "Брендинг и логотип": ["Графический дизайн", "Веб-дизайн и сайты", "Иллюстрация"],
    "Графический дизайн": ["Брендинг и логотип", "Иллюстрация", "Моушн-дизайн"],
    "SMM и контент": ["Таргетированная реклама", "Копирайтинг", "Видеомонтаж", "Фотосъёмка"],
    "Таргетированная реклама": ["SMM и контент", "Копирайтинг"],
    "Копирайтинг": ["SMM и контент", "Субтитры и перевод"],
    "Веб-дизайн и сайты": ["Брендинг и логотип", "Графический дизайн"],
    "Моушн-дизайн": ["Видеомонтаж", "Графический дизайн", "3D и визуализация"],
    "Озвучка и звук": ["Видеомонтаж", "Подкасты"],
    "Иллюстрация": ["Графический дизайн", "Брендинг и логотип"],
    "3D и визуализация": ["Моушн-дизайн", "Фотосъёмка"],
    "Аренда студии": ["Фотосъёмка", "Видеопродакшн", "Подкасты"],
    "Организация мероприятий": ["Фотосъёмка", "Видеопродакшн"],
    "Аэросъёмка": ["Видеопродакшн", "3D и визуализация"],
    "Субтитры и перевод": ["Видеомонтаж", "Копирайтинг"],
    "Подкасты": ["Видеомонтаж", "Озвучка и звук", "Аренда студии"],
}

CITY_KEYWORDS = {
    "Астана": ["астан", "нур-султан"],
    "Алматы": ["алмат"],
    "Шымкент": ["шымкент"],
    "Караганда": ["караганд", "қараған"],
    "онлайн": ["онлайн", "удалённо", "удаленно", "неважно где", "дистанционно", "қашықтан"],
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

    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(млн|миллион|тыс|тысяч|мың|к\b|k\b)?", t):
        raw, suffix = match.group(1), match.group(2)
        value = float(raw.replace(",", "."))
        if suffix in ("млн", "миллион"):
            value *= 1_000_000
        elif suffix in ("тыс", "тысяч", "мың", "к", "k"):
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
    m = re.search(r"(\d+)\s*(дн|день|дня|дней|күн)", t)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(\d+)\s*(недел|апта)", t)
    if m:
        return max(1, int(m.group(1))) * 7
    m = re.search(r"(\d+)\s*(месяц|ай\b)", t)
    if m:
        return max(1, int(m.group(1))) * 30
    if "срочно" in t or "завтра" in t or "вчера" in t or "шұғыл" in t:
        return 2
    if "недел" in t or "апта" in t:
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
    kazakh_letters = set("әғқңөұүһі")
    if "казах" in t or "қазақ" in t or " каз " in t or (kazakh_letters & set(t)):
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


def is_vague(brief):
    """Запрос, из которого не удалось вытащить вообще ничего полезного.

    Такое бывает, когда в поле набрали случайный текст или оставили его почти пустым.
    В этом случае честнее сказать об этом, чем делать вид, что подбор осмысленный.
    """
    signals = [brief.get("service"), brief.get("city"), brief.get("budget"),
               brief.get("deadline_days"), brief.get("formats"), brief.get("goal")]
    return not any(v for v in signals)


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
    return sum(1 for w in words if w and len(w) >= 4 and w.lower() in h)


def score_contractor(brief, c):
    """Считает баллы подрядчика под бриф. Возвращает (баллы, причины, риски)."""
    score = 0
    reasons = []
    risks = []
    service_matched = True  # профиль подрядчика совпал с нужной услугой

    # 1. Услуга — до 40 баллов
    service = brief.get("service")
    if service and c["service"] == service:
        score += 40
        reasons.append(f"профиль совпадает: {c['service']}")
    elif service and c["service"] in RELATED_SERVICES.get(service, []):
        score += 18
        reasons.append(f"смежная услуга: {c['service']} — может закрыть часть задачи")
    elif service:
        service_matched = False
        risks.append(f"другой профиль: {c['service']}, а нужен «{service}»")
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

    # Если профиль вообще не тот, подрядчик не может быть в топе,
    # даже когда сходятся город, бюджет и срок.
    ceiling = 45 if not service_matched else 100
    return round(min(score, ceiling)), reasons, risks


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


# --------------------------------------------------------------------------
# Сторона подрядчика: входящие заявки, проверка бюджета, ответы заказчику
# --------------------------------------------------------------------------

def load_requests():
    """Читает входящие заявки заказчиков из data/requests.json."""
    with open(DATA_DIR / "requests.json", encoding="utf-8") as f:
        return json.load(f)


def money(value):
    """Форматирует сумму: 250000 -> «250 000 ₸»."""
    if not value:
        return "не указан"
    return f"{int(value):,} ₸".replace(",", " ")


def budget_verdict(brief, c):
    """Проверяет, по бюджету ли заказчик для этого подрядчика.

    Возвращает (код, текст). Коды: fits / above / near / low / unknown.
    """
    budget = brief.get("budget")
    low, high = c["price_min"], c["price_max"]

    if not budget:
        return "unknown", "Бюджет не назван — до разговора о работе надо его выяснить."
    if budget > high:
        return "above", f"Бюджет {money(budget)} выше вашего потолка ({money(high)}). Можно предложить расширенный объём."
    if budget >= low:
        return "fits", f"Бюджет {money(budget)} попадает в вашу вилку {money(low)} – {money(high)}."
    if (low - budget) / low <= 0.2:
        return "near", f"Бюджет {money(budget)} чуть ниже вашего минимума ({money(low)}). Реально сойтись, если урезать объём."
    return "low", f"Бюджет {money(budget)} не тянет: ваш минимум {money(low)}. Разница {money(low - budget)}."


def deadline_verdict(brief, c):
    """Успевает ли подрядчик к сроку заказчика."""
    deadline = brief.get("deadline_days")
    if not deadline:
        return "unknown", "Срок не назван."
    if c["lead_time_days"] <= deadline:
        return "fits", f"Успеваете: ваш обычный срок {c['lead_time_days']} дн., у заказчика есть {deadline}."
    return "late", f"Не успеваете: ваш срок {c['lead_time_days']} дн., а заказчик просит за {deadline}."


def brief_quality_label(brief):
    """Словесная оценка качества брифа."""
    done = brief_completeness(brief)
    if done >= 85:
        return "Полный бриф", "Можно оценивать работу сразу."
    if done >= 60:
        return "Бриф неполный", "Пары ответов не хватает для оценки."
    return "Сырой запрос", "Без уточнений оценивать нельзя."


def draft_reply(request, c, mode):
    """Готовит текст ответа заказчику. Работает без ИИ.

    mode: accept — беру в работу, clarify — уточняю, decline — не мой бюджет.
    """
    brief = request["brief"]
    customer = request.get("customer", "")
    greeting = f"Здравствуйте, {customer}!" if customer else "Здравствуйте!"
    service = brief.get("service") or "задачу"
    questions = follow_up_questions(brief, limit=5)

    if mode == "clarify":
        body = [
            greeting,
            "",
            f"Спасибо за заявку. Чтобы назвать точную цену и срок по задаче «{service}», "
            "мне не хватает нескольких деталей:",
            "",
        ]
        body += [f"{i}. {q}" for i, q in enumerate(questions, 1)] or ["(бриф полный, вопросов нет)"]
        body += [
            "",
            f"Как ответите — пришлю смету и план работ. Ориентир по моим ценам: "
            f"{money(c['price_min'])} – {money(c['price_max'])} {c['unit']}, обычный срок {c['lead_time_days']} дн.",
            "",
            c["name"],
        ]
        return "\n".join(body)

    if mode == "decline":
        code, text = budget_verdict(brief, c)
        budget = brief.get("budget")
        body = [
            greeting,
            "",
            f"Спасибо за заявку. По задаче «{service}» честно скажу сразу: в {money(budget)} я не уложусь. "
            f"Мои работы этого типа стоят от {money(c['price_min'])} {c['unit']} — "
            "за меньшую сумму получится хуже, чем вы ожидаете, и это будет неприятно обоим.",
            "",
            "Что можно сделать в вашем бюджете:",
            f"— взять меньший объём работы и сделать его нормально;",
            f"— упростить формат (например, вместо полного продакшна — работа с вашим материалом);",
            f"— вернуться к задаче, когда бюджет вырастет: смету на полный объём пришлю по запросу.",
            "",
            "Если подходит один из вариантов — напишите, обсудим.",
            "",
            c["name"],
        ]
        return "\n".join(body)

    # accept
    budget_code, budget_text = budget_verdict(brief, c)
    deadline = brief.get("deadline_days")
    body = [
        greeting,
        "",
        f"Задача понятна, берусь. Коротко, как я её понял:",
        "",
        f"— Услуга: {service}",
        f"— Объём: {brief.get('volume') or 'уточним на созвоне'}",
        f"— Формат: {', '.join(brief.get('formats') or []) or 'уточним'}",
        f"— Стиль: {', '.join(brief.get('styles') or []) or 'уточним'}",
        f"— Срок: {str(deadline) + ' дн.' if deadline else 'обсудим'} "
        f"(мой обычный срок — {c['lead_time_days']} дн.)",
        f"— Бюджет: {money(brief.get('budget'))}",
        "",
    ]
    if questions:
        body += ["Один момент уточню до старта: " + questions[0], ""]
    body += [
        "Если всё верно — подтвердите, и я ставлю задачу в график.",
        "",
        c["name"],
    ]
    return "\n".join(body)


def incoming_for(c, requests, min_score=0):
    """Считает входящие заявки под конкретного подрядчика и сортирует по совпадению."""
    rows = []
    for request in requests:
        brief = request["brief"]
        score, reasons, risks = score_contractor(brief, c)
        budget_code, budget_text = budget_verdict(brief, c)
        deadline_code, deadline_text = deadline_verdict(brief, c)
        rows.append({
            "request": request,
            "brief": brief,
            "score": score,
            "reasons": reasons,
            "risks": risks,
            "budget_code": budget_code,
            "budget_text": budget_text,
            "deadline_code": deadline_code,
            "deadline_text": deadline_text,
            "completeness": brief_completeness(brief),
        })
    rows = [r for r in rows if r["score"] >= min_score]
    rows.sort(key=lambda r: -r["score"])
    return rows


# --------------------------------------------------------------------------
# Метрики рынка: что именно ломает сделки
# --------------------------------------------------------------------------

MATCH_THRESHOLD = 60  # с какого совпадения считаем, что подрядчик реально подходит


def request_status(request, contractors):
    """Может ли рынок закрыть эту заявку и, если нет, почему.

    Возвращает (код, причина словами). Коды: matched / no_profile /
    no_budget / budget_low / raw_brief / other.
    """
    brief = request["brief"]
    service = brief.get("service")

    profile = [c for c in contractors if c["service"] == service] if service else contractors

    for c in contractors:
        score, _, _ = score_contractor(brief, c)
        budget_code, _ = budget_verdict(brief, c)
        if score >= MATCH_THRESHOLD and budget_code in ("fits", "above"):
            return "matched", "Есть подходящий подрядчик по бюджету."

    if not profile:
        return "no_profile", "Нет подрядчиков такого профиля"
    if not brief.get("budget"):
        return "no_budget", "Бюджет не назван"
    if all(brief["budget"] < c["price_min"] for c in profile):
        return "budget_low", "Бюджет ниже рынка"
    if brief_completeness(brief) < 60:
        return "raw_brief", "Бриф слишком сырой"
    return "other", "Не сошлись срок, город или формат"


def market_stats(contractors, requests):
    """Считает сводку по рынку для вкладки «Рынок»."""
    total = len(requests)

    # --- Боль заказчика: насколько запрос вырастает после разбора ---
    rows = []
    for request in requests:
        before = brief_completeness(parse_request_offline(request["text"]))
        after = brief_completeness(request["brief"])
        rows.append({
            "customer": request["customer"],
            "before": before,
            "after": after,
        })
    completeness_before = round(sum(r["before"] for r in rows) / total) if total else 0
    completeness_after = round(sum(r["after"] for r in rows) / total) if total else 0

    no_budget = sum(1 for r in requests if not r["brief"].get("budget"))
    no_deadline = sum(1 for r in requests if not r["brief"].get("deadline_days"))
    no_goal = sum(1 for r in requests if not r["brief"].get("goal"))

    # --- Боль подрядчика: сколько профильных заявок бесполезны ---
    relevant_pairs = 0
    bad_budget_pairs = 0
    offers_per_request = {}
    requests_per_contractor = {}

    for c in contractors:
        requests_per_contractor[c["id"]] = 0
        for request in requests:
            brief = request["brief"]
            score, _, _ = score_contractor(brief, c)
            if score < MATCH_THRESHOLD:
                continue
            relevant_pairs += 1
            budget_code, _ = budget_verdict(brief, c)
            if budget_code in ("fits", "above"):
                offers_per_request[request["id"]] = offers_per_request.get(request["id"], 0) + 1
                requests_per_contractor[c["id"]] += 1
            else:
                bad_budget_pairs += 1

    wasted_share = round(bad_budget_pairs / relevant_pairs * 100) if relevant_pairs else 0

    # --- Какие заявки рынок вообще не закрывает и почему ---
    statuses = {}
    reasons = {}
    for request in requests:
        code, reason = request_status(request, contractors)
        statuses[request["id"]] = code
        if code != "matched":
            reasons[reason] = reasons.get(reason, 0) + 1
    matched = sum(1 for code in statuses.values() if code == "matched")

    idle = [c for c in contractors if requests_per_contractor[c["id"]] == 0]

    # --- Спрос и предложение по услугам ---
    services = sorted({c["service"] for c in contractors} |
                      {r["brief"].get("service") for r in requests if r["brief"].get("service")})
    demand_supply = [
        {
            "service": service,
            "demand": sum(1 for r in requests if r["brief"].get("service") == service),
            "supply": sum(1 for c in contractors if c["service"] == service),
        }
        for service in services
    ]

    return {
        "total": total,
        "rows": rows,
        "completeness_before": completeness_before,
        "completeness_after": completeness_after,
        "lift": completeness_after - completeness_before,
        "no_budget": no_budget,
        "no_deadline": no_deadline,
        "no_goal": no_goal,
        "relevant_pairs": relevant_pairs,
        "bad_budget_pairs": bad_budget_pairs,
        "wasted_share": wasted_share,
        "matched": matched,
        "unmatched": total - matched,
        "reasons": reasons,
        "statuses": statuses,
        "idle": idle,
        "requests_per_contractor": requests_per_contractor,
        "offers_per_request": offers_per_request,
        "demand_supply": demand_supply,
    }


# --------------------------------------------------------------------------
# Сохранение сделок: чем закончилась заявка
# --------------------------------------------------------------------------

DEALS_PATH = DATA_DIR / "deals.json"

DEAL_MODES = {
    "accept": ("Взято в работу", "🟢"),
    "clarify": ("Уточняются детали", "🟡"),
    "decline": ("Отказ: не мой бюджет", "🔴"),
}


def load_deals():
    """Читает сохранённые сделки. Файла нет — значит сделок ещё нет."""
    if not DEALS_PATH.exists():
        return []
    try:
        with open(DEALS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_deals(deals):
    """Записывает сделки на диск, чтобы они пережили перезагрузку страницы."""
    with open(DEALS_PATH, "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)


def add_deal(request, contractor, mode, reply):
    """Фиксирует ответ подрядчика на заявку. Повторный ответ заменяет прежний."""
    from datetime import datetime

    deals = [d for d in load_deals()
             if not (d["request_id"] == request["id"] and d["contractor_id"] == contractor["id"])]
    deals.append({
        "request_id": request["id"],
        "customer": request["customer"],
        "contractor_id": contractor["id"],
        "contractor_name": contractor["name"],
        "mode": mode,
        "status": DEAL_MODES[mode][0],
        "budget": request["brief"].get("budget"),
        "service": request["brief"].get("service"),
        "at": datetime.now().strftime("%d.%m %H:%M"),
        "reply": reply,
    })
    save_deals(deals)
    return deals


def clear_deals():
    """Сбрасывает демонстрационные сделки."""
    save_deals([])


def deals_by_request(deals, contractor_id):
    """Ответы конкретного подрядчика: id заявки -> запись о сделке."""
    return {d["request_id"]: d for d in deals if d["contractor_id"] == contractor_id}


def deal_stats(deals):
    """Сводка: сколько взято в работу, уточняется и отклонено."""
    counts = {mode: 0 for mode in DEAL_MODES}
    money_in_work = 0
    for d in deals:
        counts[d["mode"]] = counts.get(d["mode"], 0) + 1
        if d["mode"] == "accept":
            money_in_work += d.get("budget") or 0
    return {
        "total": len(deals),
        "accept": counts.get("accept", 0),
        "clarify": counts.get("clarify", 0),
        "decline": counts.get("decline", 0),
        "money_in_work": money_in_work,
        "requests_answered": len({d["request_id"] for d in deals}),
    }


# --------------------------------------------------------------------------
# Выгрузка данных в CSV
# --------------------------------------------------------------------------

def to_csv(rows, columns=None):
    """Собирает CSV, который нормально открывается в Excel на русском.

    Разделитель «;» и BOM в начале — иначе Excel ломает кириллицу и склеивает
    всё в одну колонку.
    """
    import csv
    import io

    rows = rows or []
    if columns is None:
        columns = list(rows[0].keys()) if rows else []

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, delimiter=";",
                            lineterminator="\r\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return "﻿" + buffer.getvalue()


def match_rows_for_csv(brief, results):
    """Результат подбора в виде строк для выгрузки."""
    return [
        {
            "Место": place,
            "Подрядчик": r["contractor"]["name"],
            "Совпадение, %": r["score"],
            "Услуга": r["contractor"]["service"],
            "Город": r["contractor"]["city"],
            "Цена от, ₸": r["contractor"]["price_min"],
            "Цена до, ₸": r["contractor"]["price_max"],
            "Единица": r["contractor"]["unit"],
            "Срок, дн.": r["contractor"]["lead_time_days"],
            "Рейтинг": r["contractor"]["rating"],
            "Отзывов": r["contractor"]["reviews"],
            "Почему подходит": "; ".join(r["reasons"]),
            "На что обратить внимание": "; ".join(r["risks"]),
            "Запрошенная услуга": brief.get("service") or "",
            "Бюджет заказчика, ₸": brief.get("budget") or "",
            "Срок заказчика, дн.": brief.get("deadline_days") or "",
        }
        for place, r in enumerate(results, 1)
    ]


def incoming_rows_for_csv(rows):
    """Входящие заявки подрядчика в виде строк для выгрузки."""
    return [
        {
            "Заявка": r["request"]["id"],
            "Заказчик": r["request"]["customer"],
            "Получена": r["request"]["date"],
            "Совпадение, %": r["score"],
            "Услуга": r["brief"].get("service") or "",
            "Город": r["brief"].get("city") or "",
            "Бюджет, ₸": r["brief"].get("budget") or "",
            "Срок, дн.": r["brief"].get("deadline_days") or "",
            "Полнота брифа, %": r["completeness"],
            "Вердикт по бюджету": r["budget_text"],
            "Вердикт по сроку": r["deadline_text"],
            "Запрос заказчика": r["request"]["text"],
        }
        for r in rows
    ]


def deals_rows_for_csv(deals):
    """Сделки в виде строк для выгрузки."""
    return [
        {
            "Время": d["at"],
            "Заявка": d["request_id"],
            "Заказчик": d["customer"],
            "Подрядчик": d["contractor_name"],
            "Услуга": d.get("service") or "",
            "Бюджет, ₸": d.get("budget") or "",
            "Статус": d["status"],
            "Текст ответа": d["reply"].replace("\n", " / "),
        }
        for d in deals
    ]


def market_rows_for_csv(stats):
    """Сводка по рынку в виде строк «показатель — значение»."""
    return [
        {"Показатель": "Заявок всего", "Значение": stats["total"]},
        {"Показатель": "Полнота исходного запроса, %", "Значение": stats["completeness_before"]},
        {"Показатель": "Полнота после разбора, %", "Значение": stats["completeness_after"]},
        {"Показатель": "Прирост полноты, п.п.", "Значение": stats["lift"]},
        {"Показатель": "Заявок без бюджета", "Значение": stats["no_budget"]},
        {"Показатель": "Заявок без срока", "Значение": stats["no_deadline"]},
        {"Показатель": "Профильных пар «подрядчик — заявка»", "Значение": stats["relevant_pairs"]},
        {"Показатель": "Из них тупиковые по бюджету", "Значение": stats["bad_budget_pairs"]},
        {"Показатель": "Доля тупиковых, %", "Значение": stats["wasted_share"]},
        {"Показатель": "Заявок закрывает рынок", "Значение": stats["matched"]},
        {"Показатель": "Заявок без исполнителя", "Значение": stats["unmatched"]},
        {"Показатель": "Подрядчиков без единой заявки", "Значение": len(stats["idle"])},
    ]
