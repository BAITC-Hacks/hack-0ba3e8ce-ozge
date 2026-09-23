"""Умный подбор подрядчиков — веб-приложение на Streamlit.

Две стороны рынка:
  • Я заказчик  — свободный запрос превращается в бриф и подбираются подрядчики.
  • Я подрядчик — входящие заявки отсортированы по совпадению, с проверкой бюджета.

Запуск:  streamlit run app.py
"""

import streamlit as st

import ai
import core

st.set_page_config(page_title="Умный подбор подрядчиков", page_icon="🎬", layout="wide")

CONTRACTORS = core.load_contractors()
EXAMPLES = core.load_demo_examples()
REQUESTS = core.load_requests()
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
    st.header("Данные")
    col1, col2 = st.columns(2)
    col1.metric("Подрядчиков", len(CONTRACTORS))
    col2.metric("Заявок", len(REQUESTS))
    st.caption("Данные демонстрационные и вымышленные — см. README.")
    with st.expander("Посмотреть базу подрядчиков"):
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
    "**Одна площадка чинит рынок с двух сторон:** заказчик пишет запрос обычными словами и получает "
    "нормальный бриф и подходящих подрядчиков, а подрядчик видит входящие заявки, "
    "уже отсортированные по своему профилю и бюджету."
)

col_a, col_b = st.columns(2)
col_a.markdown("🙍 **Боль заказчика:** не может сформулировать, что ему нужно.\n\n→ Вкладка «Я заказчик» собирает бриф за него и задаёт недостающие вопросы.")
col_b.markdown("🎥 **Боль подрядчика:** кривые брифы и заказчики не по бюджету.\n\n→ Вкладка «Я подрядчик» показывает качество брифа и вердикт по бюджету до первого сообщения.")

tab_customer, tab_contractor = st.tabs(["🙍 Я заказчик", "🎥 Я подрядчик"])


def find_example(text):
    """Если текст совпал с готовым примером — вернуть его (для демо-режима)."""
    for example in EXAMPLES:
        if example["text"].strip() == (text or "").strip():
            return example
    return None


# ==========================================================================
# ВКЛАДКА 1. ЗАКАЗЧИК
# ==========================================================================
with tab_customer:
    if "request_text" not in st.session_state:
        st.session_state.request_text = EXAMPLES[0]["text"]

    st.subheader("1. Запрос заказчика")
    st.caption("Нажмите готовый пример или напишите свой текст.")

    example_cols = st.columns(len(EXAMPLES))
    for col, example in zip(example_cols, EXAMPLES):
        if col.button(example["title"], use_container_width=True, key="ex_" + example["title"]):
            st.session_state.request_text = example["text"]

    request_text = st.text_area(
        "Запрос обычными словами",
        key="request_text",
        height=140,
        label_visibility="collapsed",
    )

    go = st.button("Собрать бриф и подобрать подрядчиков", type="primary", use_container_width=True)

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
        fields[2].metric("Бюджет", core.money(brief.get("budget")))
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
        st.download_button("Скачать бриф файлом", brief_text, file_name="bref.txt",
                           use_container_width=True, key="dl_customer")


# ==========================================================================
# ВКЛАДКА 2. ПОДРЯДЧИК
# ==========================================================================
BADGE = {
    "fits": "🟢", "above": "🟢", "near": "🟡", "unknown": "🟡", "low": "🔴", "late": "🔴",
}

