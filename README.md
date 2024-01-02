# Frontrooms bot

## Install

`poetry install`

In `.env` add `DISCORD_TOKEN`, which is your bot discord token, and `GUILD_ID`, which is your server id, and `HF_TOKEN`, which is huggingface token (https://huggingface.co/settings/tokens), and `GEMINI_TOKEN`, which is Google Gemini LLM API token (https://makersuite.google.com/app/apikey).

Before push run `poetry run ruff .` and `poetry run black .`.
