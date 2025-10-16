# Development Guidelines

## Database & Migrations
- Use **Alembic** for all database migrations (version-controlled schema changes)
- Always create migrations before modifying models
- Test migrations with sample data before running on full dataset
- Use `async` database operations throughout (asyncpg, SQLAlchemy async)
- Prefer PostgreSQL-specific features (JSONB, GIN indexes, materialized views)

## Code Style
- **Type hints required** on all function signatures
- Use **async/await** patterns consistently
- Follow **PEP 8** for Python style
- Use **docstrings** for public functions/classes
- Prefer **explicit over implicit** (clear variable names, no magic values)

## SQLAlchemy Patterns
- Use declarative models with proper relationships
- Define foreign keys and indexes explicitly
- Use `relationship()` with `back_populates` for bidirectional relationships
- Prefer `select()` over legacy query API
- Always use context managers for sessions

## Logging
- Use **loguru** for structured logging
- Log at appropriate levels: DEBUG, INFO, WARNING, ERROR
- Include context in logs (user_id, resource_id, etc.)
- Never log sensitive data (passwords, tokens)

## API Design
- Return consistent JSON response format (total, limit, offset, results)
- version API endpoints (e.g., /v1/resources)
- Use HTTP status codes appropriately (200, 201, 400, 404, 500)
- Implement pagination, filtering, and sorting on list endpoints
- Use Pydantic models for request/response validation

## Performance
- Use materialized views for read-heavy queries
- Add indexes for frequently filtered/sorted fields
- Consider query result caching for expensive operations
- Monitor query performance with EXPLAIN ANALYZE

## Git Workflow
- Commit migrations separately from model changes
- Use descriptive commit messages
- Test before committing where possible
- Document breaking changes in commit messages
- Use feature branches for large changes
- Write clear PR descriptions and link related issues
- Use frequent, small commits for easier review

## Dependencies
- Use `uv` for package management (not pip/poetry)
- Pin versions in pyproject.toml for reproducibility
- Document why dependencies are added

## configuration
- Use `.env` for environment-specific settings
- Never commit secrets or sensitive info to version control
- Validate configuration on startup (missing vars, invalid formats) using pydantic-settings
- Use sensible defaults where possible
