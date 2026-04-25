# Testing Guide for Cancer Biomarker Identifier

This guide provides comprehensive information on how to test the Cancer Biomarker Identifier project, including setup, running tests, and best practices.

## Table of Contents

1. [Testing Overview](#testing-overview)
2. [Test Infrastructure](#test-infrastructure)
3. [Running Tests](#running-tests)
4. [Test Types](#test-types)
5. [Frontend Testing](#frontend-testing)
6. [Backend Testing](#backend-testing)
7. [Integration Testing](#integration-testing)
8. [End-to-End Testing](#end-to-end-testing)
9. [Performance Testing](#performance-testing)
10. [Data Collection Testing](#data-collection-testing)
11. [Test Coverage](#test-coverage)
12. [CI/CD Integration](#cicd-integration)
13. [Best Practices](#best-practices)

## Testing Overview

The project uses a comprehensive testing strategy with multiple layers:

- **Unit Tests**: Test individual components and functions in isolation
- **Integration Tests**: Test API endpoints and database interactions
- **End-to-End Tests**: Test complete user workflows
- **Performance Tests**: Load testing and performance benchmarking
- **Data Collection Tests**: Test data collector modules

### Test coverage goals

- **Backend:** many CI flows target **80%** or higher line coverage; confirm with your `pytest` / workflow invocation.
- **Frontend:** Jest enforces the thresholds in `frontend/package.json` (`jest.coverageThreshold`); they are not a fixed 70% global today.
- **API:** cover critical paths in integration and unit tests; there is no single fixed “90% endpoints” rule in the repo.

## Test Infrastructure

### Backend Testing Stack

- **pytest**: Primary testing framework
- **pytest-cov**: Code coverage reporting
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking utilities
- **pytest-xdist**: Parallel test execution
- **pytest-html**: HTML test reports
- **pytest-benchmark**: Performance benchmarking
- **httpx**: HTTP client for API testing
- **factory-boy**: Test data factories
- **faker**: Fake data generation

### Frontend Testing Stack

- **@testing-library/react**: React component testing
- **@testing-library/jest-dom**: DOM matchers
- **@testing-library/user-event**: User interaction simulation
- **react-scripts**: Built-in Jest test runner

### Test Configuration

The project uses `backend/pytest.ini` for backend test configuration. The real file is the source of truth; a snapshot:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
filterwarnings = ...
markers =
    slow: long-running tests
    integration: integration tests
    e2e: hits a running server at localhost (run after docker compose up)
```

Coverage and other `addopts` (for example `--cov=app` or `--cov-fail-under=80`) are often passed on the `pytest` command line or in CI, not only in this file.

## Running Tests

### Quick Start

```bash
# Run all tests
python backend/run_tests.py

# Run with coverage
python backend/run_tests.py --coverage

# Run specific test type
python backend/run_tests.py --type unit
python backend/run_tests.py --type integration
python backend/run_tests.py --type e2e
```

### Backend Tests

#### Using pytest directly

```bash
# Navigate to backend directory
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_auth_service.py

# Run tests with specific marker
pytest -m unit
pytest -m integration
pytest -m "auth and not slow"

# Run tests in parallel
pytest -n auto

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test function
pytest tests/unit/test_auth_service.py::TestAuthService::test_verify_password
```

#### Using the test runner script

```bash
# From project root
python backend/run_tests.py --type all --coverage --verbose

# Run only unit tests
python backend/run_tests.py --type unit

# Run with specific markers
python backend/run_tests.py --markers "auth and not slow"

# Run specific file
python backend/run_tests.py --file tests/unit/test_auth_service.py
```

### Frontend Tests

```bash
# Navigate to frontend directory
cd frontend

# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage

# Run tests in CI mode (single run)
CI=true npm test
```

### Root-Level Test Suite

```bash
# From project root
python tests/run_all_tests.py
```

This runs:
- Unit tests
- Integration tests
- Smoke tests
- Performance tests
- Mock data tests

## Test Types

### Unit Tests

Unit tests test individual components in isolation.

**Location**: `backend/tests/unit/`

**Example**:
```python
def test_verify_password():
    """Test password verification."""
    password = "testpassword"
    hashed = auth_service.get_password_hash(password)
    
    assert auth_service.verify_password(password, hashed) is True
    assert auth_service.verify_password("wrongpassword", hashed) is False
```

**Running unit tests**:
```bash
pytest tests/unit/ -m unit
```

### Integration Tests

Integration tests test API endpoints and database interactions.

**Location**: `backend/tests/integration/`

**Example**:
```python
def test_login_endpoint(client, test_user):
    """Test login endpoint."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    
    assert response.status_code == 200
    assert "access_token" in response.json()
```

**Running integration tests**:
```bash
pytest tests/integration/ -m integration
```

### End-to-End Tests

E2E tests test complete user workflows.

**Location**: `backend/tests/e2e/`

**Running E2E tests**:

- **`tests/e2e/test_simple_workflow.py`** hits a **live** API at `http://127.0.0.1:8000` (marked `@pytest.mark.e2e`). Start the backend first, then run:
  ```bash
  cd backend
  uvicorn app.main:app --host 127.0.0.1 --port 8000
  # other terminal:
  pytest tests/e2e/ -m e2e
  ```
  If `/health` is unreachable, those tests are **skipped** locally (unless `CI=true` or `E2E_REQUIRE_LIVE_SERVER=1`).
- **All files under `tests/e2e/`** (including `TestClient` workflows) in one go:
  ```bash
  cd backend
  uvicorn app.main:app --host 127.0.0.1 --port 8000
  pytest tests/e2e/
  ```

## Frontend Testing

### Component Testing

Test React components using React Testing Library:

```javascript
import { render, screen } from '@testing-library/react';
import { LoginPage } from './LoginPage';

test('renders login form', () => {
  render(<LoginPage />);
  const emailInput = screen.getByLabelText(/email/i);
  expect(emailInput).toBeInTheDocument();
});
```

### Running Frontend Tests

```bash
cd frontend
npm test
```

### Frontend Test Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── __tests__/      # Component tests
│   ├── pages/
│   │   └── __tests__/      # Page tests
│   └── services/
│       └── __tests__/      # Service tests
```

### Frontend Test Best Practices

1. **Test user interactions, not implementation details**
2. **Use data-testid sparingly** (prefer accessible queries)
3. **Mock API calls** using MSW (Mock Service Worker) or jest.mock
4. **Test accessibility** using @testing-library/jest-dom
5. **Keep tests simple and focused**

## Backend Testing

### Test Fixtures

The project uses pytest fixtures defined in `backend/tests/conftest.py`:

- `db_session`: Database session for each test
- `client`: FastAPI test client
- `test_user`: Test user fixture
- `test_admin_user`: Admin user fixture
- `auth_headers`: Authentication headers
- `sample_expression_data`: Sample expression data
- `sample_clinical_data`: Sample clinical data
- `mock_redis`: Mock Redis client
- `mock_celery`: Mock Celery client

### Using Fixtures

```python
def test_biomarker_analysis(client, auth_headers, sample_expression_data):
    """Test biomarker analysis endpoint."""
    response = client.post(
        "/api/biomarkers/run",
        headers=auth_headers,
        json={
            "expression_data": sample_expression_data.to_dict()
        }
    )
    
    assert response.status_code == 200
```

### Database Testing

Tests use an in-memory SQLite database:

```python
@pytest.fixture(scope="function")
def db_session() -> Generator:
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
```

### Mocking External Services

```python
@patch('app.services.external_api.get_data')
def test_external_api_integration(mock_get_data):
    """Test external API integration with mocking."""
    mock_get_data.return_value = {"status": "success"}
    
    result = external_service.fetch_data()
    
    assert result["status"] == "success"
    mock_get_data.assert_called_once()
```

## Integration Testing

### API Endpoint Testing

Test API endpoints with authentication:

```python
def test_get_biomarker_results(client, auth_headers, test_analysis_run):
    """Test getting biomarker results."""
    response = client.get(
        f"/api/biomarkers/runs/{test_analysis_run.id}/results",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert "biomarkers" in response.json()
```

### Database Integration Testing

Test database operations:

```python
def test_create_analysis_run(db_session, test_user):
    """Test creating an analysis run."""
    run = AnalysisRun(
        project_name="Test Project",
        user_id=str(test_user.id),
        status="pending"
    )
    
    db_session.add(run)
    db_session.commit()
    
    assert run.id is not None
    assert run.status == "pending"
```

## End-to-End Testing

### Complete Workflow Testing

Test complete user workflows:

```python
@pytest.mark.e2e
def test_complete_biomarker_workflow(client, test_user):
    """Test complete biomarker identification workflow."""
    # 1. Login
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Start analysis
    start_response = client.post(
        "/api/biomarkers/run",
        headers=headers,
        json={
            "project_name": "E2E Test",
            "expression_file": "test_data.csv"
        }
    )
    run_id = start_response.json()["run_id"]
    
    # 3. Check status
    status_response = client.get(
        f"/api/biomarkers/runs/{run_id}/status",
        headers=headers
    )
    assert status_response.json()["status"] in ["pending", "running", "completed"]
    
    # 4. Get results
    results_response = client.get(
        f"/api/biomarkers/runs/{run_id}/results",
        headers=headers
    )
    assert results_response.status_code == 200
```

## Performance Testing

### Load Testing with Locust

Create a Locust file for load testing:

```python
# locustfile.py
from locust import HttpUser, task, between

class BiomarkerUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def get_biomarker_results(self):
        self.client.get("/api/biomarkers/runs")
    
    @task(3)
    def start_analysis(self):
        self.client.post("/api/biomarkers/run", json={...})
```

**Run Locust**:
```bash
locust -f locustfile.py
```

### Benchmark Testing

Use pytest-benchmark for performance benchmarks:

```python
def test_data_transformation_performance(benchmark, sample_expression_data):
    """Benchmark data transformation performance."""
    transformer = DataTransformation()
    result = benchmark(transformer.log2, sample_expression_data)
    assert result is not None
```

**Run benchmarks**:
```bash
pytest --benchmark-only
```

## Data Collection Testing

### Testing Data Collectors

Test data collection modules:

```bash
# Test all collectors
python data_collection/test_all_collectors.py

# Test specific collector
python -m pytest data_collection/test_tcga_collector.py
```

### Collector Test Structure

```python
def test_collector_initialization():
    """Test collector initialization."""
    collector = TCGACollector(output_dir="test_output")
    assert collector.output_dir == "test_output"

def test_get_available_datasets():
    """Test getting available datasets."""
    collector = TCGACollector(output_dir="test_output")
    datasets = collector.get_available_datasets()
    assert len(datasets) > 0
```

## Test Coverage

### Generating Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html

# Generate terminal coverage report
pytest --cov=app --cov-report=term-missing
```

### Coverage Goals

- **Backend**: 80%+ code coverage
- **Frontend**: 70%+ code coverage
- **API Endpoints**: 90%+ endpoint coverage

### Coverage Configuration

Coverage is configured in `pytest.ini`:

```ini
--cov=app
--cov-report=html
--cov-report=term-missing
--cov-fail-under=80
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

Pre-commit hooks can run:
- Code formatting (black)
- Linting (flake8)
- Type checking (mypy)
- Tests (pytest)

## Best Practices

### Writing Tests

1. **Follow AAA pattern**: Arrange, Act, Assert
2. **Use descriptive test names**: `test_should_return_error_when_user_not_found`
3. **One assertion per test** (when possible)
4. **Test edge cases**: Empty inputs, null values, boundary conditions
5. **Use fixtures** for common setup
6. **Mock external dependencies**: APIs, databases, file systems
7. **Keep tests fast**: Unit tests should run in milliseconds
8. **Test behavior, not implementation**: Focus on what, not how

### Test Organization

```
backend/tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_auth_service.py
│   └── test_biomarker_pipeline.py
├── integration/             # Integration tests
│   ├── test_auth_api.py
│   └── test_biomarker_api.py
└── e2e/                     # End-to-end tests
    └── test_complete_workflow.py
```

### Test Data Management

1. **Use factories** (factory-boy) for test data
2. **Use faker** for realistic fake data
3. **Clean up test data** after each test
4. **Use fixtures** for common test data
5. **Avoid hardcoded test data** when possible

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_unit_function():
    pass

@pytest.mark.integration
def test_integration_function():
    pass

@pytest.mark.slow
def test_slow_function():
    pass

@pytest.mark.auth
def test_auth_function():
    pass
```

Run tests by marker:
```bash
pytest -m unit
pytest -m "integration and not slow"
```

### Debugging Tests

```bash
# Run with verbose output
pytest -v

# Run with print statements
pytest -s

# Run with debugger
pytest --pdb

# Run specific test with debugging
pytest tests/unit/test_auth_service.py::TestAuthService::test_verify_password -v -s --pdb
```

### Test Maintenance

1. **Keep tests up to date** with code changes
2. **Remove obsolete tests**
3. **Refactor tests** when they become complex
4. **Document complex test scenarios**
5. **Review test coverage** regularly

## Troubleshooting

### Common Issues

1. **Database connection errors**: Ensure test database is properly configured
2. **Import errors**: Check PYTHONPATH and module structure
3. **Fixture errors**: Verify fixture scope and dependencies
4. **Async test errors**: Use pytest-asyncio and proper async/await
5. **Mock errors**: Ensure mocks are properly configured

### Getting Help

- Check test logs for detailed error messages
- Run tests with `-v` for verbose output
- Use `--pdb` to debug failing tests
- Review test fixtures in `conftest.py`
- Check pytest documentation: https://docs.pytest.org/

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [React Testing Library](https://testing-library.com/react)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)

---

**Last Updated**: 2024
**Maintained By**: Development Team

