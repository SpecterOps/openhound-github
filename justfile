set dotenv-load := true

collect +args='github /tmp/output/raw/':
    @echo "Collecting data"
    uv run src/main.py collect {{args}}

preprocess +args='github /tmp/output/raw/github':
    @echo "Preprocessing data"
    uv run openhound preprocess {{args}}

convert +args='github /tmp/output/raw/github /tmp/output/graph/github':
    @echo "Converting data"
    uv run openhound convert {{args}}

sync:
    @echo "Syncing dependencies"
    uv sync --group dev
