# fin-agent 📊

> AI-powered stock financial analysis · US & China A-shares · Fully open source
>
> AI 驱动的股票财务分析工具 · 支持美股和 A 股 · 完全开源

Bring your own LLM API key. No accounts, no servers, no tracking.

---

## ✨ Features

- 🌐 **Bilingual** — Switch between 中文 and English instantly
- 🇺🇸 **US Stocks** via Yahoo Finance (free, no API key required)
- 🇨🇳 **A-Shares** via AkShare (free, no API key required)
- 🤖 **Multiple LLM Providers** — Claude / OpenAI / DeepSeek
- 💬 **Natural Language Interface** — Just ask about any company
- 📊 **3-Dimensional Analysis** — Financials, Valuation, Risk

---

## 🚀 Quick Start

### 1. Get an LLM API Key

Choose ONE of:

| Provider | Where to get | Notes |
|----------|--------------|-------|
| **Claude** | [console.anthropic.com](https://console.anthropic.com) | Claude Code users: same key works |
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | GPT-4o |
| **DeepSeek** | [platform.deepseek.com](https://platform.deepseek.com) | Cheapest option |

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
streamlit run app.py
```

The browser will open. Enter your API key in the sidebar and start asking questions.

---

## 💡 Example Queries

- `Analyze Apple's 2024 financials`
- `Is Tesla overvalued?`
- `What are the risks for NVIDIA?`
- `分析茅台2023年的财务状况`
- `宁德时代估值合理吗`
- `比较比亚迪和理想汽车的风险`

---

## 📁 Project Structure

```
fin-agent/
├── app.py            # Main Streamlit app + chat UI
├── data.py           # Yahoo Finance + AkShare data fetching
├── agent.py          # LLM orchestration (Claude/OpenAI/DeepSeek)
├── i18n.py           # Bilingual translations
├── requirements.txt
└── README.md
```

---

## ⚠️ Disclaimer

This tool is for **educational purposes only**. All output is AI-generated commentary on public financial data and **does not constitute investment advice**. Stock investments carry risk.

---

## 🛣️ Roadmap

- [ ] Multi-company side-by-side comparison
- [ ] Historical trend charts
- [ ] DCF valuation calculator
- [ ] Export reports as PDF
- [ ] Industry-level dashboards

PRs welcome! 欢迎提 PR！

---

## 📄 License

MIT
