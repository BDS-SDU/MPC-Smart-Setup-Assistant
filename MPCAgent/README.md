# MPC Protocol Configuration Agent

这是一个 LangChain + DeepSeek API + FastAPI 的多方安全计算（MPC）配置智能体。它从用户自然语言和多轮上下文中抽取协议配置，输出结构化 JSON，便于后续接 MPC 编译器、协议选择器或仿真服务。

## 功能

- 抽取参与方规模、电路形式、底层数学结构、Secret Sharing、预处理阶段、敌手模型、腐化方式、网络模型、敌手门限和安全目标。
- 支持多轮对话，按 `session_id` 管理上下文和当前配置快照。
- 使用 `with_structured_output` 和 Pydantic schema 做“隐藏表单填充”，每轮返回 `current_mpc_config` 和 `agent_reply`。
- 使用 `RunnableWithMessageHistory` 和基于 `session_id` 的消息历史字典，隔离多个会话/实验进程。
- 内置规范化映射，将“恶意安全 / 不按协议执行 / active”等表达归一为 `Malicious` 等下游可消费参数。
- 使用 LangChain 调用 DeepSeek；优先使用 `langchain-deepseek`，缺失时可通过 OpenAI-compatible API 方式接入。
- 通过 FastAPI 暴露 `/chat`、`/health`、配置 schema、session 查询和 reset/delete 接口。
- 内置前端工作台，可在浏览器中输入需求、查看协议快照、缺失项、冲突、澄清问题并导出 JSON。
- 前端支持自然语言和结构化选项同时输入；当两者冲突时，系统优先采用结构化选项。
- 根据生成配置自动选择后端协议执行计划，当前内置 SPU、CrypTen、MP-SPDZ 三个后端适配器。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

编辑 `.env`，填入：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_MODEL=deepseek-v4-flash
```

启动服务：

```powershell
uvicorn mpc_agent.api:app --reload --host 0.0.0.0 --port 8000
```

如果 Windows 默认 `python` 环境不可用，可以显式使用 `py -3.10`：

```powershell
py -3.10 -m pip install -e ".[dev]"
py -3.10 -m uvicorn mpc_agent.api:app --reload --host 0.0.0.0 --port 8000
```

打开浏览器时请访问：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
```

`/` 是可视化工作台；`/docs` 是 FastAPI 的接口调试页。`/chat` 是 POST 接口，直接在浏览器地址栏打开 `/chat` 只会看到调用说明。

请求示例：

```powershell
$body = @{
  message = "我要三方计算，恶意安全，最多腐化一方，用算术电路和 Shamir 分享，需要 Beaver triples 预处理，网络同步且有认证信道。"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat -ContentType "application/json" -Body $body
```

只使用结构化选项也可以：

```json
{
  "structured_options": {
    "participant_scale": "3-party",
    "circuit_form": "Arithmetic",
    "math_structure": "PrimeField",
    "secret_sharing": "Shamir",
    "preprocessing": "Required",
    "adversary_behavior": "Malicious",
    "corruption_strategy": "Static",
    "network_model": "Synchronous",
    "channel_model": "Authenticated channels",
    "corruption_threshold": "t=1",
    "security_goal": "PrivacyCorrectness"
  }
}
```

继续同一轮对话时传回 `session_id`：

```json
{
  "session_id": "上一轮返回的 session_id",
  "message": "底层域改成 64 位环，安全目标要保证隐私和正确性。"
}
```

常用查询接口：

```text
GET /schema
GET /backends
POST /backends/plan
GET /sessions
GET /sessions/{session_id}
GET /sessions/{session_id}/config
POST /sessions/{session_id}/backend-plan
POST /sessions/{session_id}/reset
DELETE /sessions/{session_id}
```

后端仓库位于 `backend_repository/`：

```text
backend_repository/spu
backend_repository/crypten
backend_repository/mp_spdz
backend_repository/aby
backend_repository/emp_sh2pc
backend_repository/motion
backend_repository/scale_mamba
```

当前实现会先返回可解释的执行计划和候选后端评分。真实执行需要先安装对应后端运行时，例如 SecretFlow/SPU、CrypTen/PyTorch 或已编译的 MP-SPDZ，并把 runner stub 替换为实际执行桥接代码。

一键运行 smoke test：

```powershell
py -3.10 scripts\smoke_test.py
```

它会依次检查 `/health`、`/schema`、`POST /chat` 和 `/sessions/{session_id}/config`。

## CLI

```powershell
mpc-agent "五方半诚实 MPC，布尔电路，静态腐化，t 小于 n/2"
```

## 主要文件

- `mpc_agent/schemas.py`：MPC 协议配置结构。
- `mpc_agent/prompts.py`：系统提示词和用户提示词模板。
- `mpc_agent/memory.py`：按 session 管理短期上下文。
- `mpc_agent/agent.py`：LangChain 抽取链、DeepSeek 调用、配置合并。
- `mpc_agent/api.py`：FastAPI 外部服务。

## 说明

DeepSeek 官方 API 当前是 OpenAI/Anthropic 兼容格式，默认模型使用 `deepseek-v4-flash`。LangChain 官方提供 `langchain-deepseek` 的 `ChatDeepSeek` 集成；本项目按该集成优先实现。
