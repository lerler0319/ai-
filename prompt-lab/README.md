# 🧪 Prompt Lab — AI 提示词 A/B 测试平台

**用数据驱动的方式找到最优 AI 提示词，告别凭感觉反复试。**

AI 大模型（ChatGPT、Claude 等）的输出质量严重依赖提示词的写法。同样的问题，换个说法，回答质量可能天差地别。Prompt Lab 把这个优化过程**工程化、可量化**——创建多个版本的提示词，一键跑分对比，用数据看哪个版本更好。

## ✨ 功能

- **📝 提示词管理** — 创建和管理多个 prompt 版本，支持 `{变量}` 占位符模板
- **🧪 测试用例** — 构建评测基准集，定义输入变量和期望输出
- **🚀 一键评测** — 自动调用 AI 模型，对所有 prompt×用例组合批量评分
- **📈 结果分析** — 排名卡片、可视化图表、详细输出对比

### 评分体系

| 维度 | 权重 | 说明 |
|------|------|------|
| 准确率 | 50% | 关键词命中率 + 输出长度合理性 |
| 格式合规 | 20% | 是否包含列表/标题等结构化元素 |
| 效率 | 30% | 响应延迟 + Token 消耗 |

## 🎮 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/lerler0319/ai提示词评分.git
cd ai提示词评分

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key（可选，Mock 模式无需 Key）
cp .env.example .env
# 编辑 .env 填入你的 Key

# 4. 启动
streamlit run app.py
```

启动后打开 http://localhost:8501 ，即可开始使用。

## 🔌 支持的模型

| 供应商 | 可用模型 | 需要 API Key |
|--------|----------|-------------|
| 🖥 Mock | mock-v1 | 无（演示用） |
| 🔮 Anthropic | Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 | ANTHROPIC_API_KEY |
| 🤖 OpenAI | GPT-4o / GPT-4o-mini | OPENAI_API_KEY |
| 🐋 DeepSeek | deepseek-chat / deepseek-reasoner | OPENAI_API_KEY |

## 📁 项目结构

```
prompt-lab/
├── app.py              # Streamlit 主应用（UI + 路由）
├── evaluator.py        # 评测引擎（评分计算 + 报告生成）
├── providers.py        # LLM 提供商适配层（统一接口）
├── database.py         # SQLite 数据持久化
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
└── .gitignore
```

## 🛠 技术栈

- **前端**: Streamlit（Python Web 框架）
- **后端**: Python 3.12+
- **数据库**: SQLite
- **可视化**: Plotly + Pandas
- **AI SDK**: Anthropic SDK / OpenAI SDK

## 📄 License

MIT
