# Contributing to OSS Framework

Thank you for your interest in contributing to the OSS Framework! We welcome contributions from the community to help improve this platform for school districts worldwide.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Contribution Guidelines](#contribution-guidelines)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

---

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

---

## How to Contribute

We welcome several types of contributions:

### 🐛 Bug Reports

- Search [existing issues](https://github.com/flucido/local-data-stack/issues) first
- Use the bug report template
- Include reproduction steps, expected vs. actual behavior
- Provide system information (OS, Python version, Docker version)

### ✨ Feature Requests

- Search [existing feature requests](https://github.com/flucido/local-data-stack/issues?q=is%3Aissue+label%3Aenhancement)
- Describe the use case and benefits for school districts
- Consider implementation approach (optional)

### 📝 Documentation Improvements

- Fix typos, clarify instructions
- Add examples or troubleshooting guides
- Improve architecture diagrams

### 🔧 Code Contributions

- Bug fixes
- New features
- Performance improvements
- Test coverage improvements

---

## Development Setup

### Prerequisites

- Ubuntu 20.04+ or macOS or Windows with WSL2
- Python 3.10+
- Docker and Docker Compose
- Git
- 16GB+ RAM (32GB recommended)

### Local Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/local-data-stack.git
cd local-data-stack/oss_framework

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# 4. Start services
docker-compose up -d

# 5. Run tests
pytest tests/

# 6. Initialize dbt
cd dbt
dbt deps
dbt build --target test
```

### Development Workflow

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make changes and test
pytest tests/
cd dbt && dbt test

# Commit with descriptive messages
git add .
git commit -m "feat: add student cohort analysis"

# Push and open a PR
git push origin feature/your-feature-name
```

---

## Contribution Guidelines

### 1. Start with an Issue

- For bug fixes: reference an existing issue or create one
- For new features: discuss in an issue first before implementing
- For large changes: request a design review

### 2. Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `test/description` - Test additions/changes

### 3. Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

**Examples:**
```
feat(dbt): add student cohort tracking model
fix(ingestion): handle missing attendance records
docs(setup): clarify Docker requirements
test(dbt): add tests for attendance aggregation
```

---

## Code Standards

### Python Code

- **Style**: Follow [PEP 8](https://pep8.org/)
- **Formatting**: Use `black` (line length: 100)
- **Linting**: Use `flake8` and `pylint`
- **Type Hints**: Use type annotations where appropriate

```bash
# Format code
black src/ tests/

# Check linting
flake8 src/ tests/
pylint src/
```

### dbt Models

- **Naming**:
  - `stg_<source>_<entity>.sql` - Staging models
  - `int_<description>.sql` - Intermediate models
  - `fct_<description>.sql` - Fact tables
  - `dim_<description>.sql` - Dimension tables
- **Style**: Use [dbt SQL style guide](https://docs.getdbt.com/guides/best-practices/how-we-style/sql-style-guide)
- **Tests**: Add schema tests (unique, not_null, relationships)
- **Documentation**: Document all models in `schema.yml`

```sql
-- Example: Good dbt model structure
{{
  config(
    materialized='table',
    schema='refined'
  )
}}

with source_data as (
    select * from {{ ref('stg_sis_students') }}
),

final as (
    select
        student_id,
        full_name,
        grade_level,
        enrollment_date
    from source_data
    where is_active = true
)

select * from final
```

### SQL Queries

- Use lowercase for SQL keywords
- Use meaningful table aliases
- Add comments for complex logic
- Use CTEs instead of subqueries for readability

---

## Testing Requirements

### Required Tests

All code contributions must include appropriate tests:

#### Python Tests (pytest)

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_ingestion.py

# Run with coverage
pytest --cov=src tests/
```

**Test locations:**
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- End-to-end tests: `tests/e2e/`

#### dbt Tests

```bash
# Run dbt tests
cd dbt
dbt test

# Test specific model
dbt test --select dim_students

# Test with data refresh
dbt build --target test
```

**Required dbt tests:**
- `unique` on primary keys
- `not_null` on required fields
- `relationships` for foreign keys
- `accepted_values` for enums

#### Manual Testing Checklist

- [ ] Code runs without errors
- [ ] Existing functionality not broken
- [ ] New features work as expected
- [ ] Documentation updated
- [ ] No sensitive data in commits

---

## Pull Request Process

### Before Submitting

1. **Update your branch**
   ```bash
   git checkout main
   git pull origin main
   git checkout your-branch
   git rebase main
   ```

2. **Run all tests**
   ```bash
   pytest tests/
   cd dbt && dbt test
   ```

3. **Check code quality**
   ```bash
   black --check src/
   flake8 src/
   ```

4. **Update documentation**
   - Update README if adding features
   - Add/update docstrings
   - Update relevant markdown docs

### PR Guidelines

- **Title**: Use conventional commit format
  - `feat: Add student cohort analysis`
  - `fix: Resolve null handling in attendance`
  
- **Description**: Include:
  - What changed and why
  - Related issue number (`Fixes #123`)
  - Testing performed
  - Screenshots (if UI changes)
  - Breaking changes (if any)

- **Reviewers**: Request review from maintainers

- **CI Checks**: Ensure all checks pass
  - Tests
  - Linting
  - Security scans

### PR Template

```markdown
## Description
Brief description of changes

## Related Issue
Fixes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
- [ ] Unit tests added/updated
- [ ] dbt tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

---

## Community

### Getting Help

- **Documentation**: Start with [oss_framework/docs/](oss_framework/docs/README.md)
- **Discussions**: [GitHub Discussions](https://github.com/flucido/local-data-stack/discussions)
- **Issues**: [GitHub Issues](https://github.com/flucido/local-data-stack/issues)

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: Questions, ideas, showcases
- **Pull Requests**: Code review and collaboration

### Recognition

Contributors are recognized in:
- Repository insights
- Release notes
- Project documentation

---

## License

By contributing to this project, you agree that your contributions will be licensed under:
- **Code**: [MIT License](LICENSE-CODE)
- **Documentation**: [Creative Commons Attribution 4.0](LICENSE)

---

## Questions?

If you have questions about contributing, please:
1. Check the [documentation](oss_framework/docs/README.md)
2. Search [existing discussions](https://github.com/flucido/local-data-stack/discussions)
3. Open a new discussion

Thank you for contributing to OSS Framework! 🎉
