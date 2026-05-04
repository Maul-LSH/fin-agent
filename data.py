"""
data.py — 数据获取模块
美股：yfinance（免费，无需 API Key）
A股：AkShare（免费，无需 API Key）
自动根据股票代码格式判断市场
"""

import yfinance as yf
import akshare as ak
import pandas as pd


# ─────────────────────────────────────────
# 市场判断与代码标准化
# ─────────────────────────────────────────
def detect_market(ticker: str) -> str:
    """
    根据 ticker 格式判断市场
    返回 'us' 或 'cn'
    """
    if not ticker:
        return "us"
    ticker = ticker.strip().upper()
    # 纯 6 位数字 → A 股
    if ticker.isdigit() and len(ticker) == 6:
        return "cn"
    # 包含 A 股交易所后缀
    if any(suffix in ticker for suffix in [".SS", ".SZ", ".SH", ".BJ"]):
        return "cn"
    # 默认美股
    return "us"


def normalize_ticker(ticker: str, market: str) -> str:
    """标准化 ticker 格式，方便各数据源使用"""
    ticker = ticker.strip().upper()
    if market == "cn":
        # 提取 6 位数字代码
        digits = "".join(c for c in ticker if c.isdigit())[:6]
        return digits if len(digits) == 6 else ticker
    return ticker


# ─────────────────────────────────────────
# 公司信息查询
# ─────────────────────────────────────────
def get_company_info(ticker: str) -> dict | None:
    """
    根据 ticker 拉取公司基本信息
    返回：{"ticker": "AAPL", "market": "us", "name": "Apple Inc.", ...}
    找不到返回 None
    """
    market = detect_market(ticker)
    norm_ticker = normalize_ticker(ticker, market)

    if market == "us":
        return _get_us_company_info(norm_ticker)
    else:
        return _get_cn_company_info(norm_ticker)


