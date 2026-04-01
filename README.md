# PhxNorth Backend

Behavioral intelligence infrastructure with DISC scoring for the PhxNorth platform.

## Overview

PhxNorth Backend provides the core API services for behavioral analysis, DISC assessment scoring, and user management. Built with FastAPI, SQLAlchemy 2.0, and modern async Python.

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry
- Docker & Docker Compose (for local development)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/phxnorth-backend.git
cd phxnorth-backend

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Development

```bash
# Start development server
poetry run uvicorn app.main:app --reload

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=app --cov-report=html

# Format code
poetry run black .
poetry run isort .

# Type checking
poetry run mypy .

# Linting
poetry run flake8 .
```

### Docker Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Project Structure

```
phxnorth-backend/
├── app/                    # Main application code
├── tests/                  # Test suite
├── alembic/               # Database migrations
├── docker/                # Docker configuration
├── docs/                  # Documentation
├── pyproject.toml         # Poetry configuration
└── README.md             # This file
```

## Documentation

Full documentation is available in the [Obsidian vault](obsidian://open?vault=2026Lrg&file=Projects%2FPhxNorth%2FBackend%2FIndex):

- Architecture: `Projects/PhxNorth/Backend/`
- Implementation Plan: `Projects/PhxNorth/Backend/Implementation_Plan`
- API Documentation: (coming soon)

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

MIT
