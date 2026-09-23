"""Умный подбор подрядчиков — веб-приложение на Streamlit.

Две стороны рынка:
  • Я заказчик  — свободный запрос превращается в бриф и подбираются подрядчики.
  • Я подрядчик — входящие заявки отсортированы по совпадению, с проверкой бюджета.

Запуск:  streamlit run app.py
"""

import altair as alt
import pandas as pd
import streamlit as st

import ai
import core

# Палитра для графиков: слоты 1 и 2 проверенной категориальной палитры
SERIES_1 = "#2a78d6"   # синий
SERIES_2 = "#eb6834"   # оранжевый
INK_MUTED = "#52514e"

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

tab_customer, tab_contractor, tab_market = st.tabs(
    ["🙍 Я заказчик", "🎥 Я подрядчик", "📊 Рынок"]
)


def find_example(text):
    """Если текст совпал с готовым примером — вернуть его (для демо-режима)."""
    for example in EXAMPLES:
        if example["text"].strip() == (text or "").strip():
            return example
    return None


# ==========================================================================
# ВКЛАДКА 1. ЗАКАЗЧИК
# ==========================================================================
def build_brief(text):
    """Собирает бриф из свободного текста тем способом, который доступен."""
    example = find_example(text)
    if AI_ON:
        brief, source = ai.parse_request_ai(text, CONTRACTORS)
    elif example:
        brief, source = dict(example["ai_brief"]), "demo"
    else:
        brief, source = core.parse_request_offline(text), "offline"
    return brief, source, example


def explain(brief, results, example_title):
    """Объяснения по каждому подрядчику: от модели или заготовленные."""
    if AI_ON:
        return ai.explain_matches_ai(brief, results)
    for example in EXAMPLES:
        if example["title"] == example_title:
            return example.get("ai_explanations", {})
    return {}


def recalculate(brief):
    """Пересчитывает подбор и объяснения и кладёт их в состояние страницы."""
    results = core.match(brief, CONTRACTORS, top_n=5)
    st.session_state.results = results
    st.session_state.explanations = explain(brief, results, st.session_state.get("example_title"))


