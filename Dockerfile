# LLMSlim memory server: memory and context over HTTP, no model calls. One SQLite file in /data by default, or
# Postgres or MongoDB: the image has both drivers.
#   docker build -t llmslim .
#   docker run -p 8080:8080 -e LLMSLIM_API_KEYS="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
#     -v llmslim-data:/data llmslim
#   docker run -p 8080:8080 -e LLMSLIM_API_KEYS="<key>" \
#     -e LLMSLIM_MEMORY_DB="mongodb+srv://llmslim:<password>@cluster0.example.mongodb.net/llmslim" llmslim
# The server refuses to start on 0.0.0.0 without an API key.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    LLMSLIM_MEMORY_DB=/data/memory.db \
    LLMSLIM_HOST=0.0.0.0 \
    LLMSLIM_PORT=8080

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY llmslim ./llmslim
RUN pip install ".[server,postgres,mongodb]" \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')" \
    && useradd --create-home --uid 10001 llmslim \
    && mkdir -p /data \
    && chown llmslim /data

USER llmslim
WORKDIR /home/llmslim
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4)"
CMD ["llmslim", "serve"]