with tab_contractor:
    st.subheader("1. Кабинет подрядчика")
    st.caption("Выберите профиль — приложение покажет входящие заявки, отсортированные под него.")

    names = [f"{c['name']} — {c['service']}, {c['city']}" for c in CONTRACTORS]
    default_index = next((i for i, c in enumerate(CONTRACTORS) if c["id"] == "C02"), 0)
    chosen = st.selectbox("Ваш профиль", names, index=default_index, label_visibility="collapsed")
    me = CONTRACTORS[names.index(chosen)]

    profile = st.columns(4)
    profile[0].metric("Услуга", me["service"])
    profile[1].metric("Город", me["city"])
    profile[2].metric("Ваша вилка", f"{core.money(me['price_min'])} – {core.money(me['price_max'])}")
    profile[3].metric("Обычный срок", f"{me['lead_time_days']} дн.")
    st.caption(f"Форматы: {', '.join(me['formats'])} · Стиль: {', '.join(me['styles'])} · Языки: {', '.join(me['languages'])}")

    st.divider()
    st.subheader("2. Входящие заявки")

    filter_cols = st.columns(3)
    min_score = filter_cols[0].slider("Показывать заявки с совпадением от, %", 0, 100, 50, step=5)
    hide_low = filter_cols[1].toggle("Скрыть заказчиков не по бюджету", value=False)
    only_full = filter_cols[2].toggle("Только заявки с полным брифом", value=False)

    rows = core.incoming_for(me, REQUESTS, min_score=min_score)
    if hide_low:
        rows = [r for r in rows if r["budget_code"] != "low"]
    if only_full:
        rows = [r for r in rows if r["completeness"] >= 85]

    total = len(REQUESTS)
    fits = sum(1 for r in rows if r["budget_code"] in ("fits", "above"))
    st.markdown(
        f"Всего заявок в системе: **{total}**. Подходят вам: **{len(rows)}**, "
        f"из них по бюджету: **{fits}**."
    )

    if not rows:
        st.info("Под текущие фильтры заявок нет. Сдвиньте ползунок совпадения влево.")

    for r in rows:
        request = r["request"]
        brief = r["brief"]
        quality, quality_hint = core.brief_quality_label(brief)

        with st.container(border=True):
            head, score_col = st.columns([5, 1])
            head.markdown(
                f"### {request['customer']}\n"
                f"{brief.get('service') or '—'} · {brief.get('city') or '—'} · "
                f"бюджет {core.money(brief.get('budget'))} · "
                f"срок {str(brief.get('deadline_days')) + ' дн.' if brief.get('deadline_days') else 'не указан'} · "
                f"{request['date']}"
            )
            score_col.metric("Совпадение", f"{r['score']}%")

            st.markdown(f"> {request['text']}")

            checks = st.columns(3)
            checks[0].markdown(f"{BADGE.get(r['budget_code'], '⚪')} **Бюджет.** {r['budget_text']}")
            checks[1].markdown(f"{BADGE.get(r['deadline_code'], '⚪')} **Срок.** {r['deadline_text']}")
            checks[2].markdown(f"{'🟢' if r['completeness'] >= 85 else '🟡'} **{quality}** ({r['completeness']}%). {quality_hint}")

            with st.expander("Бриф заказчика и черновик ответа"):
                st.code(core.render_brief_text(brief, request["text"]), language=None)

                if r["budget_code"] == "low":
                    default_mode = "Отказать: не мой бюджет"
                elif r["completeness"] < 85:
                    default_mode = "Уточнить детали"
                else:
                    default_mode = "Взять в работу"

                modes = ["Взять в работу", "Уточнить детали", "Отказать: не мой бюджет"]
                mode_label = st.radio(
                    "Что ответить заказчику",
                    modes,
                    index=modes.index(default_mode),
                    horizontal=True,
                    key="mode_" + request["id"],
                )
                mode_key = {"Взять в работу": "accept",
                            "Уточнить детали": "clarify",
                            "Отказать: не мой бюджет": "decline"}[mode_label]

                reply = core.draft_reply(request, me, mode_key)
                st.caption("Готовый ответ — скопируйте и отправьте заказчику.")
                st.code(reply, language=None)
                st.download_button("Скачать ответ файлом", reply,
                                   file_name=f"otvet_{request['id']}.txt",
                                   key="dl_" + request["id"])
