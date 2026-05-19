# Contributing to local-data-stack

Thank you for your interest in contributing to local-data-stack. We welcome contributions from the community to help improve this local-first analytics framework for school districts worldwide.

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
- Open an issue with reproduction steps and expected vs. actual behavior
- Include reproduction steps, expected vs. actual behavior
- Provide system information (OS and Python version)

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
- Python 3.9+
- Git

### Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/local-data-stack.git
cd local-data-stack
python -m venv venv
source venv/bin/activate
cp .env.example .env
# edit .env with your local settings before running the pipeline
pip install -e '.[dev]'
python -m pytest oss_framework/tests/
black --check oss_framework
ruff check oss_framework
```

### Development Workflow

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make changes and test
python -m pytest oss_framework/tests/
black --check oss_framework
ruff check oss_framework

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
docs(setup): clarify local development requirements
test(dbt): add tests for attendance aggregation
```

---

## Code Standards

### Python Code

- **Style**: Follow [PEP 8](https://pep8.org/)
- **Formatting**: Use `black` (line length: 100)
- **Linting**: Use `ruff`
- **Type Hints**: Use type annotations where appropriate

```bash
black --check oss_framework
ruff check oss_framework
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
python -m pytest oss_framework/tests/

# Run specific test file
python -m pytest oss_framework/tests/test_public_release_sanitization.py
```

**Test locations:**
- Unit and integration tests: `oss_framework/tests/`

#### dbt Tests

```bash
# Run dbt tests
cd oss_framework/dbt
dbt test --profiles-dir .

# Test specific model
dbt test --profiles-dir . --select dim_students

# Test with data refresh
dbt build --profiles-dir . --target dev
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
   python -m pytest oss_framework/tests/
   ```

3. **Check code quality**
   ```bash
   black --check oss_framework
   ruff check oss_framework
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

- **Reviewers**: Changes in CODEOWNERS-covered paths require approval from @flucido

- **Signed commits required**: All commits must be GPG or SSH signed. See [GitHub's guide on signing commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

- **CI Checks**: When the path-filtered workflow runs, its checks must pass before merging
  - Contract tests
  - Tests (Python 3.9, 3.10, 3.11)
  - Linting
  - Branch must be up-to-date with `main`

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

- **Documentation**: Start with the [repository README](README.md)
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
1. Check the [repository README](README.md)
2. Search [existing discussions](https://github.com/flucido/local-data-stack/discussions)
3. Open a new discussion

Thank you for contributing to local-data-stack.
