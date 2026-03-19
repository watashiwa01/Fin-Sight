# Contributing

## Setup

- Create a virtualenv and install dependencies:
  - `python -m pip install -r requirements.txt`
- Copy `.env.example` → `.env` and add keys as needed.

## Development

- Start the app:
  - `python api.py`
- API docs:
  - `http://127.0.0.1:8140/docs`
- Health check:
  - `http://127.0.0.1:8140/health`

## Repo hygiene

- Do **not** commit secrets (`.env`) or generated/large artifacts (`output/`, `data/`, `temp_uploads/`, `*.log`).
