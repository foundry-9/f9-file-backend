"""Multi-instance management and vault registry for file backends.

This module provides a registry system for managing multiple file backend instances
(vaults) and switching between them dynamically through context managers.

Example:
    >>> from f9_file_backend import LocalFileBackend, vault_context, register_vault
    >>> from pathlib import Path
    >>>
    >>> # Create multiple backend instances
    >>> data_backend = LocalFileBackend(root=Path("/data"))
    >>> cache_backend = LocalFileBackend(root=Path("/cache"))
    >>>
    >>> # Register them with the global registry
    >>> register_vault("data", data_backend)
    >>> register_vault("cache", cache_backend)
    >>>
    >>> # Switch between vaults using context manager
    >>> with vault_context("data"):
    ...     data_backend.create("file.txt", data=b"Hello")
    ...
    >>> with vault_context("cache"):
    ...     cache_backend.create("temp.txt", data=b"Temp")

"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

from .interfaces import FileBackend


class VaultRegistry:
    """Registry for managing multiple file backend instances (vaults).

    Provides methods to register, unregister, and retrieve named backend instances
    along with their associated options.
    """

    def __init__(self) -> None:
        """Initialize an empty vault registry."""
        self._vaults: dict[str, FileBackend] = {}
        self._options: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        backend: FileBackend,
        *,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Register a file backend instance with a given name.

        Args:
            name: Unique identifier for the vault
            backend: FileBackend instance to register
            options: Optional dict of configuration options for this vault

        Raises:
            ValueError: If a vault with this name already exists.

        """
        if name in self._vaults:
            msg = f"Vault '{name}' already registered"
            raise ValueError(msg)
        self._vaults[name] = backend
        self._options[name] = options or {}

    def unregister(self, name: str) -> None:
        """Unregister and remove a vault from the registry.

        Args:
            name: Name of the vault to unregister

        Raises:
            KeyError: If vault with this name doesn't exist.

        """
        if name not in self._vaults:
            msg = f"Vault '{name}' not found"
            raise KeyError(msg)
        del self._vaults[name]
        del self._options[name]

    def get(self, name: str) -> FileBackend:
        """Retrieve a registered vault by name.

        Args:
            name: Name of the vault to retrieve

        Returns:
            The FileBackend instance for this vault

        Raises:
            KeyError: If vault with this name doesn't exist.

        """
        if name not in self._vaults:
            msg = f"Vault '{name}' not found"
            raise KeyError(msg)
        return self._vaults[name]

    def list(self) -> list[str]:
        """List all registered vault names.

        Returns:
            List of vault names in registration order.

        """
        return list(self._vaults.keys())

    def get_options(self, name: str) -> dict[str, Any]:
        """Retrieve options associated with a vault.

        Args:
            name: Name of the vault

        Returns:
            Dictionary of options for this vault

        Raises:
            KeyError: If vault with this name doesn't exist.

        """
        if name not in self._vaults:
            msg = f"Vault '{name}' not found"
            raise KeyError(msg)
        return self._options[name].copy()

    def exists(self, name: str) -> bool:
        """Check if a vault with the given name is registered.

        Args:
            name: Name of the vault to check

        Returns:
            True if vault exists, False otherwise.

        """
        return name in self._vaults


class VaultContext:
    """Context manager for working with a specific vault instance.

    Provides a way to switch the active vault for the duration of a context block.
    """

    def __init__(self, registry: VaultRegistry, name: str) -> None:
        """Initialize a vault context.

        Args:
            registry: The VaultRegistry instance to use
            name: Name of the vault to activate

        """
        self.registry = registry
        self.name = name
        self._backend: FileBackend | None = None

    def __enter__(self) -> FileBackend:
        """Enter the context and return the active backend.

        Returns:
            The FileBackend instance for the active vault

        Raises:
            KeyError: If the named vault doesn't exist.

        """
        self._backend = self.registry.get(self.name)
        return self._backend

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context and release the backend reference.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        """
        self._backend = None


# Global registry instance
_global_registry = VaultRegistry()


def register_vault(
    name: str,
    backend: FileBackend,
    *,
    options: dict[str, Any] | None = None,
) -> None:
    """Register a file backend with the global vault registry.

    Args:
        name: Unique identifier for the vault
        backend: FileBackend instance to register
        options: Optional dict of configuration options for this vault

    Raises:
        ValueError: If a vault with this name already exists

    Example:
        >>> from f9_file_backend import LocalFileBackend, register_vault
        >>> backend = LocalFileBackend(root="/data")
        >>> register_vault("primary", backend, options={"readonly": False})

    """
    _global_registry.register(name, backend, options=options)


def unregister_vault(name: str) -> None:
    """Unregister a vault from the global registry.

    Args:
        name: Name of the vault to unregister

    Raises:
        KeyError: If vault with this name doesn't exist

    Example:
        >>> from f9_file_backend import unregister_vault
        >>> unregister_vault("primary")

    """
    _global_registry.unregister(name)


def get_vault(name: str) -> FileBackend:
    """Retrieve a registered vault from the global registry.

    Args:
        name: Name of the vault to retrieve

    Returns:
        The FileBackend instance for this vault

    Raises:
        KeyError: If vault with this name doesn't exist

    Example:
        >>> from f9_file_backend import get_vault
        >>> backend = get_vault("primary")
        >>> backend.read("file.txt")

    """
    return _global_registry.get(name)


def list_vaults() -> list[str]:
    """List all registered vault names in the global registry.

    Returns:
        List of vault names

    Example:
        >>> from f9_file_backend import list_vaults
        >>> names = list_vaults()
        >>> print(names)
        ['primary', 'backup', 'cache']

    """
    return _global_registry.list()


def vault_exists(name: str) -> bool:
    """Check if a vault with the given name is registered.

    Args:
        name: Name of the vault to check

    Returns:
        True if vault exists, False otherwise

    Example:
        >>> from f9_file_backend import vault_exists
        >>> if vault_exists("primary"):
        ...     backend = get_vault("primary")

    """
    return _global_registry.exists(name)


def get_vault_options(name: str) -> dict[str, Any]:
    """Retrieve options associated with a vault in the global registry.

    Args:
        name: Name of the vault

    Returns:
        Dictionary of options for this vault

    Raises:
        KeyError: If vault with this name doesn't exist

    Example:
        >>> from f9_file_backend import get_vault_options
        >>> opts = get_vault_options("primary")
        >>> print(opts)
        {'readonly': False}

    """
    return _global_registry.get_options(name)


@contextmanager
def vault_context(name: str) -> Iterator[FileBackend]:
    """Context manager for working with a specific vault.

    Activates the named vault for the duration of the context block.

    Args:
        name: Name of the vault to activate

    Yields:
        The FileBackend instance for the active vault

    Raises:
        KeyError: If the named vault doesn't exist

    Example:
        >>> from f9_file_backend import register_vault, vault_context, LocalFileBackend
        >>> from pathlib import Path
        >>>
        >>> data = LocalFileBackend(root=Path("/data"))
        >>> cache = LocalFileBackend(root=Path("/cache"))
        >>>
        >>> register_vault("data", data)
        >>> register_vault("cache", cache)
        >>>
        >>> with vault_context("data"):
        ...     data.create("file.txt", data=b"Hello")
        ...
        >>> with vault_context("cache"):
        ...     cache.create("temp.txt", data=b"Temp")

    """
    ctx = VaultContext(_global_registry, name)
    with ctx as backend:
        yield backend
