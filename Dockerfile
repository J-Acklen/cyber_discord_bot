FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user rather than root. UID/GID 1001 matches the
# `ubuntu` user on the Oracle VM so the bind-mounted ./data directory (owned
# by that user on the host) stays writable without needing a container-side
# chown at every start.
RUN groupadd -g 1001 app && useradd -u 1001 -g app -m app \
    && mkdir -p /app/data && chown -R app:app /app
USER app

CMD ["python", "bot.py"]
