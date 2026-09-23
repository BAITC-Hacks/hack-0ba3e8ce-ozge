"""Умный подбор подрядчиков — веб-приложение на Streamlit.

Запуск:  streamlit run app.py
"""

import streamlit as st

import ai
import core

st.set_page_config(page_title="Умный подбор подрядчиков", page_icon="🎬", layout="wide")

CONTRACTORS = core.load_contractors()
EXAMPLES = core.load_demo_examples()
AI_ON = ai.is_ai_available()


# --------------------------------------------------------------------------
# Боковая панель
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Режим работы")
    if AI_ON:
        st.success(f"Режим с ИИ. Модель: {ai.MODEL}")
        st.caption("Запрос разбирает модель OpenAI, подбор считает наш алгоритм.")
    else:
        st.info("ДЕМО-РЕЖИМ (ключ API не нужен)")
        st.caption(
            "Ключ `OPENAI_API_KEY` не задан. Приложение работает целиком: "
            "запрос разбирается по правилам, подбор и объяснения считает алгоритм, "
            "а для трёх готовых примеров показываются заранее сохранённые ответы модели."
        )

    st.divider()
    st.header("База подрядчиков")
    st.metric("Подрядчиков в базе", len(CONTRACTORS))
    st.caption("Данные демонстрационные и вымышленные — см. README.")
    with st.expander("Посмотреть базу целиком"):
        st.dataframe(
            [
                {
                    "Имя": c["name"],
                    "Услуга": c["service"],
                    "Город": c["city"],
                    "Цена, ₸": f"{c['price_min']:,}–{c['price_max']:,}".replace(",", " "),
                    "Единица": c["unit"],
                    "Срок, дн.": c["lead_time_days"],
                    "Рейтинг": c["rating"],
                }
                for c in CONTRACTORS
            ],
            use_container_width=True,
            hide_index=True,
        )


# --------------------------------------------------------------------------
# Шапка
# --------------------------------------------------------------------------
st.title("🎬 Умный подбор подрядчиков")
st.markdown(
    "**Заказчик пишет запрос обычными словами — приложение превращает его в нормальный бриф "
    "и подбирает подрядчиков, которые подходят по услуге, бюджету, городу и сроку.**"
)

col_a, col_b = st.columns(2)
col_a.markdown("🙍 **Боль заказчика:** не может сформулировать, что ему нужно.\n\n→ Приложение собирает бриф за него и задаёт недостающие вопросы.")
col_b.markdown("🎥 **Боль подрядчика:** кривые брифы и заказчики не по бюджету.\n\n→ Подрядчик получает структурированный бриф, а нереальный бюджет виден сразу.")

st.divider()


# --------------------------------------------------------------------------
# Ввод запроса
# --------------------------------------------------------------------------
if "request_text" not in st.session_state:
    st.session_state.request_text = EXAMPLES[0]["text"]
if "chosen_example" not in st.session_state:
    st.session_state.chosen_example = EXAMPLES[0]["title"]

st.subheader("1. Запрос заказчика")
st.caption("Нажмите готовый пример или напишите свой текст.")

example_cols = st.columns(len(EXAMPLES))
for col, example in zip(example_cols, EXAMPLES):
    if col.button(example["title"], use_container_width=True):
        st.session_state.request_text = example["text"]
        st.session_state.chosen_example = example["title"]

request_text = st.text_area(
    "Запрос обычными словами",
    key="request_text",
    height=140,
    label_visibility="collapsed",
)

go = st.button("Собрать бриф и подобрать подрядчиков", type="primary", use_container_width=True)


def find_example(text):
    """Если текст совпал с готовым примером — вернуть его (для демо-режима)."""
    for example in EXAMPLES:
        if example["text"].strip() == (text or "").strip():
            return example
    return None