with tab_customer:
    if "request_text" not in st.session_state:
        st.session_state.request_text = EXAMPLES[0]["text"]

    st.subheader("1. Запрос заказчика")
    st.caption("Нажмите готовый пример или напишите свой текст.")

    example_cols = st.columns(len(EXAMPLES))
    for col, example in zip(example_cols, EXAMPLES):
        if col.button(example["title"], use_container_width=True, key="ex_" + example["title"]):
            st.session_state.request_text = example["text"]
            st.session_state.pop("brief", None)

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
        else:
            with st.spinner("Разбираю запрос…"):
                brief, source, example = build_brief(request_text)
            st.session_state.brief = brief
            st.session_state.brief_source = source
            st.session_state.brief_start = core.brief_completeness(brief)
            st.session_state.example_title = example["title"] if example else None
            st.session_state.used_text = request_text
            with st.spinner("Подбираю подрядчиков…"):
                recalculate(brief)

    brief = st.session_state.get("brief")

    if brief:
        source = st.session_state.get("brief_source")
        used_text = st.session_state.get("used_text", "")
        results = st.session_state.get("results", [])
        explanations = st.session_state.get("explanations", {})

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
        start = st.session_state.get("brief_start", done)
        label = f"Бриф заполнен на {done}%"
        if done > start:
            label += f"  (было {start}%, +{done - start} п.п. после ваших ответов)"
        st.progress(done / 100, text=label)

        deadline = brief.get("deadline_days")
        fields = st.columns(4)
        fields[0].markdown(f"**Услуга**  \n#### {brief.get('service') or '—'}")
        fields[1].markdown(f"**Город**  \n#### {brief.get('city') or '—'}")
        fields[2].markdown(f"**Бюджет**  \n#### {core.money(brief.get('budget'))}")
        fields[3].markdown(f"**Срок**  \n#### {str(deadline) + ' дн.' if deadline else 'не указан'}")

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

        # ---------------- Уточняющий диалог ----------------
        gaps = core.missing_fields(brief)
        if gaps:
            st.markdown("#### Ответьте на вопросы — бриф дозаполнится, а подбор пересчитается")
            st.caption("Отвечать на все не обязательно: заполните то, что знаете, остальное оставьте пустым.")

            with st.form("clarify"):
                answers = {}
                for field in gaps[:5]:
                    question = core.FOLLOW_UP_QUESTIONS.get(field, field)

                    if field == "service":
                        options = ["не знаю"] + core.all_services(CONTRACTORS)
                        answers[field] = st.selectbox(question, options)
                    elif field == "city":
                        options = ["не знаю"] + core.all_cities(CONTRACTORS)
                        answers[field] = st.selectbox(question, options)
                    elif field == "budget":
                        answers[field] = st.number_input(
                            question + "  (0 — если ещё не знаете)",
                            min_value=0, max_value=50_000_000, value=0, step=10_000,
                        )
                    elif field == "deadline_days":
                        answers[field] = st.number_input(
                            question + "  (0 — если срок не горит)",
                            min_value=0, max_value=365, value=0, step=1,
                        )
                    elif field == "formats":
                        answers[field] = st.text_input(question, placeholder="например: рилс, вертикальное видео")
                    else:
                        answers[field] = st.text_input(question)

                submitted = st.form_submit_button("Дополнить бриф и пересчитать подбор",
                                                  type="primary", use_container_width=True)

            if submitted:
                for field, value in answers.items():
                    if value in (None, "", 0, "не знаю"):
                        continue
                    if field == "formats":
                        brief[field] = [x.strip() for x in str(value).split(",") if x.strip()]
                    elif field in ("budget", "deadline_days"):
                        brief[field] = int(value)
                    else:
                        brief[field] = value
                st.session_state.brief = brief
                with st.spinner("Пересчитываю подбор…"):
                    recalculate(brief)
                st.rerun()
        else:
            st.success("Бриф полный — подрядчику можно отправлять как есть.")

        # ---------------- Подбор ----------------
        st.divider()
        st.subheader("3. Подобранные подрядчики")

        if core.is_vague(brief):
            st.error(
                "**Из этого запроса не удалось понять ничего конкретного** — ни услугу, ни город, "
                "ни бюджет, ни срок. Список ниже собран по рейтингу, а не по вашей задаче: "
                "доверять ему нельзя.\n\n"
                "Напишите хотя бы одним предложением, что нужно сделать — например: "
                "«нужен логотип для кофейни в Астане, бюджет 200 тысяч» — или ответьте "
                "на вопросы выше."
            )

        for place, r in enumerate(results, 1):
            c = r["contractor"]
            with st.container(border=True):
                head, score_col = st.columns([4, 1.15])
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
        brief_text = core.render_brief_text(brief, used_text)
        st.code(brief_text, language=None)

        dl_a, dl_b = st.columns(2)
        dl_a.download_button("Скачать бриф файлом", brief_text, file_name="bref.txt",
                             use_container_width=True, key="dl_customer")
        dl_b.download_button(
            "Скачать подбор в CSV",
            core.to_csv(core.match_rows_for_csv(brief, results)),
            file_name="podbor.csv", mime="text/csv",
            use_container_width=True, key="dl_customer_csv",
        )


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
    profile[0].markdown(f"**Услуга**  \n#### {me['service']}")
    profile[1].markdown(f"**Город**  \n#### {me['city']}")
    profile[2].markdown(f"**Ваша вилка**  \n#### {core.money(me['price_min'])} – {core.money(me['price_max'])}")
    profile[3].markdown(f"**Обычный срок**  \n#### {me['lead_time_days']} дн.")
    st.caption(f"Форматы: {', '.join(me['formats'])} · Стиль: {', '.join(me['styles'])} · Языки: {', '.join(me['languages'])}")

    deals = core.load_deals()
    my_deals = core.deals_by_request(deals, me["id"])
    my_stats = core.deal_stats([d for d in deals if d["contractor_id"] == me["id"]])

    st.divider()
    st.subheader("2. Ваши сделки")

    deal_cols = st.columns(4)
    deal_cols[0].markdown(f"**Ответов отправлено**  \n#### {my_stats['total']}")
    deal_cols[1].markdown(f"**🟢 Взято в работу**  \n#### {my_stats['accept']}")
    deal_cols[2].markdown(f"**🟡 Уточняются**  \n#### {my_stats['clarify']}")
    deal_cols[3].markdown(f"**🔴 Отказы по бюджету**  \n#### {my_stats['decline']}")

    if my_stats["money_in_work"]:
        st.markdown(f"**В работе на сумму: {core.money(my_stats['money_in_work'])}** "
                    "(по заявкам, где заказчик назвал бюджет).")

    if deals:
        with st.expander(f"История всех сделок в системе ({len(deals)})"):
            st.dataframe(
                [{"Время": d["at"], "Подрядчик": d["contractor_name"], "Заказчик": d["customer"],
                  "Услуга": d.get("service") or "—",
                  "Бюджет": core.money(d.get("budget")), "Статус": d["status"]}
                 for d in reversed(deals)],
                use_container_width=True, hide_index=True,
            )
            act_a, act_b = st.columns(2)
            act_b.download_button(
                "Скачать сделки в CSV",
                core.to_csv(core.deals_rows_for_csv(deals)),
                file_name="sdelki.csv", mime="text/csv",
                use_container_width=True, key="dl_deals_csv",
            )
            if act_a.button("Сбросить демо-сделки", use_container_width=True, key="clear_deals"):
                core.clear_deals()
                st.rerun()

    st.divider()
    st.subheader("3. Входящие заявки")

    filter_cols = st.columns(3)
    min_score = filter_cols[0].slider("Показывать заявки с совпадением от, %", 0, 100, 50, step=5)
    hide_low = filter_cols[1].toggle("Скрыть заказчиков не по бюджету", value=False)
    only_full = filter_cols[2].toggle("Только заявки с полным брифом", value=False)
    hide_answered = st.toggle("Скрыть заявки, на которые уже ответил", value=False)

    rows = core.incoming_for(me, REQUESTS, min_score=min_score)
    if hide_low:
        rows = [r for r in rows if r["budget_code"] != "low"]
    if only_full:
        rows = [r for r in rows if r["completeness"] >= 85]
    if hide_answered:
        rows = [r for r in rows if r["request"]["id"] not in my_deals]

    total = len(REQUESTS)
    fits = sum(1 for r in rows if r["budget_code"] in ("fits", "above"))
    st.markdown(
        f"Всего заявок в системе: **{total}**. Подходят вам: **{len(rows)}**, "
        f"из них по бюджету: **{fits}**."
    )

    if rows:
        st.download_button(
            "Скачать эти заявки в CSV",
            core.to_csv(core.incoming_rows_for_csv(rows)),
            file_name="zayavki.csv", mime="text/csv",
            key="dl_incoming_csv",
        )
    else:
        st.info("Под текущие фильтры заявок нет. Сдвиньте ползунок совпадения влево.")

    for r in rows:
        request = r["request"]
        brief = r["brief"]
        quality, quality_hint = core.brief_quality_label(brief)

        with st.container(border=True):
            head, score_col = st.columns([4, 1.15])
            head.markdown(
                f"### {request['customer']}\n"
                f"{brief.get('service') or '—'} · {brief.get('city') or '—'} · "
                f"бюджет {core.money(brief.get('budget'))} · "
                f"срок {str(brief.get('deadline_days')) + ' дн.' if brief.get('deadline_days') else 'не указан'} · "
                f"{request['date']}"
            )
            score_col.metric("Совпадение", f"{r['score']}%")

            deal = my_deals.get(request["id"])
            if deal:
                icon = core.DEAL_MODES[deal["mode"]][1]
                st.success(f"{icon} Вы ответили {deal['at']}: **{deal['status']}**")

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

                send_col, download_col = st.columns(2)
                if send_col.button("Отправить ответ и записать сделку",
                                   type="primary", use_container_width=True,
                                   key="send_" + request["id"]):
                    core.add_deal(request, me, mode_key, reply)
                    st.rerun()
                download_col.download_button("Скачать ответ файлом", reply,
                                             file_name=f"otvet_{request['id']}.txt",
                                             use_container_width=True,
                                             key="dl_" + request["id"])


