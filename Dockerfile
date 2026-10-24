FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Kør ikke som root
RUN useradd --create-home app
USER app

EXPOSE 8000
CMD ["parts-mcp"]
