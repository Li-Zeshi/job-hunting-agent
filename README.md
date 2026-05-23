# 🤖 Job Hunting Agent

> 自动化求职助手 — 分析岗位、匹配简历、检索 BQ 故事、生成动机信，一站式搞定。
> Automated job-seeking agent: JD analysis, resume matching, BQ story retrieval, cover letter generation, and human-in-the-loop review.

## 功能 Features

| 功能 | 说明 |
|------|------|
| 🎯 **岗位扫描** | 通过 DuckDuckGo 搜索岗位，支持关键词和地点筛选 |
| 🔍 **JD 分析** | LLM 自动提取岗位要求、职责、签证信息等结构化数据 |
| 🛂 **KM Visa 筛选** | 检测荷兰 KM visa / 担保资格，过滤不提供签证赞助的岗位 |
| 📊 **简历匹配评分** | 基于 LLM + 关键词对简历与 JD 进行匹配度评分 |
| 📖 **BQ 故事 RAG** | 从你的 BQ 故事库中检索最相关的经历，融入动机信 |
| 📝 **简历定向修改** | 根据 JD 自动调整简历，突出相关技能和经验 |
| 💌 **动机信生成** | 结合 JD、调整后的简历和 BQ 故事，生成有 passion 的动机信 |
| 👤 **人工审核** | 每条申请前展示完整材料，你可批准/编辑/跳过 |
| 📋 **每日报告** | 记录所有申请状态，生成日报汇总 |

## 技术栈 Tech Stack

- **LangGraph** — 多智能体状态机编排（9 节点 StateGraph）
- **LangChain** — Prompt 模板 + LLM 抽象
- **Ollama / OpenAI** — 双模式 LLM 支持
- **DuckDuckGo** — 岗位搜索
- **Rich** — 终端交互 UI
- **Typer** — CLI 命令行框架

## 工作流 Architecture

```
scanner → analyzer → matcher → retriever → tailor → writer → ⛔reviewer → reporter → END
                         ↕                                   ↕
                    visa 过滤 + 评分                    approved/rejected/modified
```

- 使用 LangGraph `interrupt_before` 在 reviewer 节点前暂停
- 展示调整后的简历、动机信、匹配的 BQ 故事
- 支持 `a`=批准、`e`=编辑重写、`s`=跳过、`v`=查看完整材料、`q`=退出

## 快速开始 Quick Start

### 1. 安装

```bash
git clone https://github.com/Li-Zeshi/job-hunting-agent.git
cd job-hunting-agent
uv sync
```

### 2. 准备数据

将简历放到 `job_agent/data/resume.md`：

```markdown
# 你的名字

## 技能
- Python, TypeScript, FastAPI, Docker

## 工作经历
### 公司名 | 2022 - 至今
- 负责 ...
```

将 BQ 故事放到 `job_agent/data/bq_stories/`（每个故事一个 .md 文件），然后建索引：

```bash
python main.py ingest
```

### 3. 配置 LLM

编辑 `job_agent/config.py`：

```python
LLM_PROVIDER = "ollama"  # 或 "openai"
OLLAMA_MODEL = "llama3.2:3b"  # 推荐 3B 以上模型
```

> 💡 `gemma3:270m` 太小，建议安装更好模型：`ollama pull llama3.2:3b`

### 4. 运行

```bash
# 完整工作流（搜索 → 分析 → 匹配 → 改简历 → 写动机信 → 审核）
python main.py run "Python Engineer"

# 手动添加一条岗位（推荐方式）
python main.py process --title "Senior Python Engineer" --company "TechFin" -d "粘贴JD内容"

# 仅搜索岗位
python main.py scan "Python Engineer"

# 查看日报
python main.py report
```

## 项目结构

```
job-hunting-agent/
├── main.py                    # CLI 入口
├── pyproject.toml             # 依赖管理
├── job_agent/
│   ├── config.py              # 配置（visa 关键词、模型选择）
│   ├── state.py               # LangGraph 状态定义
│   ├── workflow.py            # StateGraph 编排
│   ├── nodes/
│   │   ├── scanner.py         # 岗位搜索
│   │   ├── analyzer.py        # JD 结构化分析
│   │   ├── matcher.py         # 匹配评分 + visa 过滤
│   │   ├── retriever.py       # BQ 故事检索
│   │   ├── tailor.py          # 简历修改
│   │   ├── writer.py          # 动机信生成
│   │   ├── reviewer.py        # 人工审核
│   │   └── reporter.py        # 申请记录
│   ├── utils/
│   │   ├── llm.py             # LLM 工厂
│   │   └── visadb.py          # BQ 向量索引（OpenAI embedding / 关键词 fallback）
│   └── data/
│       ├── resume.md          # ← 你的简历
│       ├── bq_stories/        # ← 你的 BQ 故事
│       └── applications.json  # 申请历史
```

## 后续计划 Roadmap

- [ ] Playwright LinkedIn 岗位抓取
- [ ] 半自动投递（浏览器自动填表）
- [ ] 定时调度（每日自动搜索）
- [ ] Web UI
