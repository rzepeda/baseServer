# YouTube MCP Server

This project is an extensible MCP (Model-driven Co-pilot) server designed to provide tools for interacting with YouTube. The initial tool provides the ability to fetch video transcripts.

## Features

- Extensible tool registry for adding new MCP tools.
- Health check endpoint for monitoring.
- Structured JSON logging.
- Configuration driven by environment variables.

## Setup and Installation

### Prerequisites

- Python 3.12+
- pip

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```
    Alternatively, if you are using a `pyproject.toml` based workflow:
    ```bash
    pip install -e .[dev]
    ```

4.  **Configure environment variables:**
    Create a `.env` file by copying the `.env.example`:
    ```bash
    cp .env.example .env
    ```
    Update the `.env` file with your specific configuration, such as OAuth credentials.

## Running the Server

To start the server, first activate the virtual environment and then run the server module:

```bash
source .venv/bin/activate && python -m src
```

The server will start on the configured port (default: 8080).

## Running Tests

To run the test suite, activate the virtual environment and use `pytest`:

```bash
source .venv/bin/activate && pytest
```

For coverage reports:
```bash
source .venv/bin/activate && pytest --cov=src --cov-report=term-missing
```
