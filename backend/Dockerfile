FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY app ./app
RUN pip install --no-cache-dir -c requirements.lock . && useradd --uid 10001 --create-home relay
USER relay
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--ws-max-size", "8192", "--no-access-log"]
