# File Backend Library

`f9_file_backend` provides a consistent interface for working with different file storage providers. The initial release includes a local filesystem backend; additional implementations can plug into the same API.

## Installation

Install into your environment (`pip install -e .` for editable development installs). Then import the backend you need:

```python
from f9_file_backend import LocalFileBackend
```

## Usage

```python
from f9_file_backend import LocalFileBackend

backend = LocalFileBackend(root="data")

# Create a file
backend.create("example.txt", data="hello world")

# Inspect a file
info = backend.info("example.txt")
print(info.as_dict())

# Read content (text or bytes)
text = backend.read("example.txt", binary=False)

# Update a file
backend.update("example.txt", data="\nnew line", append=True)

# Manage directories
backend.create("reports", is_directory=True)
backend.delete("reports", recursive=True)

# Remove a file
backend.delete("example.txt")
```

Each backend must support the `FileBackend` interface, so introducing new storage providers is as simple as adding another implementation.
