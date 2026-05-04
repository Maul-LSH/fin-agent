"""
fin-agent: 美股 + A 股 财务分析 AI Agent
完全开源，使用用户自己的 LLM API Key
"""

import streamlit as st
from data import (
    get_company_info,
    get_financial_data,
    get_us_market_overview,
    get_cn_market_overview,
)
from agent import extract_company_and_intent, generate_analysis
from i18n import t


# ─────────────────────────────────────────
# 页面基本设置
# ─────────────────────────────────────────
st.set_page_config(
    page_title="fin-agent",
    page_icon="📊",
    layout="wide",
)

# 初始化语言
if "lang" not in st.session_state:
    st.session_state.lang = "zh"

lang = st.session_state.lang


# ─────────────────────────────────────────
# 侧边栏配置
# ─────────────────────────────────────────
with st.sidebar:
    # 语言切换
    lang_choice = st.radio(
        t("language", lang),
        options=["中文", "English"],
        horizontal=True,
        index=0 if lang == "zh" else 1,
    )
    new_lang = "zh" if lang_choice == "中文" else "en"
    if new_lang != lang:
        st.session_state.lang = new_lang
        st.rerun()

    st.divider()
    st.title(t("config", lang))
    st.caption(t("config_note", lang))

    llm_provider = st.selectbox(
        t("llm_provider", lang),
        options=["Claude (Anthropic)", "OpenAI", "DeepSeek"],
    )

    llm_api_key = st.text_input(
        t("llm_api_key", lang),
        type="password",
        help=t("llm_api_key_help", lang),
    )

    st.caption(t("claude_code_note", lang))

    st.divider()
    st.caption(t("disclaimer", lang))


# ─────────────────────────────────────────
# 主页头部（永远显示）
# ─────────────────────────────────────────
st.title(t("app_title", lang))
st.caption(t("app_subtitle", lang))


# ─────────────────────────────────────────
# 市场概览（无需 API Key 即可查看）
# ─────────────────────────────────────────
st.subheader(t("industry_overview", lang))

tab_us, tab_cn = st.tabs([t("us_market", lang), t("cn_market", lang)])

with tab_us:
    with st.spinner(t("thinking", lang)):
        us_data = get_us_market_overview()
    cols = st.columns(len(us_data))
    for col, item in zip(cols, us_data):
        with col:
            if item["price"] is not None:
                st.metric(
                    label=item["label"],
                    value=f"${item['price']}",
                    delta=f"{item['change_pct']}%",
                )
            else:
                st.metric(label=item["label"], value="—")

with tab_cn:
    with st.spinner(t("thinking", lang)):
        cn_data = get_cn_market_overview()
    cols = st.columns(len(cn_data))
    for col, item in zip(cols, cn_data):
        with col:
            if item["price"] is not None:
                st.metric(
                    label=item["label"],
                    value=f"{item['price']}",
                    delta=f"{item['change_pct']}%",
                )
            else:
                st.metric(label=item["label"], value="—")

st.divider()


# ─────────────────────────────────────────
# 聊天主区域（需要 API Key）
# ─────────────────────────────────────────
st.subheader(t("chat_title", lang))

# 没填 API Key 时，显示友好提示但不阻塞页面
if not llm_api_key:
    st.info(t("config_prompt", lang))
    st.stop()

st.caption(t("chat_hint", lang))

# 初始化对话历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 展示历史对话
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 用户输入
user_input = st.chat_input(t("chat_input", lang))

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            # 第一步：理解意图
            with st.spinner(t("thinking", lang)):
                intent = extract_company_and_intent(
                    user_input,
                    llm_api_key=llm_api_key,
                    provider=llm_provider,
                    lang=lang,
                )

            ticker = intent.get("ticker")
            company_name = intent.get("company_name")

            if not ticker:
                reply = t("no_company", lang)
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
                st.stop()

            # 类型映射成显示文本
            type_labels = {
                "financial": t("type_financial", lang),
                "valuation": t("type_valuation", lang),
                "risk": t("type_risk", lang),
            }
            analysis_types = intent.get("analysis_types", ["financial", "valuation", "risk"])
            types_display = ", ".join([type_labels.get(t_, t_) for t_ in analysis_types])
            period = intent.get("period", "2024")
            market_hint = intent.get("market", "us")

            st.info(
                t(
                    "identified",
                    lang,
                    name=company_name or ticker,
                    ticker=ticker,
                    types=types_display,
                    period=period,
                )
            )

            # 第二步：拉取数据（即使 company_info 失败也尝试拉取财务数据）
            with st.spinner(t("fetching_data", lang)):
                company_info = get_company_info(ticker)

                # 即使没拿到详细公司信息，也用 LLM 给的信息构造一个最小数据
                if not company_info:
                    company_info = {
                        "ticker": ticker,
                        "market": market_hint or "us",
                        "name": company_name or ticker,
                    }

                financial_data = get_financial_data(ticker, period)
                market = company_info["market"]

            # 第三步：生成分析
            with st.spinner(t("generating_analysis", lang)):
                analysis = generate_analysis(
                    company_name=company_info["name"],
                    ticker=ticker,
                    market=market,
                    financial_data=financial_data,
                    analysis_types=analysis_types,
                    period=period,
                    llm_api_key=llm_api_key,
                    provider=llm_provider,
                    lang=lang,
                )

            st.markdown(analysis)
            st.session_state.messages.append({"role": "assistant", "content": analysis})

        except Exception as e:
            error_msg = t("error_prefix", lang) + str(e) + t("error_suffix", lang)
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
