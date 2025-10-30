"""Tests for vault registry and multi-instance management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from f9_file_backend import (
    LocalFileBackend,
    VaultContext,
    VaultRegistry,
    get_vault,
    get_vault_options,
    list_vaults,
    register_vault,
    unregister_vault,
    vault_context,
    vault_exists,
)


@pytest.fixture
def registry() -> VaultRegistry:
    """Provide a fresh VaultRegistry instance."""
    return VaultRegistry()


@pytest.fixture
def backend1(tmp_path: Path) -> LocalFileBackend:
    """Provide a backend instance for vault 1."""
    return LocalFileBackend(root=tmp_path / "vault1")


@pytest.fixture
def backend2(tmp_path: Path) -> LocalFileBackend:
    """Provide a backend instance for vault 2."""
    return LocalFileBackend(root=tmp_path / "vault2")


@pytest.fixture
def backend3(tmp_path: Path) -> LocalFileBackend:
    """Provide a backend instance for vault 3."""
    return LocalFileBackend(root=tmp_path / "vault3")


class TestVaultRegistry:
    """Tests for VaultRegistry class."""

    def test_register_and_get_vault(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
    ) -> None:
        """Ensure registering and retrieving a vault works correctly."""
        registry.register("primary", backend1)
        assert registry.get("primary") is backend1  # noqa: S101

    def test_register_with_options(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
    ) -> None:
        """Ensure options can be stored with a vault registration."""
        options = {"readonly": True, "cache_enabled": False}
        registry.register("primary", backend1, options=options)
        assert registry.get_options("primary") == options  # noqa: S101

    def test_register_duplicate_raises(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
        backend2: LocalFileBackend,
    ) -> None:
        """Ensure registering duplicate vault names raises ValueError."""
        registry.register("primary", backend1)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("primary", backend2)

    def test_unregister_vault(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
    ) -> None:
        """Ensure unregistering a vault removes it from the registry."""
        registry.register("primary", backend1)
        assert registry.exists("primary")  # noqa: S101
        registry.unregister("primary")
        assert not registry.exists("primary")  # noqa: S101

    def test_unregister_nonexistent_raises(self, registry: VaultRegistry) -> None:
        """Ensure unregistering a nonexistent vault raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            registry.unregister("nonexistent")

    def test_get_nonexistent_raises(self, registry: VaultRegistry) -> None:
        """Ensure getting a nonexistent vault raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent")

    def test_get_options_nonexistent_raises(self, registry: VaultRegistry) -> None:
        """Ensure getting options for nonexistent vault raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            registry.get_options("nonexistent")

    def test_list_vaults(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
        backend2: LocalFileBackend,
        backend3: LocalFileBackend,
    ) -> None:
        """Ensure listing vaults returns all registered names."""
        registry.register("vault1", backend1)
        registry.register("vault2", backend2)
        registry.register("vault3", backend3)
        names = registry.list()
        assert set(names) == {"vault1", "vault2", "vault3"}  # noqa: S101

    def test_list_empty_vaults(self, registry: VaultRegistry) -> None:
        """Ensure listing empty registry returns empty list."""
        assert registry.list() == []  # noqa: S101

    def test_exists_registered(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
    ) -> None:
        """Ensure exists() returns True for registered vaults."""
        registry.register("primary", backend1)
        assert registry.exists("primary")  # noqa: S101

    def test_exists_unregistered(self, registry: VaultRegistry) -> None:
        """Ensure exists() returns False for unregistered vaults."""
        assert not registry.exists("nonexistent")  # noqa: S101

    def test_get_options_empty_by_default(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
    ) -> None:
        """Ensure get_options() returns empty dict when no options provided."""
        registry.register("primary", backend1)
        assert registry.get_options("primary") == {}  # noqa: S101

    def test_get_options_returns_copy(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
    ) -> None:
        """Ensure get_options() returns a copy, not the original dict."""
        options = {"key": "value"}
        registry.register("primary", backend1, options=options)
        retrieved = registry.get_options("primary")
        retrieved["key"] = "modified"
        # Original in registry should be unchanged
        assert registry.get_options("primary")["key"] == "value"  # noqa: S101


class TestVaultContext:
    """Tests for VaultContext context manager."""

    def test_vault_context_enter_exit(
        self,
        registry: VaultRegistry,
        backend1: LocalFileBackend,
    ) -> None:
        """Ensure VaultContext properly enters and exits."""
        registry.register("primary", backend1)
        ctx = VaultContext(registry, "primary")
        with ctx as backend:
            assert backend is backend1  # noqa: S101

    def test_vault_context_nonexistent_raises(self, registry: VaultRegistry) -> None:
        """Ensure VaultContext raises KeyError for nonexistent vault."""
        ctx = VaultContext(registry, "nonexistent")
        with pytest.raises(KeyError, match="not found"):
            with ctx:
                pass


