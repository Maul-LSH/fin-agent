"""
data.py — 数据获取模块
美股：yfinance（免费，无需 API Key）
A股：AkShare（免费，无需 API Key）
自动根据股票代码格式判断市场
"""

import time
import yfinance as yf
import akshare as ak
import pandas as pd


# ─────────────────────────────────────────
# 重试装饰器（应对 Streamlit Cloud 上 yfinance 偶发失败）
# ─────────────────────────────────────────
def _retry(func, retries: int = 2, delay: float = 0.5):
    """简单重试，失败返回 None"""
    for i in range(retries + 1):
        try:
            result = func()
            if result is not None:
                return result
        except Exception:
            pass
        if i < retries:
            time.sleep(delay)
    return None


# ─────────────────────────────────────────
# 市场判断与代码标准化
# ─────────────────────────────────────────
def detect_market(ticker: str) -> str:
    """根据 ticker 格式判断市场，返回 'us' 或 'cn'"""
    if not ticker:
        return "us"
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        return "cn"
    if any(suffix in ticker for suffix in [".SS", ".SZ", ".SH", ".BJ"]):
        return "cn"
    return "us"


def normalize_ticker(ticker: str, market: str) -> str:
    """标准化 ticker 格式"""
    ticker = ticker.strip().upper()
    if market == "cn":
        digits = "".join(c for c in ticker if c.isdigit())[:6]
        return digits if len(digits) == 6 else ticker
    return ticker


# ─────────────────────────────────────────
# 公司信息查询
# ─────────────────────────────────────────
def get_company_info(ticker: str) -> dict | None:
    """
    根据 ticker 拉取公司基本信息
    美股：信任 ticker 本身，即使 yfinance info 失败也返回最小信息
    A股：用 AkShare 验证
    """
    market = detect_market(ticker)
    norm_ticker = normalize_ticker(ticker, market)

    if market == "us":
        return _get_us_company_info(norm_ticker)
    else:
        return _get_cn_company_info(norm_ticker)


