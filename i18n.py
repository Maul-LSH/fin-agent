"""
i18n.py — 中英文翻译模块
"""

TRANSLATIONS = {
    "zh": {
        # Sidebar
        "config": "⚙️ 配置",
        "config_note": "API Key 只存于你本地浏览器，不会上传到任何服务器。",
        "language": "🌐 Language / 语言",
        "llm_provider": "LLM 提供商",
        "llm_api_key": "LLM API Key",
        "llm_api_key_help": "Claude / OpenAI / DeepSeek 的 API Key",
        "claude_code_note": "💡 如果你使用 Claude Code，选择 Claude 选项并填入相同的 API Key 即可。",
        "disclaimer": "⚠️ 本工具仅供学习使用，所有分析不构成投资建议。",
        # Main page
        "app_title": "📊 fin-agent",
        "app_subtitle": "AI 驱动的股票财务分析工具 · 美股 & A 股 · 完全开源",
        "config_prompt": "👈 请先在左侧填入你的 LLM API Key 以开始使用。",
        "industry_overview": "🗺️ 市场概览",
        "us_market": "美股市场",
        "cn_market": "A 股市场",
        "chat_title": "💬 开始分析",
        "chat_hint": "试试：「分析苹果公司2024年的财务状况」「Tesla 估值合理吗」「比较茅台和五粮液的风险」",
        "chat_input": "输入你的问题...",
        # Agent process
        "thinking": "正在分析...",
        "no_company": "没有识别到具体的公司，请告诉我你想分析哪家公司？",
        "company_not_found": "未找到「{name}」的股票信息，请检查公司名称或股票代码。",
        "identified": "🔍 已识别：{name}（{ticker}）· 分析维度：{types} · 时间：{period}",
        "fetching_data": "正在拉取财务数据...",
        "generating_analysis": "正在生成分析报告...",
        "error_prefix": "分析过程出错：",
        "error_suffix": "\n\n请检查 API Key 是否正确，或稍后重试。",
        # Analysis types
        "type_financial": "财务",
        "type_valuation": "估值",
        "type_risk": "风险",
    },
    "en": {
        # Sidebar
        "config": "⚙️ Settings",
        "config_note": "API keys stay in your browser session only, never uploaded.",
        "language": "🌐 Language / 语言",
        "llm_provider": "LLM Provider",
        "llm_api_key": "LLM API Key",
        "llm_api_key_help": "API key for Claude / OpenAI / DeepSeek",
        "claude_code_note": "💡 If you use Claude Code, select Claude and use the same API key.",
        "disclaimer": "⚠️ For educational use only. Nothing here is investment advice.",
        # Main page
        "app_title": "📊 fin-agent",
        "app_subtitle": "AI-powered financial analysis · US & CN stocks · Fully open source",
        "config_prompt": "👈 Please enter your LLM API key in the sidebar to begin.",
        "industry_overview": "🗺️ Market Overview",
        "us_market": "US Market",
        "cn_market": "China A-Shares",
        "chat_title": "💬 Start Analysis",
        "chat_hint": "Try: \"Analyze Apple's 2024 financials\" / \"Is Tesla overvalued?\" / \"Compare NVDA and AMD risk\"",
        "chat_input": "Type your question...",
        # Agent process
        "thinking": "Analyzing...",
        "no_company": "No company identified. Which company would you like to analyze?",
        "company_not_found": "Could not find stock info for \"{name}\". Please check the name or ticker.",
        "identified": "🔍 Identified: {name} ({ticker}) · Analysis: {types} · Period: {period}",
        "fetching_data": "Fetching financial data...",
        "generating_analysis": "Generating analysis report...",
        "error_prefix": "Error during analysis: ",
        "error_suffix": "\n\nPlease check your API key or try again later.",
        # Analysis types
        "type_financial": "Financial",
        "type_valuation": "Valuation",
        "type_risk": "Risk",
    },
}


def t(key: str, lang: str = "zh", **kwargs) -> str:
    """获取翻译文本，支持 {var} 占位符"""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["zh"]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
