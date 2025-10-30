# Contributing Guide

Thank you for your interest in contributing to f9_file_backend! This guide will help you add new features, fix bugs, and maintain the codebase.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Adding New Backend Implementations](#adding-new-backend-implementations)
- [Pull Request Process](#pull-request-process)
- [Architecture](#architecture)

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch** from `main`: `git checkout -b feature/your-feature-name`
4. **Make your changes**
5. **Write/update tests**
6. **Run the test suite** and ensure all tests pass
7. **Commit with clear messages**
8. **Push to your fork** and open a pull request

## Development Setup

### Prerequisites

- Python 3.9+
- Git
- pip or your preferred package manager

### Setting up the Environment

```bash
# Clone the repository
git clone https://github.com/your-username/f9_file_backend.git
cd f9_file_backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=f9_file_backend --cov-report=html

# Run specific test file
pytest tests/test_local.py -v

# Run integration tests
pytest tests/integration/ -v

# Run with markers
pytest -m "not slow" tests/  # Skip slow tests
```

### Code Quality Tools

```bash
# Format code
ruff format f9_file_backend/ tests/

# Check linting
ruff check f9_file_backend/ tests/

# Type checking
mypy f9_file_backend/

# Pre-commit hook
.githooks/pre-commit
```

## Code Style

### Python Style Guide

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with the following exceptions/additions:

- **Line length:** 100 characters (enforced by ruff)
- **Imports:** Organized with isort
- **Type hints:** Required for all public APIs
- **Docstrings:** Google-style docstrings

### Docstring Example

```python
def create(
    self,
    path: PathLike,
    *,
    data: bytes | str | BinaryIO | None = None,
    overwrite: bool = False,
) -> FileInfo:
    """Create a new file with optional initial content.

    Creates a file at the specified path. If data is provided, it will be
    written to the file. The operation fails if the file already exists
    unless overwrite=True is specified.

    Args:
        path: Path to the file to create. Must be relative to the root.
        data: Initial file content. Can be bytes, string (UTF-8 encoded),
            or a file-like object. Defaults to empty file.
        overwrite: If True, replace existing files. If False (default),
            raises AlreadyExistsError if file exists.

    Returns:
        FileInfo object with metadata about the created file.

    Raises:
        AlreadyExistsError: If file exists and overwrite=False.
        InvalidOperationError: If path is invalid or outside root.
        NotFoundError: If parent directory doesn't exist (some backends).

    Example:
        >>> backend.create("file.txt", data=b"Hello")
        FileInfo(path="file.txt", size=5, ...)

    Note:
        The behavior of parent directory creation varies by backend.
        LocalFileBackend creates parent directories automatically.
    """
```

### Type Hints

```python
# Good: Clear and specific types
def read(self, path: PathLike, *, binary: bool = True) -> bytes | str:
    ...

# Good: Using Union for complex types
from typing import BinaryIO
def update(self, path: PathLike, *, data: bytes | str | BinaryIO) -> FileInfo:
    ...

# Bad: Using Any for everything
def read(self, path, binary=True):
    ...
```

## Testing

### Test Organization

Tests are organized by backend:

- `tests/test_utils.py` - Utility functions
- `tests/test_path_utils.py` - Path validation
- `tests/test_validation.py` - Validation protocol
- `tests/test_local.py` - LocalFileBackend
- `tests/test_openai_backend.py` - OpenAIVectorStoreFileBackend
- `tests/test_git_backend.py` - GitSyncFileBackend
- `tests/integration/` - Integration tests

### Writing Tests

#### Unit Tests

Test a single function or method:

```python
def test_get_hasher_sha256():
    """Test hasher creation for SHA256 algorithm."""
    hasher = get_hasher("sha256")
    hasher.update(b"test")
    assert len(hasher.hexdigest()) == 64  # SHA256 is 256 bits = 64 hex chars
```

#### Parameterized Tests

Test multiple backends with the same test:

```python
@pytest.fixture(
    params=[
        "local",
        "openai",  # Skip with @pytest.mark.skip_openai if no API key
    ]
)
def backend(request, tmp_path, monkeypatch):
    if request.param == "local":
        return LocalFileBackend(tmp_path)
    elif request.param == "openai":
        return OpenAIVectorStoreFileBackend(...)

def test_create_read_roundtrip(backend):
    """All backends must support basic create/read."""
    backend.create("test.txt", data=b"Content")
    assert backend.read("test.txt") == b"Content"
```

#### Integration Tests

Test real-world scenarios:

```python
def test_streaming_large_file(tmp_path):
    """Test streaming large files doesn't load into memory."""
    backend = LocalFileBackend(tmp_path)

    # Create a large file via streaming
    chunks = [b"x" * 8192 for _ in range(1000)]  # 8MB
    backend.stream_write("large.bin", chunk_source=iter(chunks))

    # Read via streaming
    total = 0
    for chunk in backend.stream_read("large.bin"):
        total += len(chunk)

    assert total == 8192 * 1000
```

### Test Coverage

- **Minimum coverage:** 90%
- **Utility modules:** 95%
- **Public APIs:** 100%
- **Error paths:** 100%

Check coverage:

```bash
pytest tests/ --cov=f9_file_backend --cov-report=html
# Open htmlcov/index.html to see detailed report
```

## Adding New Backend Implementations

### Overview

A new backend should support any storage mechanism - cloud storage (S3, Azure), remote protocols (SFTP, FTP), or in-memory storage.

### Step 1: Understand the FileBackend Interface

Review the abstract base class:

```python
from f9_file_backend.interfaces import FileBackend

class MyBackend(FileBackend):
    # Must implement these methods...
    def create(self, path: PathLike, *, data=None, overwrite=False) -> FileInfo: ...
    def read(self, path: PathLike, *, binary: bool = True) -> bytes | str: ...
    def update(self, path: PathLike, *, data, overwrite_mode="replace") -> FileInfo: ...
    # ... etc
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for design patterns.

### Step 2: Choose Your Storage Mechanism

Decide how to store files:

- **Filesystem-based:** Use LocalFileBackend composition (like GitSyncFileBackend)
- **Remote API:** Implement directly (like OpenAIVectorStoreFileBackend)
- **In-memory:** Dictionary-based storage for testing

### Step 3: Implement Path Validation

Choose an approach:

```python
# Filesystem-aware (for local storage)
def _ensure_within_root(self, path: PathLike) -> Path:
    candidate = (self._root / Path(path)).resolve(strict=False)
    try:
        candidate.relative_to(self._root)
    except ValueError as exc:
        raise InvalidOperationError.path_outside_root(candidate) from exc
    return candidate

# Virtual path (for remote storage)
def _normalise_path(self, path: PathLike) -> str:
    path_str = str(path).replace("\\", "/")
    pure = PurePosixPath(path_str)
    if pure.is_absolute() or ".." in pure.parts:
        raise InvalidOperationError.path_outside_root(path_str)
    return pure.as_posix()
```

Use helpers from `path_utils.py`:

```python
from f9_file_backend.path_utils import (
    validate_not_empty,
    validate_not_root,
    detect_path_traversal_posix,
    normalize_windows_path,
)
```

### Step 4: Use Shared Utilities

Check if utilities already exist before reimplementing:

```python
# Data coercion
from f9_file_backend.utils import coerce_to_bytes

# Checksums
from f9_file_backend.utils import (
    compute_checksum_from_file,
    compute_checksum_from_bytes,
)

# Chunk handling
from f9_file_backend.utils import accumulate_chunks

# Validation
from f9_file_backend.validation import (
    validate_entry_exists,
    validate_entry_not_exists,
    validate_is_file,
)
```

### Step 5: Handle Errors Consistently

Use standard exceptions:

```python
from f9_file_backend.interfaces import (
    NotFoundError,
    AlreadyExistsError,
    InvalidOperationError,
)

# Path doesn't exist
if not entry:
    raise NotFoundError(path)

# Path already exists
if entry and not overwrite:
    raise AlreadyExistsError(path)

# Can't read directory as file
if entry.is_dir:
    raise InvalidOperationError.cannot_read_directory(path)
```

### Step 6: Create the Implementation

Template:

```python
"""Description of MyBackend."""

from f9_file_backend.interfaces import FileBackend, FileInfo
from pathlib import Path
from typing import BinaryIO

class MyBackend(FileBackend):
    """Storage backend using [storage mechanism]."""

    def __init__(self, **config):
        """Initialize backend with configuration."""
        # Store configuration
        # Initialize storage connection
        pass

    def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a new file."""
        # Validate path
        # Check if exists
        # Create file
        # Return FileInfo
        pass

    # Implement remaining abstract methods...
```

### Step 7: Write Tests

Create three test files:

```
tests/
├── test_mybackend.py                 # Unit tests
└── integration/
    └── test_mybackend_integration.py # Integration tests
```

Unit tests:

```python
# tests/test_mybackend.py
import pytest
from f9_file_backend import MyBackend

@pytest.fixture
def backend():
    return MyBackend(config=...)

def test_create_file(backend):
    backend.create("test.txt", data=b"Hello")
    assert backend.exists("test.txt")

def test_read_nonexistent_raises(backend):
    with pytest.raises(NotFoundError):
        backend.read("nonexistent.txt")

# ... more tests
```

Parameterized tests for shared behavior:

```python
# Add to tests/test_shared_behavior.py
@pytest.fixture(
    params=["local", "mybackend"]
)
def backend(request, tmp_path):
    if request.param == "local":
        return LocalFileBackend(tmp_path)
    elif request.param == "mybackend":
        return MyBackend(config=...)

def test_all_backends_support_basic_operations(backend):
    """All backends must support create/read/delete."""
    # Test shared behavior
```

### Step 8: Document the Backend

Update documentation:

1. **ARCHITECTURE.md** - Add section about your backend
2. **Module docstring** - Add comprehensive docstring with examples
3. **README.md** - Add usage example

Example docstring:

```python
"""MyBackend implementation of FileBackend.

This module provides [description of storage mechanism].

Key Features:
    - Feature 1
    - Feature 2
    - Feature 3

Path Validation:
    [Describe path validation strategy]

Storage Mechanism:
    [Describe where/how files are stored]

Example:

    >>> from f9_file_backend import MyBackend
    >>> backend = MyBackend(config=...)
    >>> backend.create("file.txt", data=b"Hello")
    >>> content = backend.read("file.txt")
"""
```

### Step 9: Run Tests and Coverage

```bash
# Run all tests including new backend
pytest tests/ -v

# Check coverage
pytest tests/ --cov=f9_file_backend --cov-report=html

# Ensure 90%+ coverage
```

### Step 10: Submit Pull Request

Follow the [Pull Request Process](#pull-request-process) below.

## Pull Request Process

### Before You Submit

1. **Update tests** - Add tests for your changes
2. **Run tests** - `pytest tests/ -v`
3. **Check coverage** - Should be 90%+
4. **Format code** - `ruff format f9_file_backend/`
5. **Lint** - `ruff check f9_file_backend/`
6. **Type check** - `mypy f9_file_backend/`
7. **Update documentation** - Add docstrings, update ARCHITECTURE.md if needed
8. **Commit with clear message** - Reference issue if applicable

### Pull Request Template

```markdown
## Description
Briefly describe what changes were made and why.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] New backend implementation
- [ ] Refactoring

## Related Issues
Closes #ISSUE_NUMBER

## Testing
- [ ] Added/updated unit tests
- [ ] Added/updated integration tests
- [ ] All tests pass locally
- [ ] Coverage is 90%+

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] No breaking changes (or documented)
- [ ] Commit messages are clear

## Screenshots (if applicable)
```

### Review Process

1. **Maintainers review** your code
2. **Address feedback** - Push additional commits to your PR
3. **Squash commits** - If requested
4. **Merge** - Once approved, maintainers will merge to main

## Architecture

For detailed architecture information, see:

- [ARCHITECTURE.md](ARCHITECTURE.md) - Design patterns, validation strategies, error handling
- [REFACTORING_PLAN.md](REFACTORING_PLAN.md) - Current refactoring phases and status

Key concepts:

- **FileBackend interface** - All backends implement this abstract base class
- **Composition pattern** - Use for adding behavior (like GitSyncFileBackend)
- **Shared utilities** - Use existing utilities to avoid duplication
- **Path validation** - Two strategies: filesystem-aware vs. virtual paths
- **Error consistency** - Use standard exception hierarchy

## Questions?

- **Architecture questions** - See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Bug reports** - Open an issue on GitHub
- **Feature requests** - Open an issue or discussion
- **API documentation** - Check docstrings and type hints

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

---

**Last Updated:** 2025-10-30
