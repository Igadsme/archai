FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/archai
COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN pip install --no-cache-dir '.[ml,platform,benchmark]'
USER 10001
EXPOSE 8000
CMD ["uvicorn", "archai_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