# ==========================================================================
# ВКЛАДКА 3. РЫНОК
# ==========================================================================
def bar_chart(data, y_field, y_title, color_field, color_domain, x_title, height):
    """Горизонтальная столбчатая диаграмма с двумя рядами."""
    return (
        alt.Chart(data, height=height)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=11)
        .encode(
            y=alt.Y(f"{y_field}:N", title=None, sort=None,
                    axis=alt.Axis(labelLimit=220, domain=False, ticks=False,
                                  labelColor=INK_MUTED, titleColor=INK_MUTED)),
            x=alt.X("value:Q", title=x_title,
                    axis=alt.Axis(grid=True, gridColor="#e8e8e6", domain=False,
                                  ticks=False, labelColor=INK_MUTED, titleColor=INK_MUTED)),
            yOffset=alt.YOffset(f"{color_field}:N", sort=color_domain),
            color=alt.Color(
                f"{color_field}:N",
                title=None,
                scale=alt.Scale(domain=color_domain, range=[SERIES_1, SERIES_2]),
                legend=alt.Legend(orient="top", labelColor=INK_MUTED),
            ),
            tooltip=[
                alt.Tooltip(f"{y_field}:N", title=y_title),
                alt.Tooltip(f"{color_field}:N", title=" "),
                alt.Tooltip("value:Q", title=x_title),
            ],
        )
        .configure_view(strokeWidth=0)
    )


