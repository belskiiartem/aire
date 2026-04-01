Завдання на наступну сесію.
Lab-1. Розгортання Basic Agentic Infrastructure:

Початківці: (є обвʼязковим для сертифікації)
1. Встановити agentgateway локально https://agentgateway.dev/docs/standalone/latest/deployment/binary/
2. Обрати llm провайдера https://agentgateway.dev/docs/standalone/latest/llm/providers/
3. Налаштувати config.yaml https://agentgateway.dev/docs/standalone/latest/tutorials/llm-gateway/
4. Запустити gateway та отримати доступ через UI http://localhost:15000/ui/
5. Перевірити доступ до llm (https://aistudio.google.com/api-keys) та ознайомитися з фундаментальними можливостями Backends та Policy

Досвідчені:
1. Виконати завдання початківців але як helm deployment в Kubernetes кластері
2. Налаштувати Secrets та ConfigMap для API ключів та конфігурації
3. Розгорнути kagent https://kagent.dev/docs/kagent/getting-started/quickstart
4. Налаштувати маршрут моделі через agentgateway
5. Перевірити роботу будь-якого вбудованого агента

Макс:
1. Виконати завдання досвідчених але з kagent gateway API https://agentgateway.dev/docs/kubernetes/main/

Research-1: Дати оцінку ADR проектів S&T SRE Agent та MultiAgent (опціонально для сертифікації)
https://github.com/denver2048/insomnia
https://github.com/neo4j/neo4j
1. Ваші питання до проектів, запропонуйте покращення та рішення (формат: md в репо)

Development: PR Instrumentation (опціонально для сертифікації) https://docs.github.com/en/github-models/about-github-models
1. Реалізуйте інструментування репозиторію: CODEBASE.md, REVIEW.md, EVALS.md
2. Реалізуйте github workflow AI Review https://github.com/marketplace?page=2&category=code-review&type=actions
3. Реалізуйте github workflow AI Review Evals


Результати роботи зберегти у власному GitHub репозиторії.