class TestGlobalRegistry:
    """Tests for module-level global registry functions."""

    def test_register_and_get_vault_global(
        self,
        tmp_path: Path,
    ) -> None:
        """Ensure register_vault and get_vault work with global registry."""
        backend = LocalFileBackend(root=tmp_path)
        try:
            register_vault("test_vault", backend)
            assert get_vault("test_vault") is backend  # noqa: S101
        finally:
            unregister_vault("test_vault")

    def test_register_vault_duplicate_raises(self, tmp_path: Path) -> None:
        """Ensure registering duplicate vault names raises ValueError."""
        backend1 = LocalFileBackend(root=tmp_path / "v1")
        backend2 = LocalFileBackend(root=tmp_path / "v2")
        try:
            register_vault("test_vault", backend1)
            with pytest.raises(ValueError, match="already registered"):
                register_vault("test_vault", backend2)
        finally:
            unregister_vault("test_vault")

    def test_register_vault_with_options(self, tmp_path: Path) -> None:
        """Ensure vault options are stored and retrieved correctly."""
        backend = LocalFileBackend(root=tmp_path)
        options = {"readonly": True}
        try:
            register_vault("test_vault", backend, options=options)
            assert get_vault_options("test_vault") == options  # noqa: S101
        finally:
            unregister_vault("test_vault")

    def test_unregister_vault_global(self, tmp_path: Path) -> None:
        """Ensure unregister_vault removes from global registry."""
        backend = LocalFileBackend(root=tmp_path)
        register_vault("test_vault", backend)
        unregister_vault("test_vault")
        assert not vault_exists("test_vault")  # noqa: S101

    def test_unregister_nonexistent_raises(self) -> None:
        """Ensure unregister_vault raises for nonexistent vault."""
        with pytest.raises(KeyError, match="not found"):
            unregister_vault("nonexistent")

    def test_list_vaults_global(self, tmp_path: Path) -> None:
        """Ensure list_vaults returns all registered vaults."""
        backend1 = LocalFileBackend(root=tmp_path / "v1")
        backend2 = LocalFileBackend(root=tmp_path / "v2")
        try:
            register_vault("vault1", backend1)
            register_vault("vault2", backend2)
            vaults = list_vaults()
            assert "vault1" in vaults  # noqa: S101
            assert "vault2" in vaults  # noqa: S101
        finally:
            unregister_vault("vault1")
            unregister_vault("vault2")

    def test_vault_exists_global(self, tmp_path: Path) -> None:
        """Ensure vault_exists checks global registry."""
        backend = LocalFileBackend(root=tmp_path)
        try:
            assert not vault_exists("test_vault")  # noqa: S101
            register_vault("test_vault", backend)
            assert vault_exists("test_vault")  # noqa: S101
        finally:
            unregister_vault("test_vault")

    def test_get_vault_nonexistent_raises(self) -> None:
        """Ensure get_vault raises for nonexistent vault."""
        with pytest.raises(KeyError, match="not found"):
            get_vault("nonexistent")

    def test_get_vault_options_nonexistent_raises(self) -> None:
        """Ensure get_vault_options raises for nonexistent vault."""
        with pytest.raises(KeyError, match="not found"):
            get_vault_options("nonexistent")

    def test_get_vault_options_empty(self, tmp_path: Path) -> None:
        """Ensure get_vault_options returns empty dict when no options."""
        backend = LocalFileBackend(root=tmp_path)
        try:
            register_vault("test_vault", backend)
            assert get_vault_options("test_vault") == {}  # noqa: S101
        finally:
            unregister_vault("test_vault")


