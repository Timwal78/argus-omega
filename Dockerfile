FROM python:3.11-slim

WORKDIR /app

# Prevent glibc memory fragmentation (OOM Fix)
ENV MALLOC_ARENA_MAX=2
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY . .

# Set PYTHONPATH to include the current directory so modules are found
ENV PYTHONPATH=/app

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
