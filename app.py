"""
fin-agent: 美股 + A 股 财务分析 AI Agent
完全开源，使用用户自己的 LLM API Key

⚠️ 这个文件是 Streamlit 渲染层，所有业务逻辑都在 core/ 包里。
   未来切换前端框架（React/Next.js）时，只需要重写这一层，core/ 完全复用。
"""

import streamlit as st

from core.markets import get_us_market_overview, get_cn_market_overview
from core.sectors import (
    get_us_industry_sectors,
    get_us_size_sectors,
    get_cn_industry_sectors,
    get_cn_region_sectors,
    get_us_sector_history,
    get_cn_sector_history,
)
from core.data import get_company_info, get_financial_data
from core.agent import extract_company_and_intent, generate_analysis
from i18n import t


# ─────────────────────────────────────────
# 页面基本设置
# ─────────────────────────────────────────
st.set_page_config(page_title="fin-agent", page_icon="📊", layout="wide")

if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "messages" not in st.session_state:
    st.session_state.messages = []
for key in [
    "selected_us_industry",
    "selected_us_size",
    "selected_cn_industry",
    "selected_cn_region",
]:
    if key not in st.session_state:
        st.session_state[key] = None

lang = st.session_state.lang


# ─────────────────────────────────────────
# 缓存
# ─────────────────────────────────────────
# 大盘指数和板块数据：30 分钟刷新一次（白天交易时段足够及时）
@st.cache_data(ttl=1800)
def cached_us_market():
    return get_us_market_overview()


@st.cache_data(ttl=1800)
def cached_cn_market():
    return get_cn_market_overview()


@st.cache_data(ttl=1800)
def cached_us_industry():
    return get_us_industry_sectors()


@st.cache_data(ttl=1800)
def cached_us_size():
    return get_us_size_sectors()


@st.cache_data(ttl=1800)
def cached_cn_industry():
    return get_cn_industry_sectors()


@st.cache_data(ttl=1800)
def cached_cn_region():
    return get_cn_region_sectors()


# 历史趋势：1 小时缓存（90 天的数据变化没那么频繁）
@st.cache_data(ttl=3600)
def cached_us_history(ticker: str):
    return get_us_sector_history(ticker)


@st.cache_data(ttl=3600)
def cached_cn_history(name: str):
    return get_cn_sector_history(name)


# ─────────────────────────────────────────
# 侧边栏
# ─────────────────────────────────────────
with st.sidebar:
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
# 渲染辅助函数
# ─────────────────────────────────────────
def _render_index_metrics(data: list, currency_prefix: str = ""):
    """顶部大盘指数卡片"""
    cols = st.columns(len(data))
    for col, item in zip(cols, data):
        with col:
            if item["price"] is not None:
                st.metric(
                    label=item["label"],
                    value=f"{currency_prefix}{item['price']}",
                    delta=f"{item['change_pct']}%",
                )
            else:
                st.metric(label=item["label"], value="—")


def _render_sector_table(sectors: list, has_inflow: bool, key_prefix: str, session_key: str):
    """渲染板块列表，每行带「查看历史趋势」按钮"""
    if not sectors:
        st.caption("暂无数据 / No data")
        return

    if has_inflow:
        head_cols = st.columns([4, 2, 2, 3, 2])
        head_cols[0].caption("板块 / Sector")
        head_cols[1].caption("最新价 / Price")
        head_cols[2].caption("涨跌幅 / %")
        head_cols[3].caption(t("main_inflow", lang) + " (亿)")
        head_cols[4].caption("")
    else:
        head_cols = st.columns([4, 2, 2, 2])
        head_cols[0].caption("板块 / Sector")
        head_cols[1].caption("最新价 / Price")
        head_cols[2].caption("涨跌幅 / %")
        head_cols[3].caption("")

    for idx, item in enumerate(sectors):
        change = item.get("change_pct")
        change_str = f"{change:+.2f}%" if change is not None else "—"
        color = "🟢" if (change or 0) > 0 else ("🔴" if (change or 0) < 0 else "⚪")

        if has_inflow:
            cols = st.columns([4, 2, 2, 3, 2])
            cols[0].write(f"{color} {item['label']}")
            cols[1].write(item.get("price") if item.get("price") is not None else "—")
            cols[2].write(change_str)
            inflow = item.get("main_inflow_yi")
            cols[3].write(f"{inflow:+.2f}" if inflow is not None else "—")
            if cols[4].button(t("view_history", lang), key=f"{key_prefix}_{idx}"):
                st.session_state[session_key] = item
        else:
            cols = st.columns([4, 2, 2, 2])
            cols[0].write(f"{color} {item['label']}")
            cols[1].write(item.get("price") if item.get("price") is not None else "—")
            cols[2].write(change_str)
            if cols[3].button(t("view_history", lang), key=f"{key_prefix}_{idx}"):
                st.session_state[session_key] = item


