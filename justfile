set dotenv-load := true

collect +args:
    @echo "Collecting data"
    uv run src/main.py collect github {{args}}

preprocess +args:
    @echo "Collecting data"
    uv run src/main.py preprocess github {{args}}

convert +args:
    @echo "Converting data"
    uv run src/main.py convert github {{args}}

sync:
    @echo "Syncing dependencies"
    uv sync --group dev