def _get_us_company_info(ticker: str) -> dict | None:
    """yfinance 拉美股公司信息"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # 验证是不是有效 ticker
        if not info or "longName" not in info and "shortName" not in info:
            return None
        return {
            "ticker": ticker,
            "market": "us",
            "name": info.get("longName") or info.get("shortName") or ticker,
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "summary": info.get("longBusinessSummary", "")[:300],
        }
    except Exception:
        return None


def _get_cn_company_info(ticker: str) -> dict | None:
    """AkShare 拉 A 股公司信息"""
    try:
        # 拉取 A 股全量列表，匹配代码
        df = ak.stock_info_a_code_name()
        matched = df[df["code"] == ticker]
        if matched.empty:
            return None
        return {
            "ticker": ticker,
            "market": "cn",
            "name": matched.iloc[0]["name"],
        }
    except Exception:
        return None


# ─────────────────────────────────────────
# 财务数据获取（统一入口）
# ─────────────────────────────────────────
def get_financial_data(ticker: str, period: str) -> dict:
    """
    根据 ticker 自动判断市场，拉取对应财务数据
    period: 年份字符串，如 "2024"
    """
    market = detect_market(ticker)
    norm_ticker = normalize_ticker(ticker, market)

    if market == "us":
        return _get_us_financial_data(norm_ticker, period)
    else:
        return _get_cn_financial_data(norm_ticker, period)


# ─────────────────────────────────────────
# 美股财务数据（yfinance）
# ─────────────────────────────────────────
def _get_us_financial_data(ticker: str, period: str) -> dict:
    result = {"market": "us", "ticker": ticker, "period": period}

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # ── 估值数据 ──
        result["valuation"] = {
            "PE (TTM)": _round(info.get("trailingPE")),
            "Forward PE": _round(info.get("forwardPE")),
            "PB": _round(info.get("priceToBook")),
            "PS (TTM)": _round(info.get("priceToSalesTrailing12Months")),
            "Market Cap (B)": _round(info.get("marketCap", 0) / 1e9, 2),
            "Dividend Yield (%)": _round((info.get("dividendYield") or 0) * 100, 2),
            "52W High": _round(info.get("fiftyTwoWeekHigh")),
            "52W Low": _round(info.get("fiftyTwoWeekLow")),
            "Beta": _round(info.get("beta")),
        }

        # ── 利润表 ──
        income = stock.income_stmt
        if income is not None and not income.empty:
            col = _find_year_column(income.columns, period)
            if col is not None:
                row = income[col]
                result["income"] = {
                    "Revenue (B)": _to_billion(row.get("Total Revenue")),
                    "Gross Profit (B)": _to_billion(row.get("Gross Profit")),
                    "Operating Income (B)": _to_billion(row.get("Operating Income")),
                    "Net Income (B)": _to_billion(row.get("Net Income")),
                    "EPS (Basic)": _round(row.get("Basic EPS")),
                }
                # 计算利润率
                rev = row.get("Total Revenue")
                if rev and rev > 0:
                    gp = row.get("Gross Profit")
                    ni = row.get("Net Income")
                    if gp:
                        result["income"]["Gross Margin (%)"] = _round(gp / rev * 100, 2)
                    if ni:
                        result["income"]["Net Margin (%)"] = _round(ni / rev * 100, 2)

        # ── 资产负债表 ──
        balance = stock.balance_sheet
        if balance is not None and not balance.empty:
            col = _find_year_column(balance.columns, period)
            if col is not None:
                row = balance[col]
                total_assets = row.get("Total Assets")
                total_liab = row.get("Total Liabilities Net Minority Interest")
                result["balance"] = {
                    "Total Assets (B)": _to_billion(total_assets),
                    "Total Liabilities (B)": _to_billion(total_liab),
                    "Stockholders Equity (B)": _to_billion(row.get("Stockholders Equity")),
                    "Cash & Equivalents (B)": _to_billion(row.get("Cash And Cash Equivalents")),
                    "Total Debt (B)": _to_billion(row.get("Total Debt")),
                }
                if total_assets and total_liab:
                    result["balance"]["Debt-to-Asset Ratio (%)"] = _round(total_liab / total_assets * 100, 2)

        # ── 现金流 ──
        cashflow = stock.cashflow
        if cashflow is not None and not cashflow.empty:
            col = _find_year_column(cashflow.columns, period)
            if col is not None:
                row = cashflow[col]
                result["cashflow"] = {
                    "Operating Cash Flow (B)": _to_billion(row.get("Operating Cash Flow")),
                    "Capital Expenditure (B)": _to_billion(row.get("Capital Expenditure")),
                    "Free Cash Flow (B)": _to_billion(row.get("Free Cash Flow")),
                }

        # ── 关键指标计算 ──
        if "income" in result and "balance" in result:
            try:
                ni = stock.income_stmt[col].get("Net Income") if col is not None else None
                eq = stock.balance_sheet[col].get("Stockholders Equity") if col is not None else None
                if ni and eq and eq > 0:
                    result.setdefault("indicators", {})["ROE (%)"] = _round(ni / eq * 100, 2)
            except Exception:
                pass

    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────
# A股财务数据（AkShare）
# ─────────────────────────────────────────
def _get_cn_financial_data(ticker: str, period: str) -> dict:
    result = {"market": "cn", "ticker": ticker, "period": period}

    # ── 估值数据（实时行情）──
    try:
        spot = ak.stock_zh_a_spot_em()
        matched = spot[spot["代码"] == ticker]
        if not matched.empty:
            row = matched.iloc[0]
            result["valuation"] = {
                "PE (TTM)": _round(row.get("市盈率-动态")),
                "PB": _round(row.get("市净率")),
                "总市值(亿元)": _round((row.get("总市值") or 0) / 1e8, 2),
                "流通市值(亿元)": _round((row.get("流通市值") or 0) / 1e8, 2),
                "最新价": _round(row.get("最新价")),
                "52周最高": _round(row.get("52周最高")),
                "52周最低": _round(row.get("52周最低")),
            }
    except Exception as e:
        result["valuation_error"] = str(e)

    # ── 财务摘要（包含核心指标）──
    try:
        abstract = ak.stock_financial_abstract(symbol=ticker)
        if abstract is not None and not abstract.empty:
            # 找到对应年报列（YYYY1231）
            year_col = f"{period}1231"
            if year_col in abstract.columns:
                # 提取关键指标
                indicators_row = {}
                for _, r in abstract.iterrows():
                    key = r.get("指标")
                    val = r.get(year_col)
                    if key and pd.notna(val):
                        indicators_row[key] = val

                # 利润表数据
                result["income"] = {
                    "营业总收入(亿元)": _to_yi(indicators_row.get("营业总收入")),
                    "归母净利润(亿元)": _to_yi(indicators_row.get("归母净利润")),
                    "扣非净利润(亿元)": _to_yi(indicators_row.get("扣非净利润")),
                    "营业总收入同比增长(%)": _round(indicators_row.get("营业总收入同比增长")),
                    "归母净利润同比增长(%)": _round(indicators_row.get("归母净利润同比增长")),
                }

                # 关键指标
                result["indicators"] = {
                    "ROE(%)": _round(indicators_row.get("净资产收益率")),
                    "毛利率(%)": _round(indicators_row.get("销售毛利率")),
                    "净利率(%)": _round(indicators_row.get("销售净利率")),
                    "EPS(元)": _round(indicators_row.get("基本每股收益")),
                    "每股净资产(元)": _round(indicators_row.get("每股净资产")),
                }

                # 资产负债数据
                result["balance"] = {
                    "总资产(亿元)": _to_yi(indicators_row.get("资产总计")),
                    "总负债(亿元)": _to_yi(indicators_row.get("负债合计")),
                    "股东权益(亿元)": _to_yi(indicators_row.get("归属母公司股东权益合计")),
                    "资产负债率(%)": _round(indicators_row.get("资产负债率")),
                }

                # 现金流
                result["cashflow"] = {
                    "经营现金流(亿元)": _to_yi(indicators_row.get("经营活动产生的现金流量净额")),
                    "投资现金流(亿元)": _to_yi(indicators_row.get("投资活动产生的现金流量净额")),
                    "筹资现金流(亿元)": _to_yi(indicators_row.get("筹资活动产生的现金流量净额")),
                }
    except Exception as e:
        result["financial_error"] = str(e)

    return result


# ─────────────────────────────────────────
# 行业概览（主页卡片）
# ─────────────────────────────────────────
def get_us_market_overview() -> list:
    """获取美股几个核心指数/行业的简要数据"""
    tickers = ["SPY", "QQQ", "DIA", "IWM"]
    labels = ["S&P 500", "NASDAQ 100", "Dow Jones", "Russell 2000"]
    results = []

    for ticker, label in zip(tickers, labels):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get("regularMarketPrice") or info.get("previousClose", 0)
            change = info.get("regularMarketChangePercent", 0) or 0
            results.append({
                "label": label,
                "ticker": ticker,
                "price": _round(price),
                "change_pct": _round(change, 2),
            })
        except Exception:
            results.append({"label": label, "ticker": ticker, "price": None, "change_pct": None})

    return results


def get_cn_market_overview() -> list:
    """获取 A 股几个核心指数的简要数据"""
    indices = [
        ("000001", "上证指数"),
        ("399001", "深证成指"),
        ("399006", "创业板指"),
        ("000300", "沪深300"),
    ]
    results = []

    try:
        df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        for code, label in indices:
            try:
                # 简化处理：直接查询
                row = df[df["代码"] == code]
                if not row.empty:
                    r = row.iloc[0]
                    results.append({
                        "label": label,
                        "ticker": code,
                        "price": _round(r.get("最新价")),
                        "change_pct": _round(r.get("涨跌幅"), 2),
                    })
                else:
                    results.append({"label": label, "ticker": code, "price": None, "change_pct": None})
            except Exception:
                results.append({"label": label, "ticker": code, "price": None, "change_pct": None})
    except Exception:
        # 失败时返回占位数据
        for code, label in indices:
            results.append({"label": label, "ticker": code, "price": None, "change_pct": None})

    return results


# ─────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────
def _round(val, digits: int = 2):
    """安全四舍五入"""
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(val), digits)
    except (TypeError, ValueError):
        return None


def _to_billion(val):
    """美元数值 → 十亿单位"""
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(val) / 1e9, 2)
    except (TypeError, ValueError):
        return None


def _to_yi(val):
    """人民币数值 → 亿元单位"""
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(val) / 1e8, 2)
    except (TypeError, ValueError):
        return None


def _find_year_column(columns, year: str):
    """在 yfinance 财报的列中找到对应年份的列"""
    for col in columns:
        try:
            if hasattr(col, "year") and str(col.year) == str(year):
                return col
        except Exception:
            continue
    # 退而求其次：返回最近的一列
    return columns[0] if len(columns) > 0 else None
