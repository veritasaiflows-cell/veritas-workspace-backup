# OpenAI Agents SDK Sandbox

Local learning sandbox for the OpenAI Agents SDK.

This is intentionally separate from the production OpenClaw workflow scripts.
Use it to inspect SDK primitives, run small examples, and learn durable-agent
patterns before promoting anything into Veritas-owned workflow code.

## Environment

- Python venv: `.venv`
- Package: `openai-agents`
- Install command used:

```powershell
python -m venv tools\openai-agents-sdk-sandbox\.venv
tools\openai-agents-sdk-sandbox\.venv\Scripts\python.exe -m pip install --upgrade pip
tools\openai-agents-sdk-sandbox\.venv\Scripts\python.exe -m pip install openai-agents
```

## Smoke Test

```powershell
tools\openai-agents-sdk-sandbox\.venv\Scripts\python.exe -c "from agents import Agent, Runner; import openai; print('agents-sdk import ok')"
```

## Boundary

This sandbox has no authority to mutate OpenClaw runtime config, cron,
finance/canon/portfolio state, customer/external surfaces, account/brokerage
state, paper/live execution, or approval state. Any useful pattern must be
copied into Veritas-owned scripts, validators, skills, or PM packets through a
normal implementation lane and validator closeout.
