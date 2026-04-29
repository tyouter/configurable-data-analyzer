FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server/ ./mcp_server/

RUN mkdir -p /app/projects /app/data

ENV PROJECTS_DIR=/app/projects
ENV TRANSPORT=sse
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('localhost',8000)); s.close()" || exit 1

CMD ["python", "mcp_server/server.py", "--transport", "sse"]
