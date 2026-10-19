# Status: written but not built in the authoring environment. Review before use.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 caterya
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[api,crypto,graphql]"
USER caterya
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/v1/health', timeout=2)"
CMD ["caterya", "serve", "--host", "0.0.0.0", "--port", "8000"]
