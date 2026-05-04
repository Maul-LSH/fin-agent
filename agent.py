"""
agent.py — AI Agent 核心模块
支持的 LLM 提供商：
- Claude (Anthropic) — 官方 SDK，Claude Code 用户也用同一个 Key
- OpenAI (GPT)
- DeepSeek — OpenAI 兼容协议
"""

import json
import re


# ─────────────────────────────────────────
# 统一 LLM 调用接口
# ─────────────────────────────────────────
def call_llm(
    prompt: str,
    system: str,
    api_key: str,
    provider: str,
    max_tokens: int = 2000,
) -> str:
    """根据 provider 路由到对应的 LLM"""
    if "Claude" in provider or "claude" in provider:
        return _call_claude(prompt, system, api_key, max_tokens)
    elif "DeepSeek" in provider or "deepseek" in provider:
        return _call_deepseek(prompt, system, api_key, max_tokens)
    else:
        return _call_openai(prompt, system, api_key, max_tokens)


def _call_claude(prompt: str, system: str, api_key: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_openai(prompt: str, system: str, api_key: str, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def _call_deepseek(prompt: str, system: str, api_key: str, max_tokens: int) -> str:
    """DeepSeek 用 OpenAI 兼容协议，只是换个 base_url"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


# ─────────────────────────────────────────
# 第一步：理解用户意图
# ─────────────────────────────────────────
def extract_company_and_intent(
    user_input: str,
    llm_api_key: str,
    provider: str,
    lang: str = "zh",
) -> dict:
    """
    抽取关键词：公司名、股票代码、分析类型、时间
    LLM 直接给出 ticker，省得我们自己做公司名→代码的映射
    
    返回：
    {
        "company_name": "Apple",
        "ticker": "AAPL",      // 美股直接代码 / A股 6 位数字
        "market": "us" | "cn",
        "analysis_types": ["financial", "valuation", "risk"],
        "period": "2024"
    }
    """

    system = """You are an expert assistant that extracts stock analysis intents from user queries.
You handle BOTH US stocks and China A-shares.

Output STRICT JSON only, no extra text, no markdown.

Schema:
{
  "company_name": string or null,    // company name in original language
  "ticker": string or null,          // US: "AAPL", "TSLA"; A-share: 6-digit code like "600519"
  "market": "us" | "cn" | null,
  "analysis_types": array,           // subset of ["financial", "valuation", "risk"]; default all three
  "period": string                   // year, default "2024"
}

Examples:
Input: "Analyze Apple's 2023 financials"
Output: {"company_name": "Apple", "ticker": "AAPL", "market": "us", "analysis_types": ["financial"], "period": "2023"}

Input: "帮我看看茅台的估值和风险"
Output: {"company_name": "贵州茅台", "ticker": "600519", "market": "cn", "analysis_types": ["valuation", "risk"], "period": "2024"}

Input: "Tesla overvalued?"
Output: {"company_name": "Tesla", "ticker": "TSLA", "market": "us", "analysis_types": ["valuation"], "period": "2024"}

Input: "宁德时代怎么样"
Output: {"company_name": "宁德时代", "ticker": "300750", "market": "cn", "analysis_types": ["financial", "valuation", "risk"], "period": "2024"}

Important:
- For well-known companies, you MUST provide the correct ticker from your knowledge.
- If you don't know the ticker, set ticker to null.
- Default period to "2024" if not specified.
- Default analysis_types to all three if not specified."""

    prompt = f"User query: {user_input}"

    try:
        raw = call_llm(prompt, system, llm_api_key, provider, max_tokens=300)
        # 清理 markdown 代码块
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)
        # 确保字段齐全
        result.setdefault("analysis_types", ["financial", "valuation", "risk"])
        result.setdefault("period", "2024")
        return result
    except Exception:
        return {
            "company_name": None,
            "ticker": None,
            "market": None,
            "analysis_types": ["financial", "valuation", "risk"],
            "period": "2024",
        }


# ─────────────────────────────────────────
# 第二步：生成财务分析
# ─────────────────────────────────────────
def generate_analysis(
    company_name: str,
    ticker: str,
    market: str,
    financial_data: dict,
    analysis_types: list,
    period: str,
    llm_api_key: str,
    provider: str,
    lang: str = "zh",
) -> str:
    """根据财务数据生成结构化分析报告"""

    data_text = _format_financial_data(financial_data)
    instructions = _build_analysis_instructions(analysis_types, lang)

    if lang == "en":
        system = """You are a professional equity analyst who explains financial data in clear, accessible language.

Principles:
1. Base ALL analysis ONLY on the data provided. Never fabricate numbers.
2. Explain technical terms simply so retail investors can follow.
3. Be objective. State facts and observations. NEVER give buy/sell recommendations.
4. Back every conclusion with specific numbers from the data.
5. Always end with: "*This analysis is based solely on public financial data and does not constitute investment advice.*"

Use Markdown formatting. Respond in English."""

        prompt = f"""Please analyze the following company:

Company: {company_name} ({ticker})
Market: {"US Stock" if market == "us" else "China A-Share"}
Period: FY {period}

Financial Data:
{data_text}

Generate a report with these sections:
{instructions}"""
    else:
        system = """你是一名专业的股票分析师，擅长用通俗易懂的语言解读财务数据。

分析原则：
1. 严格只基于提供的数据进行分析，不编造任何数字
2. 用大白话解释专业指标，让普通投资者能看懂
3. 客观中立，只陈述事实，绝不给出买入/卖出建议
4. 每个结论都要有具体数据支撑
5. 报告末尾必须注明：「*以上分析仅基于公开财务数据，不构成投资建议。*」

用 Markdown 格式输出，使用中文回答。"""

        prompt = f"""请对以下公司进行财务分析：

公司：{company_name}（{ticker}）
市场：{"美股" if market == "us" else "A股"}
分析年度：{period}年

财务数据：
{data_text}

请按以下结构生成分析报告：
{instructions}"""

    return call_llm(prompt, system, llm_api_key, provider, max_tokens=2500)


# ─────────────────────────────────────────
# 内部辅助函数
# ─────────────────────────────────────────
def _format_financial_data(data: dict) -> str:
    """把财务数据字典格式化成清晰的文本"""
    lines = []

    section_map = {
        "valuation": "📈 Valuation / 估值",
        "income": "💰 Income Statement / 利润表",
        "balance": "🏦 Balance Sheet / 资产负债表",
        "cashflow": "💵 Cash Flow / 现金流量表",
        "indicators": "📊 Key Indicators / 核心指标",
    }

    for key, title in section_map.items():
        if key in data and isinstance(data[key], dict):
            section_lines = []
            for metric, value in data[key].items():
                if value is not None:
                    section_lines.append(f"  - {metric}: {value}")
            if section_lines:
                lines.append(f"\n{title}:")
                lines.extend(section_lines)

    # 如有错误，注明
    for key, value in data.items():
        if key.endswith("_error") and value:
            lines.append(f"\n⚠️ {key}: {value}")

    return "\n".join(lines) if lines else "No financial data available."


def _build_analysis_instructions(analysis_types: list, lang: str) -> str:
    """根据分析类型与语言生成对应的指令"""
    instructions = []

    if lang == "en":
        if "financial" in analysis_types:
            instructions.append("""
**1. Financial Health**
- Profitability: Revenue, net income, ROE, gross/net margins — what do they say?
- Solvency: Debt levels, leverage ratios — is the balance sheet healthy?
- Cash flow: Does operating cash flow match net income? Any red flags?
""")
        if "valuation" in analysis_types:
            instructions.append("""
**2. Valuation**
- Interpret current PE, PB, PS levels
- Is the valuation reasonable given the profitability?
- Any standout signals (very cheap or very expensive)?
""")
        if "risk" in analysis_types:
            instructions.append("""
**3. Risk Assessment**
- Financial risks visible in the data (debt, cash burn, etc.)
- Operating risks the numbers reveal
- Overall risk level (Low / Medium / High) with reasoning
""")
        instructions.append("""
**4. One-Line Summary**
A single sentence capturing this company's current financial story.
""")
    else:
        if "financial" in analysis_types:
            instructions.append("""
**一、财务健康度**
- 盈利能力：营收、净利润规模，ROE、毛利率、净利率说明了什么
- 偿债能力：负债水平、杠杆率，资产负债表是否稳健
- 现金流：经营现金流和净利润是否匹配，有没有异常信号
""")
        if "valuation" in analysis_types:
            instructions.append("""
**二、估值分析**
- 解读当前 PE、PB、PS 水平
- 结合盈利能力判断估值是否合理
- 是否有特别突出的信号（极度便宜或极度昂贵）
""")
        if "risk" in analysis_types:
            instructions.append("""
**三、风险排查**
- 财务数据中能看到的财务风险（负债、现金消耗等）
- 数据反映出的经营层面风险
- 整体风险等级（低 / 中 / 高），并说明理由
""")
        instructions.append("""
**四、一句话总结**
用一句话概括这家公司当前的核心财务特征。
""")

    return "\n".join(instructions)