with tab_market:
    stats = core.market_stats(CONTRACTORS, REQUESTS)

    st.subheader("Что именно ломает сделки на креативном рынке")
    st.download_button(
        "Скачать сводку в CSV",
        core.to_csv(core.market_rows_for_csv(stats)),
        file_name="rynok.csv", mime="text/csv", key="dl_market_csv",
    )
    st.caption(
        f"Посчитано по демонстрационным данным: {len(REQUESTS)} заявок заказчиков "
        f"и {len(CONTRACTORS)} подрядчиков. Все цифры пересчитываются из данных, не вписаны руками."
    )

    # ---------------- Боль заказчика ----------------
    st.markdown("### 🙍 Боль заказчика: запрос не равен брифу")

    tiles = st.columns(4)
    tiles[0].metric("Запрос как есть", f"{stats['completeness_before']}%")
    tiles[1].metric("После разбора", f"{stats['completeness_after']}%",
                    delta=f"+{stats['lift']} п.п.")
    tiles[2].metric("Без бюджета",
                    f"{stats['no_budget']} из {stats['total']}",
                    delta=f"{round(stats['no_budget'] / stats['total'] * 100)}% заявок",
                    delta_color="inverse")
    tiles[3].metric("Без срока",
                    f"{stats['no_deadline']} из {stats['total']}",
                    delta=f"{round(stats['no_deadline'] / stats['total'] * 100)}% заявок",
                    delta_color="inverse")

    st.markdown(
        f"**Заказчик в среднем присылает бриф, заполненный на {stats['completeness_before']}%.** "
        f"После разбора запроса приложением — **{stats['completeness_after']}%**. "
        f"Это {stats['lift']} процентных пунктов, которые подрядчику больше не нужно вытягивать перепиской."
    )

    before_after = pd.DataFrame(
        [{"Заказчик": r["customer"], "Ряд": "Исходный запрос", "value": r["before"]} for r in stats["rows"]] +
        [{"Заказчик": r["customer"], "Ряд": "После разбора", "value": r["after"]} for r in stats["rows"]]
    )
    st.altair_chart(
        bar_chart(before_after, "Заказчик", "Заказчик", "Ряд",
                  ["Исходный запрос", "После разбора"], "Полнота брифа, %", 430),
        use_container_width=True,
    )
    with st.expander("Показать те же данные таблицей"):
        table = [{"Заказчик": r["customer"],
                  "Исходный запрос, %": r["before"],
                  "После разбора, %": r["after"],
                  "Прирост, п.п.": r["after"] - r["before"]} for r in stats["rows"]]
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Скачать в CSV", core.to_csv(table),
                           file_name="polnota_brifov.csv", mime="text/csv",
                           key="dl_briefs_csv")

    st.divider()

    # ---------------- Боль подрядчика ----------------
    st.markdown("### 🎥 Боль подрядчика: переписка, которая ничем не кончится")

    tiles2 = st.columns(4)
    tiles2[0].metric("Профильных пар", stats["relevant_pairs"],
                     help="Пары «подрядчик — заявка», где профиль подрядчика подходит заявке")
    tiles2[1].metric("Тупик по бюджету", stats["bad_budget_pairs"],
                     delta=f"{stats['wasted_share']}% впустую", delta_color="inverse",
                     help="Профиль подходит, но по деньгам не сойдутся")
    tiles2[2].metric("Рынок закрывает", f"{stats['matched']} из {stats['total']}",
                     help="Заявки, на которые нашёлся подрядчик по профилю и по бюджету")
    tiles2[3].metric("Простаивают", f"{len(stats['idle'])} из {len(CONTRACTORS)}",
                     help="Подрядчики, которым не подошла ни одна заявка")

    st.markdown(
        f"**{stats['wasted_share']}% обращений, которые формально подходят подрядчику по профилю, "
        f"не сойдутся по бюджету.** Сегодня это выясняется после трёх дней переписки. "
        f"В приложении — до первого сообщения, на вкладке «Я подрядчик»."
    )

    if stats["reasons"]:
        st.markdown("**Почему заявки остаются без исполнителя:**")
        for reason, count in sorted(stats["reasons"].items(), key=lambda x: -x[1]):
            word = "заявка" if count == 1 else ("заявки" if count < 5 else "заявок")
            st.markdown(f"- {reason} — **{count}** {word} из {stats['total']}")
    if stats["idle"]:
        st.markdown("**Простаивают без подходящих заявок:** " +
                    ", ".join(f"{c['name']} ({c['service']})" for c in stats["idle"]))

    st.divider()

    # ---------------- Спрос и предложение ----------------
    st.markdown("### ⚖️ Спрос и предложение по услугам")
    st.caption("Где подрядчиков больше, чем заявок, — там конкуренция. Где наоборот — там дефицит.")

    demand_supply = pd.DataFrame(
        [{"Услуга": d["service"], "Ряд": "Заявок (спрос)", "value": d["demand"]} for d in stats["demand_supply"]] +
        [{"Услуга": d["service"], "Ряд": "Подрядчиков (предложение)", "value": d["supply"]} for d in stats["demand_supply"]]
    )
    st.altair_chart(
        bar_chart(demand_supply, "Услуга", "Услуга", "Ряд",
                  ["Заявок (спрос)", "Подрядчиков (предложение)"], "Количество", 560),
        use_container_width=True,
    )
    with st.expander("Показать те же данные таблицей"):
        table = [{"Услуга": d["service"], "Заявок": d["demand"], "Подрядчиков": d["supply"]}
                 for d in stats["demand_supply"]]
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Скачать в CSV", core.to_csv(table),
                           file_name="spros_predlozhenie.csv", mime="text/csv",
                           key="dl_supply_csv")

    # ---------------- Что стало со сделками ----------------
    deals_all = core.load_deals()
    if deals_all:
        st.divider()
        st.markdown("### 🤝 Воронка: что стало с заявками")
        d_stats = core.deal_stats(deals_all)
        funnel = st.columns(4)
        funnel[0].markdown(f"**Заявок всего**  \n#### {stats['total']}")
        funnel[1].markdown(f"**Получили ответ**  \n#### {d_stats['requests_answered']}")
        funnel[2].markdown(f"**🟢 Взято в работу**  \n#### {d_stats['accept']}")
        funnel[3].markdown(f"**🔴 Отказ по бюджету**  \n#### {d_stats['decline']}")
        if d_stats["money_in_work"]:
            st.markdown(f"Подрядчики взяли работы на **{core.money(d_stats['money_in_work'])}**.")
        st.caption("Считается по сделкам, которые вы записали на вкладке «Я подрядчик». "
                   "Сбросить их можно там же, в истории сделок.")
