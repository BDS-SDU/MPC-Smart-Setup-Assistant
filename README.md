# MPC Agent

MPC Agent is an auto-configuration and orchestration assistant for secure multi-party computation (MPC). It parses natural language or structured requirements, ranks MPC protocol candidates, generates an implementation configuration, and can optionally call MP-SPDZ, SecretFlow SPU, or CrypTen when the corresponding runtime is available.

The project includes an HTTP API, a lightweight web UI, MCP-style local tools/resources/prompts, a Skills execution chain, local knowledge retrieval, and case memory. It is suitable for MPC protocol selection, experiment orchestration, teaching demos, and prototype system integration.

## Features

- Requirement parsing from natural language and structured fields.
- Protocol ranking based on rules, local knowledge, runtime signals, and historical cases.
- Skills workflow for requirement analysis, protocol selection, circuit optimization, configuration generation, deployment monitoring, threat simulation, and decision explanation.
- Optional DeepSeek second opinion through `DEEPSEEK_API_KEY`.
- Runtime orchestration for MP-SPDZ, SecretFlow SPU, and CrypTen.
- MCP-style local interface for tool calls, resource reads, and prompt rendering.
- Built-in web UI served by `server.py`.
- Persistent local case memory for experience-driven routing.

## demo




https://github.com/user-attachments/assets/97eff532-e747-4857-81b8-bada02160bb2







## Project Structure

```text
.
|-- server.py                  # HTTP API and static web server entrypoint
|-- pyproject.toml             # Python package metadata
|-- mpc_agent/                 # Core Python package
|   |-- parser.py              # Requirement parser
|   |-- policy.py              # Protocol scoring and ranking
|   |-- orchestrator.py        # End-to-end workflow coordinator
|   |-- runtime_runner.py      # Runtime backend dispatcher
|   |-- spdz_runner.py         # MP-SPDZ compile/run wrapper
|   |-- spu_runner.py          # SecretFlow SPU runtime wrapper
|   |-- crypten_runner.py      # CrypTen runtime wrapper
|   |-- mcp/                   # MCP-style tools, resources, prompts, server
|   |-- skills/                # Skills registry, router, executor, packages
|   `-- integrations/          # Whitelisted third-party tool integrations
|-- static/                    # Web UI assets
|-- docs/                      # Additional documentation
|-- tests/                     # Unit tests
|-- pragmaticmpc.txt           # Local knowledge retrieval source
|-- pragmaticmpc.pdf           # Reference PDF
`-- examples/                  # Local runtime configuration examples
```

## Requirements

- Python 3.10 or later
- Windows, macOS, or Linux for the controller service
- Optional runtimes:
  - MP-SPDZ, preferably on Linux or Windows WSL2
  - SecretFlow SPU in a separate Python environment
  - CrypTen in a separate Python environment

The core controller does not require third-party MPC frameworks. Without runtime backends, it can still parse requirements, recommend protocols, and generate configurations.

## Quick Start

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python server.py
```

macOS / Linux:

```bash
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
python server.py
```

Default URL:

```text
http://127.0.0.1:8080
```

Open the URL in a browser to use the web UI, or call the API directly.

## API Examples

Health check:

```bash
curl http://127.0.0.1:8080/api/health
```

Generate an MPC configuration:

```bash
curl -X POST http://127.0.0.1:8080/api/configure \
  -H "Content-Type: application/json" \
  -d '{"requirement":"3-party malicious secure private aggregation with low online bandwidth","parties":3,"execute":false}'
```

Windows PowerShell:

```powershell
curl.exe -X POST http://127.0.0.1:8080/api/configure `
  -H "Content-Type: application/json" `
  -d "{\"requirement\":\"3-party malicious secure private aggregation with low online bandwidth\",\"parties\":3,\"execute\":false}"
```

Common endpoints:

- `POST /api/configure`: parse, rank, generate configuration, and optionally execute.
- `GET /api/skills/list`: list available Skills.
- `POST /api/skills/recommend`: recommend Skills for a request.
- `POST /api/knowledge/retrieve`: retrieve local MPC knowledge snippets.
- `GET /api/cases/list`: list local case memory.
- `POST /api/runtime/signals/collect`: collect network and hardware signals.
- `GET /api/mcp/capabilities`: inspect MCP-style capabilities.
- `POST /api/mcp`: call local MCP tools, resources, or prompts.

## Environment Variables

```text
DEEPSEEK_API_KEY       Optional, enables DeepSeek second opinion
DEEPSEEK_BASE_URL      Defaults to https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL         Defaults to deepseek-chat
DEEPSEEK_TIMEOUT       Defaults to 30 seconds
MPSPDZ_HOME            MP-SPDZ root directory
SPU_PYTHON             SecretFlow SPU Python executable
SPU_RUNTIME_MODE       SecretFlow SPU runtime mode, for example local or wsl
SPU_WSL_DISTRO         WSL distro name, for example Ubuntu
CRYPTEN_PYTHON         CrypTen Python executable
MPC_AGENT_CASE_DB      Case database path, defaults to ./.mpc_agent_cases.jsonl
MPC_AGENT_HOST         Server host, defaults to 127.0.0.1
MPC_AGENT_PORT         Server port, defaults to 8080
EXTERNAL_SYSTEMS_JSON  JSON-encoded third-party tool whitelist
```

See `.env.example` for a local environment template. Do not commit real API keys or machine-specific absolute paths.

## Optional Runtime Backends

The recommended layout keeps the controller and heavyweight MPC runtimes in separate environments:

```text
venvs/
  agent_env/
  spu_env/
  crypten_env/
MP-SPDZ/
```

Controller environment:

```bash
python -m venv venvs/agent_env
source venvs/agent_env/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

SecretFlow SPU environment example:

```bash
python -m venv venvs/spu_env
source venvs/spu_env/bin/activate
python -m pip install -U pip
python -m pip install spu ray
```

CrypTen environment example:

```bash
python -m venv venvs/crypten_env
source venvs/crypten_env/bin/activate
python -m pip install -U pip
python -m pip install crypten torch
```

Copy example runtime defaults when needed:

```bash
cp examples/spu_runtime.example.json .spu_runtime.json
cp examples/crypten_runtime.example.json .crypten_runtime.json
```

Windows PowerShell:

```powershell
Copy-Item examples\spu_runtime.example.json .spu_runtime.json
Copy-Item examples\crypten_runtime.example.json .crypten_runtime.json
```

After filling in local paths, set `execute=true` in a configure request to call the selected runtime backend.

## Third-Party Tool Integrations

Use `EXTERNAL_SYSTEMS_JSON` to configure whitelisted external systems:

```json
[
  {
    "name": "toolhub",
    "base_url": "https://api.example.com",
    "description": "third-party tool platform",
    "allow_write": false,
    "api_key_env": "TOOLHUB_API_KEY",
    "auth_scheme": "Bearer",
    "timeout_seconds": 20,
    "allowed_prefixes": ["v1/tools/", "v1/status/"]
  }
]
```

The integration layer only allows configured systems and path prefixes. This is useful for connecting external network probes, hardware profilers, and monitoring tools to the configuration flow.

## Testing

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
