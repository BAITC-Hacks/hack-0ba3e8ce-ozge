"""Слой ИИ: разбор свободного запроса и объяснение подбора.

Если ключа OPENAI_API_KEY нет или запрос к модели не прошёл,
модуль сам откатывается на разбор по ключевым словам из core.py.
Приложение из-за отсутствия ключа не ломается никогда.
"""

import json
import os

from dotenv import load_dotenv

import core

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def api_key():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return key or None


def is_ai_available():
    """Есть ли ключ. Если нет — приложение работает в демо-режиме."""
    return api_key() is not None


def _client():
    from openai import OpenAI
    return OpenAI(api_key=api_key())


BRIEF_SYSTEM_PROMPT = """Ты — продюсер креативной студии в Казахстане.
Заказчик пишет запрос обычными словами и часто не знает, что именно ему нужно.
Твоя задача — превратить его запрос в структурированный бриф.

Верни ТОЛЬКО JSON без пояснений, по схеме:
{
  "service": "одна услуга из списка или null",
  "city": "Астана | Алматы | Шымкент | Караганда | онлайн | null",
  "budget": число в тенге или null,
  "budget_unit": "за ролик | за проект | в месяц | в час | за съёмочный день | null",
  "deadline_days": число дней или null,
  "formats": ["короткие названия форматов"],
  "styles": ["слова про стиль и настроение"],
  "language": "рус | каз | англ | null",
  "goal": "зачем это заказчику, одним предложением, или null",
  "volume": "объём работы словами, или null",
  "assumptions": ["что ты домыслил за заказчика"]
}

Правила:
- Ничего не выдумывай в полях budget и deadline_days: не сказано — null.
- Если заказчик описал задачу размыто, всё равно выбери самую вероятную услугу.
- Пиши по-русски.

Доступные услуги: {services}"""

EXPLAIN_SYSTEM_PROMPT = """Ты — продюсер, который советует заказчику подрядчиков.
Тебе дают бриф и список подобранных подрядчиков с их данными.
Напиши по каждому одно короткое предложение: почему он подходит именно под этот бриф,
и честно назови риск, если он есть (не тот город, не хватает бюджета, не успеет по сроку).

Верни ТОЛЬКО JSON: {"C01": "текст", "C02": "текст"}
Пиши простыми словами, по-русски, без воды и без восклицаний."""


def parse_request_ai(text, contractors):
    """Разбирает запрос через модель. При любой ошибке — откат на офлайн-разбор."""
    if not is_ai_available():
        return core.parse_request_offline(text), "offline"

    services = ", ".join(core.all_services(contractors))
    try:
        client = _client()
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": BRIEF_SYSTEM_PROMPT.replace("{services}", services)},
                {"role": "user", "content": text},
            ],
        )
        brief = json.loads(response.choices[0].message.content)
    except Exception as exc:  # ключ не тот, нет денег, нет интернета
        fallback = core.parse_request_offline(text)
        fallback["error"] = str(exc)
        return fallback, "offline"

    # приводим к нашему формату и добиваем пропуски офлайн-разбором
    offline = core.parse_request_offline(text)
    for field in core.BRIEF_FIELDS:
        if brief.get(field) in (None, "", []):
            brief[field] = offline.get(field)
    brief.setdefault("assumptions", [])
    brief["source"] = "ai"
    return brief, "ai"


def explain_matches_ai(brief, results):
    """Просит модель объяснить каждый подбор. При ошибке возвращает пустой словарь."""
    if not is_ai_available():
        return {}

    payload = {
        "brief": {k: brief.get(k) for k in core.BRIEF_FIELDS},
        "contractors": [
            {
                "id": r["contractor"]["id"],
                "name": r["contractor"]["name"],
                "service": r["contractor"]["service"],
                "city": r["contractor"]["city"],
                "price": f"{r['contractor']['price_min']}–{r['contractor']['price_max']} ₸ {r['contractor']['unit']}",
                "lead_time_days": r["contractor"]["lead_time_days"],
                "rating": r["contractor"]["rating"],
                "portfolio": r["contractor"]["portfolio"],
                "score": r["score"],
            }
            for r in results
        ],
    }
    try:
        client = _client()
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {}
