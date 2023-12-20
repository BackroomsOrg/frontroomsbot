FROM python:3.11-slim

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /app

COPY pyproject.toml poetry.lock /app/

RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install
RUN adduser --shell /bin/bash bot

USER bot

COPY . /app/

WORKDIR /app/frontroomsbot

CMD ["python", "bot.py"]