def _get_us_company_info(ticker: str) -> dict:
    """
    美股公司信息：信任 ticker，即使拉不到详细 info 也返回基础信息
    避免 yfinance 在 Streamlit Cloud 上间歇性失败导致整个流程中断
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        name = info.get("longName") or info.get("shortName") or ticker
        return {
            "ticker": ticker,
            "market": "us",
            "name": name,
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "summary": (info.get("longBusinessSummary") or "")[:300],
        }
    except Exception:
        # yfinance 失败时仍返回最小信息，让流程继续
        return {
            "ticker": ticker,
            "market": "us",
            "name": ticker,
        }


def _get_cn_company_info(ticker: str) -> dict | None:
    """A 股公司信息：通过 AkShare 验证"""
    def _fetch():
        df = ak.stock_info_a_code_name()
        matched = df[df["code"] == ticker]
        if matched.empty:
            return None
        return {
            "ticker": ticker,
            "market": "cn",
            "name": matched.iloc[0]["name"],
        }

    return _retry(_fetch, retries=1)


# ─────────────────────────────────────────
# 财务数据获取
# ─────────────────────────────────────────
def get_financial_data(ticker: str, period: str) -> dict:
    """根据 ticker 自动判断市场，拉取对应财务数据"""
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
        info = _retry(lambda: stock.info, retries=2) or {}

        # ── 估值数据 ──
        if info:
            result["valuation"] = {
                "PE (TTM)": _round(info.get("trailingPE")),
                "Forward PE": _round(info.get("forwardPE")),
                "PB": _round(info.get("priceToBook")),
                "PS (TTM)": _round(info.get("priceToSalesTrailing12Months")),
                "Market Cap (B)": _round((info.get("marketCap") or 0) / 1e9, 2),
                "Dividend Yield (%)": _round((info.get("dividendYield") or 0) * 100, 2),
                "52W High": _round(info.get("fiftyTwoWeekHigh")),
                "52W Low": _round(info.get("fiftyTwoWeekLow")),
                "Beta": _round(info.get("beta")),
            }

        # ── 利润表 ──
        income = _retry(lambda: stock.income_stmt, retries=2)
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
                rev = row.get("Total Revenue")
                if rev and rev > 0:
                    gp = row.get("Gross Profit")
                    ni = row.get("Net Income")
                    if gp:
                        result["income"]["Gross Margin (%)"] = _round(gp / rev * 100, 2)
                    if ni:
                        result["income"]["Net Margin (%)"] = _round(ni / rev * 100, 2)

        # ── 资产负债表 ──
        balance = _retry(lambda: stock.balance_sheet, retries=2)
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
        cashflow = _retry(lambda: stock.cashflow, retries=2)
        if cashflow is not None and not cashflow.empty:
            col = _find_year_column(cashflow.columns, period)
            if col is not None:
                row = cashflow[col]
                result["cashflow"] = {
                    "Operating Cash Flow (B)": _to_billion(row.get("Operating Cash Flow")),
                    "Capital Expenditure (B)": _to_billion(row.get("Capital Expenditure")),
                    "Free Cash Flow (B)": _to_billion(row.get("Free Cash Flow")),
                }

        # ── ROE 计算 ──
        if "income" in result and "balance" in result:
            try:
                if income is not None and balance is not None:
                    col = _find_year_column(income.columns, period)
                    ni = income[col].get("Net Income") if col is not None else None
                    eq = balance[col].get("Stockholders Equity") if col is not None else None
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

    # 实时行情（估值）
    try:
        spot = _retry(lambda: ak.stock_zh_a_spot_em(), retries=1)
        if spot is not None:
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

    # 财务摘要
    try:
        abstract = _retry(lambda: ak.stock_financial_abstract(symbol=ticker), retries=1)
        if abstract is not None and not abstract.empty:
            year_col = f"{period}1231"
            if year_col in abstract.columns:
                indicators_row = {}
                for _, r in abstract.iterrows():
                    key = r.get("指标")
                    val = r.get(year_col)
                    if key and pd.notna(val):
                        indicators_row[key] = val

                result["income"] = {
                    "营业总收入(亿元)": _to_yi(indicators_row.get("营业总收入")),
                    "归母净利润(亿元)": _to_yi(indicators_row.get("归母净利润")),
                    "扣非净利润(亿元)": _to_yi(indicators_row.get("扣非净利润")),
                    "营业总收入同比增长(%)": _round(indicators_row.get("营业总收入同比增长")),
                    "归母净利润同比增长(%)": _round(indicators_row.get("归母净利润同比增长")),
                }

                result["indicators"] = {
                    "ROE(%)": _round(indicators_row.get("净资产收益率")),
                    "毛利率(%)": _round(indicators_row.get("销售毛利率")),
                    "净利率(%)": _round(indicators_row.get("销售净利率")),
                    "EPS(元)": _round(indicators_row.get("基本每股收益")),
                    "每股净资产(元)": _round(indicators_row.get("每股净资产")),
                }

                result["balance"] = {
                    "总资产(亿元)": _to_yi(indicators_row.get("资产总计")),
                    "总负债(亿元)": _to_yi(indicators_row.get("负债合计")),
                    "股东权益(亿元)": _to_yi(indicators_row.get("归属母公司股东权益合计")),
                    "资产负债率(%)": _round(indicators_row.get("资产负债率")),
                }

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
    """获取美股几个核心指数 ETF 的简要数据"""
    tickers = ["SPY", "QQQ", "DIA", "IWM"]
    labels = ["S&P 500", "NASDAQ 100", "Dow Jones", "Russell 2000"]
    results = []

    for ticker, label in zip(tickers, labels):
        item = {"label": label, "ticker": ticker, "price": None, "change_pct": None}

        # 优先用 history 拉最近的价格（比 info 稳定得多）
        try:
            stock = yf.Ticker(ticker)
            hist = _retry(lambda: stock.history(period="5d"), retries=2)

            if hist is not None and not hist.empty and len(hist) >= 2:
                latest_close = hist["Close"].iloc[-1]
                prev_close = hist["Close"].iloc[-2]
                change_pct = (latest_close - prev_close) / prev_close * 100
                item["price"] = _round(latest_close)
                item["change_pct"] = _round(change_pct, 2)
            elif hist is not None and not hist.empty:
                item["price"] = _round(hist["Close"].iloc[-1])
                item["change_pct"] = 0
        except Exception:
            pass

        results.append(item)

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

    df = _retry(lambda: ak.stock_zh_index_spot_em(symbol="上证系列指数"), retries=1)

    for code, label in indices:
        item = {"label": label, "ticker": code, "price": None, "change_pct": None}
        if df is not None:
            try:
                row = df[df["代码"] == code]
                if not row.empty:
                    r = row.iloc[0]
                    item["price"] = _round(r.get("最新价"))
                    item["change_pct"] = _round(r.get("涨跌幅"), 2)
            except Exception:
                pass
        results.append(item)

    return results


# ─────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────
def _round(val, digits: int = 2):
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(val), digits)
    except (TypeError, ValueError):
        return None


def _to_billion(val):
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(val) / 1e9, 2)
    except (TypeError, ValueError):
        return None


def _to_yi(val):
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(val) / 1e8, 2)
    except (TypeError, ValueError):
        return None


def _find_year_column(columns, year: str):
    for col in columns:
        try:
            if hasattr(col, "year") and str(col.year) == str(year):
                return col
        except Exception:
            continue
    return columns[0] if len(columns) > 0 else None
