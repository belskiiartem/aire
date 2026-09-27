# wikipedia-agent

Агент на LangGraph, який використовує навичку [wikipedia-interest](skills/wikipedia-interest/) і розгортається в кластер через Flux. Звертається до LLM через agentgateway.

```
browser ──► agentgateway /wikipedia-agent ──► wikipedia-agent (FastAPI + LangGraph)
                                                  │  run_skill_command
                                                  ├──► skills/wikipedia-interest/scripts/wiki-interest ──► Wikimedia API
                                                  └──► agentgateway /llm/wikipedia-agent ──► OpenAI (ключ і ліміти — у gateway)
```

## Як це влаштовано

- **Граф** ([app/graph.py](app/graph.py)): вузол `agent` (модель з інструментами) ⇄ `ToolNode`; пам'ять діалогу через checkpointer за `thread_id`.
- **Середовище навичок** ([app/skills.py](app/skills.py)): знаходить `skills/*/SKILL.md`, перевіряє frontmatter за специфікацією та запускає скрипти навички без shell і лише з її `scripts/`. Якщо навичка одна, її SKILL.md вбудовується в системний промпт (на один крок моделі менше).
- **API** ([app/main.py](app/main.py)): `POST /chat {message, thread_id}` → відповідь, посилання на артефакти, виклики інструментів, токени; `GET /artifacts/...` віддає PDF/PNG; `GET /healthz`; `GET /` — простий веб-чат.
- **Трасування**: якщо задано `PHOENIX_COLLECTOR_ENDPOINT`, траси LangChain надсилаються в Phoenix.

## Локальний запуск

```bash
pip install -r requirements.txt
OPENAI_API_KEY=... uvicorn app.main:app --port 8080     # або LLM_BASE_URL=<будь-який OpenAI-сумісний endpoint>
python -m app.evals --model gpt-4.1-nano               # сценарії з skills/wikipedia-interest/evals
```

Змінні: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (за замовчуванням `gpt-4.1-mini`), `WORK_DIR` (кеш і звіти, `/data` у контейнері), `MAX_STEPS`.

## Розгортання

1. **Образ**: [.github/workflows/wikipedia-agent.yaml](../.github/workflows/wikipedia-agent.yaml) запускає тести й публікує `ghcr.io/belskiiartem/aire/wikipedia-agent`. На main публікуються теги `sha-<commit>` і `latest`, на тег `wikipedia-agent-v0.1.0` — тег `0.1.0`.
2. **Маніфести**: [releases/wikipedia-agent.yaml](../releases/wikipedia-agent.yaml) містить Namespace, `AgentgatewayBackend` (OpenAI), LLM-маршрут з обмеженням 60 запитів/хв і 300 тис. токенів/год, Deployment, Service і маршрут UI. Файл підключено в `releases/kustomization.yaml`, тож він потрапить у кластер з наступним релізом `v*` артефакту `releases`.
3. **Секрет**: `terraform apply` після першого розгортання Flux (ресурс `openAiSecret-wikipedia-agent` у `manifests.tf`) копіює ключ у namespace `wikipedia-agent`.

UI: `http://<gateway>/wikipedia-agent/`.

## Обмеження поточної версії

- `replicas: 1`: пам'ять діалогів і кеш зберігаються в поді (`emptyDir`) і зникають під час перезапуску. Для масштабування потрібні Postgres-checkpointer і PVC або об'єктне сховище для звітів.
- Автентифікації на UI/API немає, а LLM-маршрут також доступний на зовнішньому gateway (його захищають лише ліміти частоти й токенів). Для продакшну потрібні JWT/API-key-політика в agentgateway або окремий внутрішній Gateway.
