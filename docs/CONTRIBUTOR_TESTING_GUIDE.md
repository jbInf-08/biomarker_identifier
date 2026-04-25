# Contributor Testing Guide

## Quick Start

This guide helps contributors understand how to write and run tests for the Cancer Biomarker Identifier project.

## Prerequisites

- Python 3.9+
- pytest installed (`pip install pytest pytest-cov pytest-asyncio pytest-xdist`)
- Access to test database setup

## Setting Up Test Environment

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio pytest-xdist black flake8 mypy
```

### 2. Set Environment Variables

Create a `.env.test` file:

```bash
DATABASE_URL=sqlite:///./test.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key
DEBUG=True
```

### 3. Run Initial Test Setup

```bash
pytest --setup-only
```

## Writing Your First Test

### Example: Testing a Simple Function

```python
# backend/app/utils/calculations.py
def calculate_fold_change(control_mean: float, treatment_mean: float) -> float:
    """Calculate fold change."""
    if control_mean == 0:
        raise ValueError("Control mean cannot be zero")
    return treatment_mean / control_mean

# backend/tests/unit/test_calculations.py
import pytest
from app.utils.calculations import calculate_fold_change

def test_calculate_fold_change_normal():
    """Test normal fold change calculation."""
    result = calculate_fold_change(10.0, 20.0)
    assert result == 2.0

def test_calculate_fold_change_error():
    """Test error handling."""
    with pytest.raises(ValueError):
        calculate_fold_change(0.0, 20.0)
```

### Example: Testing an API Endpoint

```python
# backend/tests/integration/test_api_example.py
def test_get_biomarkers(client, test_user):
    """Test getting biomarkers."""
    # Authenticate
    response = client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "testpassword"},
    )
    token = response.json()["access_token"]
    
    # Make authenticated request
    response = client.get(
        "/api/biomarkers/runs",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

## Using Mock Data Generators

```python
from tests.fixtures.mock_data_generators import MockDataGenerator, TestDataFactory

def test_analysis_with_mock_data():
    """Test analysis with generated mock data."""
    # Generate mock data
    expr_data = MockDataGenerator.generate_gene_expression_data(
        n_samples=50, n_genes=1000, seed=42
    )
    clinical_data = MockDataGenerator.generate_clinical_data(
        n_samples=50, seed=42
    )
    
    # Use in your test
    # ... test logic here ...
```

## Using Test Fixtures

### Available Fixtures

- `db_session`: Database session
- `client`: FastAPI test client
- `test_user`: Regular test user
- `test_admin_user`: Admin test user

### Example Usage

```python
def test_with_database(db_session):
    """Test using database session."""
    # Use db_session to interact with database
    user = User(email="test@example.com", name="Test")
    db_session.add(user)
    db_session.commit()
    
    # Verify
    found = db_session.query(User).filter(User.email == "test@example.com").first()
    assert found is not None
```

## Test Structure Guidelines

### File Organization

```
backend/tests/
├── unit/              # Unit tests
│   ├── test_auth_service.py
│   └── test_biomarker_pipeline.py
├── integration/       # Integration tests
│   ├── test_api_routes.py
│   └── test_pipeline_workflow.py
└── e2e/              # End-to-end tests
    └── test_complete_workflow.py
```

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ComponentName>`
- Test functions: `test_<functionality>`

### Example Structure

```python
import pytest
from app.module import Component

class TestComponent:
    """Test suite for Component."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        component = Component()
        result = component.do_something()
        assert result == expected
    
    def test_edge_case(self):
        """Test edge case."""
        # Test edge case
        pass
    
    @pytest.mark.slow
    def test_slow_operation(self):
        """Test slow operation."""
        # Mark slow tests
        pass
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Type

```bash
# Unit tests only
pytest -m unit

# Integration tests
pytest -m integration

# E2E tests
pytest -m e2e
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html
```

Open `htmlcov/index.html` in browser to view coverage report.

### Run in Parallel (Faster)

```bash
pytest -n auto  # Auto-detect CPU cores
pytest -n 4     # Use 4 workers
```

### Run Specific File/Test

```bash
# Run specific file
pytest tests/unit/test_auth_service.py

# Run specific test
pytest tests/unit/test_auth_service.py::TestAuthService::test_verify_password
```

### Verbose Output

```bash
pytest -v  # Verbose
pytest -vv # Very verbose
pytest -s  # Show print statements
```

## Code Quality Checks

### Before Committing

Run these checks:

```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Check imports
isort app/ tests/

# Type check
mypy app/
```

### Automated Checks

These run automatically in CI/CD, but run locally before pushing.

## Common Patterns

### Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result == expected
```

### Testing Exceptions

```python
def test_raises_exception():
    """Test that exception is raised."""
    with pytest.raises(ValueError, match="error message"):
        function_that_raises()
```

### Parameterized Tests

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_multiply(input, expected):
    """Test multiplication with multiple inputs."""
    assert input * 2 == expected
```

### Fixtures with Parameters

```python
@pytest.fixture
def sample_size(request):
    """Fixture with parameter."""
    return request.param

@pytest.mark.parametrize("sample_size", [10, 50, 100], indirect=True)
def test_with_variable_size(sample_size):
    """Test with different sample sizes."""
    # Use sample_size fixture
    pass
```

## Debugging Tests

### Use Print Statements

```python
def test_debug():
    """Debug test."""
    result = some_function()
    print(f"Result: {result}")  # Use pytest -s to see output
    assert result == expected
```

### Use pytest Debugger

```python
def test_with_breakpoint():
    """Test with breakpoint."""
    result = some_function()
    import pdb; pdb.set_trace()  # Set breakpoint
    assert result == expected
```

### Check Test Coverage

```bash
pytest --cov=app --cov-report=term-missing
```

This shows which lines are not covered.

## Troubleshooting

### Common Issues

**Issue**: Tests fail with database errors
**Solution**: Ensure test database is set up correctly, check `conftest.py`

**Issue**: Import errors
**Solution**: Check PYTHONPATH, ensure you're in the right directory

**Issue**: Tests are slow
**Solution**: Use parallel execution (`pytest -n auto`), check for unnecessary setup

**Issue**: Flaky tests
**Solution**: Check for race conditions, use proper fixtures, avoid shared state

### Getting Help

1. Check existing tests for examples
2. Review `TESTING_GUIDE.md` in the repository root
3. Ask in team chat
4. Create an issue if needed

## Checklist Before Submitting

- [ ] All tests pass locally
- [ ] Code is formatted (black)
- [ ] Code passes linting (flake8)
- [ ] Type checking passes (mypy)
- [ ] Test coverage is maintained or improved
- [ ] Tests are well-documented
- [ ] Edge cases are covered
- [ ] Error cases are tested

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Testing Best Practices](https://realpython.com/python-testing/)
- The root `TESTING_GUIDE.md`

---

**Happy Testing!** 🧪