# --------------------------------------------------------------------------
# Работа
# --------------------------------------------------------------------------
if go:
    if not request_text.strip():
        st.warning("Напишите запрос или выберите готовый пример.")
        st.stop()

    example = find_example(request_text)

    with st.spinner("Разбираю запрос…"):
        if AI_ON:
            brief, source = ai.parse_request_ai(request_text, CONTRACTORS)
        elif example:
            brief, source = dict(example["ai_brief"]), "demo"
        else:
            brief, source = core.parse_request_offline(request_text), "offline"

    results = core.match(brief, CONTRACTORS, top_n=5)

    explanations = {}
    if AI_ON:
        with st.spinner("Объясняю подбор…"):
            explanations = ai.explain_matches_ai(brief, results)
    elif example:
        explanations = example.get("ai_explanations", {})

    # ---------------- Бриф ----------------
    st.divider()
    st.subheader("2. Бриф, собранный из запроса")

    if source == "demo":
        st.caption("Демо-режим: показан заранее сохранённый разбор модели для этого примера.")
    elif source == "offline":
        st.caption("Разбор по правилам, без обращения к модели.")
        if brief.get("error"):
            st.warning(f"Модель недоступна, работаю по правилам. Причина: {brief['error']}")

    done = core.brief_completeness(brief)
    st.progress(done / 100, text=f"Бриф заполнен на {done}%")

    fields = st.columns(4)
    fields[0].metric("Услуга", brief.get("service") or "—")
    fields[1].metric("Город", brief.get("city") or "—")
    budget = brief.get("budget")
    fields[2].metric("Бюджет", f"{budget:,} ₸".replace(",", " ") if budget else "не указан")
    deadline = brief.get("deadline_days")
    fields[3].metric("Срок", f"{deadline} дн." if deadline else "не указан")

    left, right = st.columns(2)
    with left:
        st.markdown("**Цель:** " + (brief.get("goal") or "_не сформулирована_"))
        st.markdown("**Объём:** " + (brief.get("volume") or "_не указан_"))
        st.markdown("**Формат:** " + (", ".join(brief.get("formats") or []) or "_не указан_"))
        st.markdown("**Стиль:** " + (", ".join(brief.get("styles") or []) or "_не указан_"))
    with right:
        if brief.get("assumptions"):
            st.markdown("**Что приложение домыслило за заказчика:**")
            for a in brief["assumptions"]:
                st.markdown(f"- {a}")

    questions = core.follow_up_questions(brief)
    if questions:
        st.warning("**Это надо уточнить у заказчика до начала работы:**\n\n" +
                   "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)))
    else:
        st.success("Бриф полный — подрядчику можно отправлять как есть.")

    # ---------------- Подбор ----------------
    st.divider()
    st.subheader("3. Подобранные подрядчики")

    for place, r in enumerate(results, 1):
        c = r["contractor"]
        with st.container(border=True):
            head, score_col = st.columns([5, 1])
            head.markdown(
                f"### {place}. {c['name']}\n"
                f"{c['service']} · {c['city']} · "
                f"{c['price_min']:,}–{c['price_max']:,} ₸ {c['unit']} · "
                f"срок {c['lead_time_days']} дн. · ⭐ {c['rating']} ({c['reviews']})".replace(",", " ")
            )
            score_col.metric("Совпадение", f"{r['score']}%")

            explanation = explanations.get(c["id"])
            if explanation:
                st.markdown(f"💬 {explanation}")

            st.caption(c["portfolio"])

            why, risk = st.columns(2)
            if r["reasons"]:
                why.markdown("**Почему подходит**")
                for reason in r["reasons"]:
                    why.markdown(f"- ✅ {reason}")
            if r["risks"]:
                risk.markdown("**На что обратить внимание**")
                for item in r["risks"]:
                    risk.markdown(f"- ⚠️ {item}")

    # ---------------- Готовый бриф ----------------
    st.divider()
    st.subheader("4. Готовый бриф для отправки подрядчику")
    st.caption("Скопируйте и отправьте — подрядчик сразу видит задачу, бюджет и срок.")
    brief_text = core.render_brief_text(brief, request_text)
    st.code(brief_text, language=None)
    st.download_button("Скачать бриф файлом", brief_text, file_name="bref.txt", use_container_width=True)