class TestVaultContextManager:
    """Tests for vault_context() context manager function."""

    def test_vault_context_manager(self, tmp_path: Path) -> None:
        """Ensure vault_context manager works correctly."""
        backend = LocalFileBackend(root=tmp_path)
        try:
            register_vault("test_vault", backend)
            with vault_context("test_vault") as active_backend:
                assert active_backend is backend  # noqa: S101
        finally:
            unregister_vault("test_vault")

    def test_vault_context_manager_nonexistent_raises(self) -> None:
        """Ensure vault_context raises for nonexistent vault."""
        with pytest.raises(KeyError, match="not found"):
            with vault_context("nonexistent"):
                pass

    def test_vault_context_multiple_switches(self, tmp_path: Path) -> None:
        """Ensure switching between vaults works correctly."""
        backend1 = LocalFileBackend(root=tmp_path / "v1")
        backend2 = LocalFileBackend(root=tmp_path / "v2")
        try:
            register_vault("vault1", backend1)
            register_vault("vault2", backend2)

            with vault_context("vault1") as active:
                assert active is backend1  # noqa: S101

            with vault_context("vault2") as active:
                assert active is backend2  # noqa: S101

            with vault_context("vault1") as active:
                assert active is backend1  # noqa: S101
        finally:
            unregister_vault("vault1")
            unregister_vault("vault2")

    def test_vault_context_with_file_operations(self, tmp_path: Path) -> None:
        """Ensure vault_context allows file operations on active vault."""
        from f9_file_backend import NotFoundError

        backend1 = LocalFileBackend(root=tmp_path / "v1")
        backend2 = LocalFileBackend(root=tmp_path / "v2")
        try:
            register_vault("vault1", backend1)
            register_vault("vault2", backend2)

            with vault_context("vault1") as active:
                active.create("file1.txt", data=b"vault1 data")

            with vault_context("vault2") as active:
                active.create("file2.txt", data=b"vault2 data")

            # Verify files are in correct vaults
            assert backend1.read("file1.txt") == b"vault1 data"  # noqa: S101
            assert backend2.read("file2.txt") == b"vault2 data"  # noqa: S101

            # Verify cross-vault isolation
            with pytest.raises(NotFoundError):
                backend1.read("file2.txt")
            with pytest.raises(NotFoundError):
                backend2.read("file1.txt")
        finally:
            unregister_vault("vault1")
            unregister_vault("vault2")

    def test_vault_context_nested_same_vault(self, tmp_path: Path) -> None:
        """Ensure nested contexts for same vault work correctly."""
        backend = LocalFileBackend(root=tmp_path)
        try:
            register_vault("test_vault", backend)
            with vault_context("test_vault") as outer:
                outer.create("outer.txt", data=b"outer")
                with vault_context("test_vault") as inner:
                    assert inner is outer  # noqa: S101
                    inner.create("inner.txt", data=b"inner")
                # Both files should exist
                assert backend.read("outer.txt") == b"outer"  # noqa: S101
                assert backend.read("inner.txt") == b"inner"  # noqa: S101
        finally:
            unregister_vault("test_vault")

    def test_vault_context_nested_different_vaults(self, tmp_path: Path) -> None:
        """Ensure nested contexts for different vaults work correctly."""
        backend1 = LocalFileBackend(root=tmp_path / "v1")
        backend2 = LocalFileBackend(root=tmp_path / "v2")
        try:
            register_vault("vault1", backend1)
            register_vault("vault2", backend2)

            with vault_context("vault1") as v1:
                v1.create("v1_file.txt", data=b"vault1")
                with vault_context("vault2") as v2:
                    v2.create("v2_file.txt", data=b"vault2")
                # Back in vault1 context
                assert v1.read("v1_file.txt") == b"vault1"  # noqa: S101

            # Verify correct file isolation
            assert backend1.read("v1_file.txt") == b"vault1"  # noqa: S101
            assert backend2.read("v2_file.txt") == b"vault2"  # noqa: S101
        finally:
            unregister_vault("vault1")
            unregister_vault("vault2")


class TestRegistryMultiVaultScenarios:
    """Integration tests for multi-vault scenarios."""

    def test_independent_vault_operations(self, tmp_path: Path) -> None:
        """Ensure operations in different vaults don't interfere."""
        from f9_file_backend import NotFoundError

        data_backend = LocalFileBackend(root=tmp_path / "data")
        cache_backend = LocalFileBackend(root=tmp_path / "cache")
        try:
            register_vault("data", data_backend)
            register_vault("cache", cache_backend)

            # Write to data vault
            with vault_context("data") as vault:
                vault.create("config.json", data=b'{"key": "value"}')

            # Write to cache vault
            with vault_context("cache") as vault:
                vault.create("cache.bin", data=b"binary cache")

            # Verify separation
            assert (  # noqa: S101
                data_backend.read("config.json") == b'{"key": "value"}'
            )
            with pytest.raises(NotFoundError):
                data_backend.read("cache.bin")
            assert cache_backend.read("cache.bin") == b"binary cache"  # noqa: S101
            with pytest.raises(NotFoundError):
                cache_backend.read("config.json")
        finally:
            unregister_vault("data")
            unregister_vault("cache")

    def test_vault_metadata_tracking(self, tmp_path: Path) -> None:
        """Ensure vault metadata is tracked independently."""
        priority_primary = 1
        priority_backup = 2
        backend1 = LocalFileBackend(root=tmp_path / "v1")
        backend2 = LocalFileBackend(root=tmp_path / "v2")
        try:
            register_vault(
                "vault1",
                backend1,
                options={"purpose": "primary", "priority": priority_primary},
            )
            register_vault(
                "vault2",
                backend2,
                options={"purpose": "backup", "priority": priority_backup},
            )

            opts1 = get_vault_options("vault1")
            opts2 = get_vault_options("vault2")

            assert opts1["purpose"] == "primary"  # noqa: S101
            assert opts2["purpose"] == "backup"  # noqa: S101
            assert opts1["priority"] == priority_primary  # noqa: S101
            assert opts2["priority"] == priority_backup  # noqa: S101
        finally:
            unregister_vault("vault1")
            unregister_vault("vault2")
