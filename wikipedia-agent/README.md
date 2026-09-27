# wikipedia-agent

Агент на LangGraph, який використовує навичку [wikipedia-interest](skills/wikipedia-interest/). У кластері він зареєстрований у **kagent** як `Agent` типу BYO (`wikipedia-analyst`), розгортається через Flux і звертається до LLM через agentgateway.

```
kagent UI ──► kagent controller ──A2A──► wikipedia-analyst (LangGraph, app/kagent_main.py)
                     ▲                        │  run_skill_command
                     └─ історія діалогів ─────┤──► skills/wikipedia-interest ──► Wikimedia API
                        (KAgentCheckpointer)  └──► agentgateway /llm/wikipedia-agent ──► OpenAI

браузер ──► agentgateway /wikipedia-analyst/artifacts/... ──► PDF / PNG (PVC)
```

Один образ підтримує два режими запуску:

| Режим | Команда | Для чого |
|---|---|---|
| kagent BYO | `uvicorn app.kagent_main:app` | A2A-сервер для kagent; історія діалогів зберігається в контролері kagent і переживає перезапуск |
| Автономний | `uvicorn app.main:app` (за замовчуванням) | Власний API (`/chat`) і веб-чат, пам'ять у поді. Для локальної розробки й evals |

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

1. **Образ**: [.github/workflows/wikipedia-agent.yaml](../.github/workflows/wikipedia-agent.yaml) запускає тести й публікує `ghcr.io/belskiiartem/aire/wikipedia-agent` (`sha-*`, `latest` з main, семвер із тегу `wikipedia-agent-vX.Y.Z`).
2. **Маніфести**: [releases/wikipedia-agent.yaml](../releases/wikipedia-agent.yaml) містить:
   - `AgentgatewayBackend` (OpenAI) і LLM-маршрут з обмеженням 60 запитів/хв і 300 тис. токенів/год;
   - PVC для звітів і кешу;
   - kagent `Agent` типу BYO;
   - маршрут `/wikipedia-analyst` для посилань на PDF.

   Flux розгортає все це з тегу `vX.Y.Z` артефакту `releases`.
3. **Секрети** створюються через `terraform apply` з файлів у `secrets/`, які не потрапляють у git:
   - `openAiSecret-wikipedia-agent` — ключ OpenAI для agentgateway;
   - `phoenixKey-wikipedia-agent` — API-ключ Phoenix.

## Трасування (Phoenix)

Трасування вмикається змінною `PHOENIX_COLLECTOR_ENDPOINT`, API-ключ береться з `PHOENIX_API_KEY` ([app/tracing.py](app/tracing.py)). У кластері траси йдуть у проєкт `wikipedia-agent` на `phoenix-svc.phoenix:6006`.

Один запит дає близько 9 спанів: граф LangGraph, кожен виклик моделі (з токенами та промптом) і кожна команда навички (з аргументами й JSON-результатом). Спани одного діалогу групуються в сесію за `session.id`. Щоб прибрати шум, внутрішні спани `a2a-sdk` вимкнено. Прогін `python -m app.evals` теж трасується, тож результати оцінювання моделей можна порівнювати в Phoenix.

Чат: kagent UI → агент `wikipedia-agent/wikipedia-analyst`.

## Залежності

`requirements.in` містить прямі залежності, а `requirements.txt` — повністю закріплений lock (команда генерації вказана в заголовку `requirements.in`). kagent 0.10.x зібраний під `a2a-sdk` 0.3, бо у версії 1.x модуль `a2a.server.apps` видалено, тому `a2a-sdk` зафіксовано на 0.3.26.

## Обмеження поточної версії

- `PUBLIC_BASE_URL` прописано під NodePort minikube (`192.168.49.2:32700`). В іншому оточенні його треба замінити.
- PVC має режим `ReadWriteOnce`, тому працює одна репліка. Для масштабування звіти треба перенести в об'єктне сховище.
- Автентифікації на маршрутах `/wikipedia-analyst` і `/llm/wikipedia-agent` немає: LLM-маршрут захищають лише ліміти частоти й токенів. Для продакшну потрібні JWT/API-key-політика в agentgateway або окремий внутрішній Gateway.
