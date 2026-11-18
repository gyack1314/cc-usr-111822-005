FROM python:3.11-slim
WORKDIR /app
COPY . .
CMD ["python","-m","pilot_economics.cli","data/example.json"]