def _render_history_chart(selected: dict, market: str):
    """渲染选中板块的历史走势"""
    if not selected:
        st.caption(t("select_sector", lang))
        return

    st.markdown(f"**{t('history_title', lang, name=selected['label'])}**")
    with st.spinner(t("loading_history", lang)):
        if market == "us":
            history = cached_us_history(selected["ticker"])
        else:
            history = cached_cn_history(selected["label"])

    if not history:
        st.warning(t("no_history_data", lang))
        return

    import pandas as pd
    df = pd.DataFrame(history, columns=["date", "close"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    st.line_chart(df)


# ─────────────────────────────────────────
# 主页头部
# ─────────────────────────────────────────
st.title(t("app_title", lang))
st.caption(t("app_subtitle", lang))


# ─────────────────────────────────────────
# 市场概览（合并大盘指数 + 板块）
# ─────────────────────────────────────────
st.subheader(t("industry_overview", lang))

market_us, market_cn = st.tabs([t("us_market", lang), t("cn_market", lang)])

# ─── 美股 ───
with market_us:
    with st.spinner(t("thinking", lang)):
        us_index_data = cached_us_market()
    _render_index_metrics(us_index_data, currency_prefix="$")

    st.markdown("---")

    sub_us_industry, sub_us_size = st.tabs([
        t("us_industry_sectors", lang),
        t("us_size_sectors", lang),
    ])

    with sub_us_industry:
        with st.spinner(t("thinking", lang)):
            data = cached_us_industry()
        _render_sector_table(data, has_inflow=False, key_prefix="us_ind", session_key="selected_us_industry")
        _render_history_chart(st.session_state.selected_us_industry, market="us")

    with sub_us_size:
        with st.spinner(t("thinking", lang)):
            data = cached_us_size()
        _render_sector_table(data, has_inflow=False, key_prefix="us_size", session_key="selected_us_size")
        _render_history_chart(st.session_state.selected_us_size, market="us")

# ─── A 股 ───
with market_cn:
    with st.spinner(t("thinking", lang)):
        cn_index_data = cached_cn_market()
    _render_index_metrics(cn_index_data, currency_prefix="")

    st.markdown("---")

    sub_cn_industry, sub_cn_region = st.tabs([
        t("cn_industry_sectors", lang),
        t("cn_region_sectors", lang),
    ])

    with sub_cn_industry:
        with st.spinner(t("thinking", lang)):
            data = cached_cn_industry()
        _render_sector_table(data, has_inflow=True, key_prefix="cn_ind", session_key="selected_cn_industry")
        _render_history_chart(st.session_state.selected_cn_industry, market="cn")

    with sub_cn_region:
        with st.spinner(t("thinking", lang)):
            data = cached_cn_region()
        _render_sector_table(data, has_inflow=False, key_prefix="cn_reg", session_key="selected_cn_region")
        _render_history_chart(st.session_state.selected_cn_region, market="cn")

st.divider()


# ─────────────────────────────────────────
# 聊天分析
# ─────────────────────────────────────────
st.subheader(t("chat_title", lang))

if not llm_api_key:
    st.info(t("config_prompt", lang))
    st.stop()

st.caption(t("chat_hint", lang))

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input(t("chat_input", lang))

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
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

            with st.spinner(t("fetching_data", lang)):
                company_info = get_company_info(ticker)
                if not company_info or not company_info.get("name"):
                    company_info = {
                        "ticker": ticker,
                        "market": market_hint or "us",
                        "name": company_name or ticker,
                    }
                financial_data = get_financial_data(ticker, period)
                market = company_info["market"]

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
