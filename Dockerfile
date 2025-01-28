FROM python:3.11-slim

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /app

RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN adduser --shell /bin/bash bot

COPY README.md pyproject.toml poetry.lock /app/

RUN poetry install

USER bot

COPY . /app/

WORKDIR /app/frontroomsbot

CMD ["python", "bot.py"]
