# ⚡ LocalManus

**An open-source, locally-running agentic AI** — inspired by Manus, built on the architecture described in [*How AI Agents Actually Do Things*](https://www.linkedin.com/pulse/).

Run complex multi-step tasks (code, files, web search) entirely on your own machine with [Ollama](https://ollama.com), or plug in OpenAI / Anthropic with one config change.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Ollama](https://img.shields.io/badge/ollama-first-orange)

---

## What it does

LocalManus gives an LLM a set of tools and runs a **ReAct loop** (Reason → Act → Observe → repeat) until the task is complete. Every tool call and result streams live to the browser.

```
User prompt
    │
    ▼
┌─────────────────────────────────────┐
│  Agent (ReAct loop)                 │
│  ┌──────────┐   tool_call           │
│  │   LLM    │──────────────────┐    │
│  │(Ollama / │                  ▼    │
│  │ OpenAI / │   ┌────────────────┐  │
│  │ Claude)  │◄──│ Tool Executor  │  │
│  └──────────┘   │ run_python     │  │
│   tool_result   │ run_shell      │  │
│                 │ read/write file│  │
│                 │ web_search     │  │
│                 └────────────────┘  │
│              (isolated workspace)   │
└─────────────────────────────────────┘
    │
    ▼
Streaming UI (SSE)
```

---

## Features

| | |
|---|---|
| 🦙 **Ollama-first** | Runs 100% locally — no accounts, no API keys needed |
| 🔌 **Multi-provider** | Switch to OpenAI or Anthropic with one env var |
| 🐍 **Python executor** | Runs code in an isolated workspace; pandas, numpy, matplotlib included |
| 🖥️ **Shell executor** | Bash commands in the same workspace |
| 📁 **File tools** | Read, write, list — sandboxed to the session directory |
| 🌐 **Web search** | DuckDuckGo — no API key required |
| 📡 **Live streaming** | Every tool call and result appears in real time via SSE |
| 🗂️ **Session isolation** | Each chat gets its own workspace; files downloadable from the UI |
| 🔧 **Small-model compatible** | Fallback parser handles models that output JSON/code instead of native tool calls |

---

## Quickstart

### 1. Clone & install

```bash
git clone https://github.com/your-username/local-manus.git
cd local-manus
make install
```

Or manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Pull a model

```bash
# Install Ollama from https://ollama.com, then:
ollama pull qwen3:8b       # recommended — best tool use + code quality
# or
ollama pull llama3.2       # smaller, faster, good for simple tasks
```

### 3. Configure (optional)

```bash
cp .env.example .env
# Edit .env to change provider, model, port, etc.
```

### 4. Run

```bash
make run
# or: .venv/bin/python3 main.py
```

Open **http://localhost:7860**

---

## Model compatibility

| Model | Pull command | Tool calling | Code quality | Speed (CPU) |
|---|---|---|---|---|
| **qwen3:8b** ⭐ | `ollama pull qwen3:8b` | ✅ native | ⭐⭐⭐⭐⭐ | slow |
| llama3.2 | `ollama pull llama3.2` | ✅ native | ⭐⭐⭐ | fast |
| llama3.1:8b | `ollama pull llama3.1` | ✅ native | ⭐⭐⭐⭐ | slow |
| qwen2.5:7b | `ollama pull qwen2.5` | ✅ native | ⭐⭐⭐⭐⭐ | slow |
| mistral | `ollama pull mistral` | ⚠️ fallback | ⭐⭐ | slow |
| GPT-4o | OpenAI API | ✅ native | ⭐⭐⭐⭐⭐ | fast |
| Claude Sonnet | Anthropic API | ✅ native | ⭐⭐⭐⭐⭐ | fast |

> **Tip:** On Apple Silicon or a machine with a GPU, all models run 10–20× faster. CPU inference with 7B+ models is usable but slow.

---

## Configuration

All settings via `.env` (copy from `.env.example`):

```env
# Provider: ollama | openai | anthropic
LLM_PROVIDER=ollama

OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3:8b

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

MAX_ITERATIONS=30
WORKSPACE_DIR=./workspace
PORT=7860
```

You can also override the **provider and model per-chat** from the UI sidebar.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Run a task — returns SSE stream |
| `GET` | `/api/sessions` | List active sessions |
| `GET` | `/api/sessions/{id}` | List files in a session workspace |
| `DELETE` | `/api/sessions/{id}` | Destroy a session |
| `GET` | `/workspace/{id}/{path}` | Download a file from the workspace |
| `GET` | `/api/health` | Health check |

### SSE event types

```json
{"type": "session",     "session_id": "..."}
{"type": "thinking",    "content": "..."}
{"type": "tool_call",   "tool_name": "run_python", "tool_args": {...}, "tool_call_id": "..."}
{"type": "tool_result", "content": "...", "tool_call_id": "...", "is_error": false}
{"type": "message",     "content": "Final answer..."}
{"type": "done"}
{"type": "error",       "content": "...", "is_error": true}
```

---

## Adding a custom tool

```python
# tools/my_tool.py
from tools.base import Tool, ToolResult
from pathlib import Path

class MyTool(Tool):
    name = "my_tool"
    description = "Does something useful."
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input value"}
        },
        "required": ["input"]
    }

    async def execute(self, input: str) -> ToolResult:
        result = do_something(input)
        return ToolResult(content=result)
```

Register it in `tools/__init__.py` → `get_all_tools()`. That's it.

---

## Project structure

```
local-manus/
├── main.py                  # Entry point
├── config.py                # Env-var configuration
├── requirements.txt
├── Makefile
├── .env.example
│
├── agent/
│   └── core.py              # ReAct loop (reason → act → observe)
│
├── llm/
│   ├── base.py              # ToolCall, LLMResponse, BaseLLMProvider
│   ├── openai_compat.py     # Ollama + OpenAI (shared client)
│   ├── anthropic_provider.py
│   └── factory.py           # create_provider()
│
├── tools/
│   ├── base.py              # Tool, ToolResult base classes
│   ├── code_executor.py     # Python execution (subprocess, 60s timeout)
│   ├── shell.py             # Bash execution (30s timeout)
│   ├── file_system.py       # read_file / write_file / list_files
│   └── web_search.py        # DuckDuckGo (no key needed)
│
├── sandbox/
│   └── workspace.py         # Per-session isolated directories
│
├── api/
│   └── server.py            # FastAPI + SSE streaming
│
└── ui/
    └── index.html           # Browser UI (single file, no build step)
```

---

## How it works

Based on the **ReAct pattern** (Yao et al., 2022). At each step the agent:

1. Assembles context: system prompt + conversation history + tool definitions
2. Calls the LLM → gets either a **tool call** or a **final answer**
3. If tool call: executes the tool in the sandboxed workspace, appends the result, loops
4. If final answer: streams it to the user and stops

Small models that don't use native function calling are handled by a three-tier fallback:
- **Tier 1** — parse JSON tool call from response text (with newline sanitisation)
- **Tier 2** — extract `\`\`\`python` code blocks and run as `run_python`
- **Tier 3** — treat as final text answer

---

## Roadmap

- [ ] Browser automation (Playwright)
- [ ] Multi-agent orchestration (Planner + Executor + Critic)
- [ ] Persistent session memory (RAG over past sessions)
- [ ] MCP server support
- [ ] Docker image
- [ ] Configurable tool enable/disable per request

---

## Contributing

PRs welcome. Please open an issue first for anything beyond small fixes.

---

## License

MIT
