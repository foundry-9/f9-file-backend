"""Tests for exception translation and compatibility module."""

from pathlib import Path

import pytest

from f9_file_backend.compat import (
    CompatibleFileBackend,
    translate_backend_exception,
    translate_exceptions,
    translate_method,
)
from f9_file_backend.interfaces import (
    AlreadyExistsError,
    FileBackendError,
    InvalidOperationError,
    NotFoundError,
)
from f9_file_backend.local import LocalFileBackend

SHA256_HEX_LENGTH = 64
EMPTY_GLOB_LENGTH = 2


class TestTranslateBackendException:
    """Test translate_backend_exception function."""

    def test_translate_notfound_error(self):  # noqa: S101
        """Test NotFoundError is translated to FileNotFoundError."""
        exc = NotFoundError(Path("missing.txt"))
        result = translate_backend_exception(exc)
        assert isinstance(result, FileNotFoundError)
        assert "missing.txt" in str(result)

    def test_translate_already_exists_error(self):
        """Test AlreadyExistsError is translated to FileExistsError."""
        exc = AlreadyExistsError(Path("existing.txt"))
        result = translate_backend_exception(exc)
        assert isinstance(result, FileExistsError)
        assert "existing.txt" in str(result)

    def test_translate_invalid_operation_read_directory(self):
        """Test InvalidOperationError reading directory becomes IsADirectoryError."""
        exc = InvalidOperationError.cannot_read_directory(Path("dir"))
        result = translate_backend_exception(exc)
        assert isinstance(result, IsADirectoryError)
        assert "dir" in str(result)

    def test_translate_invalid_operation_update_directory(self):
        """Test InvalidOperationError updating directory becomes IsADirectoryError."""
        exc = InvalidOperationError.cannot_update_directory(Path("dir"))
        result = translate_backend_exception(exc)
        assert isinstance(result, IsADirectoryError)

    def test_translate_invalid_operation_not_directory(self):
        """Test InvalidOperationError parent not directory becomes NotADirectoryError."""
        exc = InvalidOperationError(
            "Parent path is not a directory",
            path=Path("file/nested"),
        )
        result = translate_backend_exception(exc)
        assert isinstance(result, NotADirectoryError)

    def test_translate_invalid_operation_generic(self):
        """Test generic InvalidOperationError becomes OSError."""
        exc = InvalidOperationError("Some invalid operation", path=Path("file.txt"))
        result = translate_backend_exception(exc)
        assert isinstance(result, OSError)
        assert not isinstance(result, IsADirectoryError)

    def test_translate_generic_backend_error(self):
        """Test generic FileBackendError becomes OSError."""
        exc = FileBackendError("Something went wrong", path=Path("file.txt"))
        result = translate_backend_exception(exc)
        assert isinstance(result, OSError)
        assert "Something went wrong" in str(result)

    def test_translate_preserves_message(self):
        """Test that translation preserves the original exception message."""
        exc = NotFoundError(Path("my/important/file.txt"))
        result = translate_backend_exception(exc)
        assert "my/important/file.txt" in str(result)


class TestTranslateExceptionsContextManager:
    """Test translate_exceptions context manager."""

    def test_translate_exceptions_catches_notfound(self):
        """Test context manager translates NotFoundError."""
        with pytest.raises(FileNotFoundError):
            with translate_exceptions():
                raise NotFoundError(Path("missing.txt"))

    def test_translate_exceptions_catches_already_exists(self):
        """Test context manager translates AlreadyExistsError."""
        with pytest.raises(FileExistsError):
            with translate_exceptions():
                raise AlreadyExistsError(Path("existing.txt"))

    def test_translate_exceptions_catches_invalid_operation(self):
        """Test context manager translates InvalidOperationError."""
        with pytest.raises(IsADirectoryError):
            with translate_exceptions():
                raise InvalidOperationError.cannot_read_directory(Path("dir"))

    def test_translate_exceptions_passes_through_other_exceptions(self):
        """Test context manager doesn't catch non-FileBackendError exceptions."""
        error_message = "Some error"
        with pytest.raises(ValueError):
            with translate_exceptions():
                raise ValueError(error_message)  # noqa: TRY003

    def test_translate_exceptions_no_exception(self):
        """Test context manager doesn't affect normal execution."""
        value = None
        with translate_exceptions():
            value = 42
        assert value == 42

    def test_translate_exceptions_preserves_exception_chain(self):
        """Test that exception translation preserves the cause chain."""
        try:
            with translate_exceptions():
                raise NotFoundError(Path("file.txt"))
        except FileNotFoundError as e:
            assert isinstance(e.__cause__, NotFoundError)


class TestTranslateMethodDecorator:
    """Test translate_method decorator."""

    def test_translate_method_on_function_raising_notfound(self):
        """Test decorator translates NotFoundError in decorated function."""

        @translate_method
        def read_file():
            raise NotFoundError(Path("missing.txt"))

        with pytest.raises(FileNotFoundError):
            read_file()

    def test_translate_method_on_function_raising_already_exists(self):
        """Test decorator translates AlreadyExistsError in decorated function."""

        @translate_method
        def create_file():
            raise AlreadyExistsError(Path("existing.txt"))

        with pytest.raises(FileExistsError):
            create_file()

    def test_translate_method_preserves_return_value(self):
        """Test decorator preserves function return value."""

        @translate_method
        def get_value():
            return 42

        assert get_value() == 42

    def test_translate_method_preserves_arguments(self):
        """Test decorator preserves function arguments."""

        @translate_method
        def add(a, b):
            return a + b

        assert add(2, 3) == 5
        assert add(a=10, b=20) == 30

    def test_translate_method_on_method_with_self(self):
        """Test decorator works on instance methods."""

        class MyClass:
            def __init__(self):
                self.value = 0

            @translate_method
            def read_file(self):
                raise NotFoundError(Path("missing.txt"))

            @translate_method
            def get_value(self):
                return self.value

        obj = MyClass()
        with pytest.raises(FileNotFoundError):
            obj.read_file()
        assert obj.get_value() == 0

    def test_translate_method_preserves_function_name(self):
        """Test decorator preserves function metadata."""

        @translate_method
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestCompatibleFileBackend:
    """Test CompatibleFileBackend wrapper."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory for testing."""
        return tmp_path

    @pytest.fixture
    def base_backend(self, temp_dir):
        """Create a base LocalFileBackend."""
        return LocalFileBackend(root=temp_dir)

    @pytest.fixture
    def compat_backend(self, base_backend):
        """Create a CompatibleFileBackend wrapper."""
        return CompatibleFileBackend(base_backend)

    def test_create_and_read_file(self, compat_backend):
        """Test basic file operations through compatible backend."""
        compat_backend.create("test.txt", data=b"Hello, World!")
        content = compat_backend.read("test.txt")
        assert content == b"Hello, World!"

    def test_read_nonexistent_file_raises_file_not_found_error(self, compat_backend):
        """Test reading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            compat_backend.read("nonexistent.txt")

    def test_create_duplicate_file_raises_file_exists_error(self, compat_backend):
        """Test creating duplicate file raises FileExistsError."""
        compat_backend.create("file.txt", data=b"content")
        with pytest.raises(FileExistsError):
            compat_backend.create("file.txt", data=b"other")

    def test_read_directory_raises_is_directory_error(self, compat_backend):
        """Test reading a directory raises IsADirectoryError."""
        compat_backend.create("mydir/.keep", data=b"")
        with pytest.raises(IsADirectoryError):
            compat_backend.read("mydir")

    def test_update_directory_raises_is_directory_error(self, compat_backend):
        """Test updating a directory raises IsADirectoryError."""
        compat_backend.create("mydir/.keep", data=b"")
        with pytest.raises(IsADirectoryError):
            compat_backend.update("mydir", data=b"content")

    def test_glob_operations(self, compat_backend):
        """Test glob operations through compatible backend."""
        compat_backend.create("a.txt", data=b"a")
        compat_backend.create("b.txt", data=b"b")
        compat_backend.create("subdir/c.txt", data=b"c")

        files = compat_backend.glob("*.txt")
        assert len(files) == 2

    def test_delete_file(self, compat_backend):
        """Test delete operation through compatible backend."""
        compat_backend.create("file.txt", data=b"content")
        compat_backend.delete("file.txt")

        with pytest.raises(FileNotFoundError):
            compat_backend.read("file.txt")

    def test_directory_info(self, compat_backend):
        """Test info operation on directory through compatible backend."""
        compat_backend.create("newdir/.keep", data=b"")
        info = compat_backend.info("newdir")
        assert info.is_dir

    def test_info_file(self, compat_backend):
        """Test info operation on file through compatible backend."""
        compat_backend.create("file.txt", data=b"content")
        info = compat_backend.info("file.txt")
        assert info.size == 7
        assert not info.is_dir

    def test_info_nonexistent_raises_file_not_found_error(self, compat_backend):
        """Test info on nonexistent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            compat_backend.info("nonexistent.txt")

    def test_info_is_method_for_checking_existence(self, compat_backend):
        """Test that info can be used to check existence (raises on missing)."""
        compat_backend.create("file.txt", data=b"content")
        # This succeeds
        info = compat_backend.info("file.txt")
        assert info.path.name == "file.txt"
        # This raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            compat_backend.info("nonexistent.txt")

    def test_stream_read_nonexistent_raises_file_not_found_error(self, compat_backend):
        """Test stream_read on nonexistent file raises FileNotFoundError."""
        # Note: stream_read returns an iterator, so exception happens when consumed
        with pytest.raises(FileNotFoundError):
            # Need to trigger the NotFoundError by consuming the iterator
            stream = compat_backend.stream_read("nonexistent.txt")
            next(stream)

    def test_stream_write(self, compat_backend):
        """Test stream_write operation through compatible backend."""
        chunks = [b"Hello, ", b"World!"]
        compat_backend.stream_write("file.txt", chunk_source=iter(chunks))
        content = compat_backend.read("file.txt")
        assert content == b"Hello, World!"

    def test_stream_read(self, compat_backend):
        """Test stream_read operation through compatible backend."""
        compat_backend.create("file.txt", data=b"Hello, World!")
        chunks = list(compat_backend.stream_read("file.txt", chunk_size=5))
        assert b"".join(chunks) == b"Hello, World!"

    def test_repr(self, compat_backend):
        """Test string representation of compatible backend."""
        repr_str = repr(compat_backend)
        assert "CompatibleFileBackend" in repr_str
        assert "LocalFileBackend" in repr_str

    def test_attribute_delegation(self, compat_backend, base_backend):
        """Test that non-callable attributes are delegated."""
        # These should be accessible through delegation
        assert hasattr(compat_backend, "_backend")

    def test_checksum_operation(self, compat_backend):
        """Test checksum operation through compatible backend."""
        compat_backend.create("file.txt", data=b"content")
        checksum = compat_backend.checksum("file.txt", algorithm="sha256")
        assert isinstance(checksum, str)
        assert len(checksum) == SHA256_HEX_LENGTH

    def test_glob_operation(self, compat_backend):
        """Test glob operation through compatible backend."""
        compat_backend.create("file1.txt", data=b"a")
        compat_backend.create("file2.txt", data=b"b")
        compat_backend.create("file3.md", data=b"c")

        txt_files = compat_backend.glob("*.txt")
        expected_count = 2
        assert len(txt_files) == expected_count

    def test_multiple_operations_preserve_state(self, compat_backend):
        """Test that multiple operations preserve backend state."""
        compat_backend.create("file1.txt", data=b"content1")
        compat_backend.create("file2.txt", data=b"content2")

        content1 = compat_backend.read("file1.txt")
        assert content1 == b"content1"

        compat_backend.update("file2.txt", data=b"modified")
        content2 = compat_backend.read("file2.txt")
        assert content2 == b"modified"

    def test_exception_chaining_preserved(self, compat_backend):
        """Test that exception cause chain is preserved."""
        try:
            compat_backend.read("nonexistent.txt")
        except FileNotFoundError as e:
            assert isinstance(e.__cause__, NotFoundError)


class TestExceptionTranslationWithRealBackend:
    """Integration tests with real backend operations."""

    @pytest.fixture
    def compat_backend(self, tmp_path):
        """Create a compatible backend with real filesystem."""
        base = LocalFileBackend(root=tmp_path)
        return CompatibleFileBackend(base)

    def test_complete_workflow(self, compat_backend):
        """Test complete workflow with exception handling."""
        # Should succeed
        compat_backend.create("data.txt", data=b"test data")

        # Should fail with FileExistsError
        with pytest.raises(FileExistsError):
            compat_backend.create("data.txt", data=b"more data")

        # Should succeed
        content = compat_backend.read("data.txt")
        assert content == b"test data"

        # Should fail with FileNotFoundError
        with pytest.raises(FileNotFoundError):
            compat_backend.read("missing.txt")

        # Should succeed
        compat_backend.delete("data.txt")

        # Should fail with FileNotFoundError
        with pytest.raises(FileNotFoundError):
            compat_backend.read("data.txt")

    def test_directory_operations(self, compat_backend):
        """Test directory operation exception handling."""
        compat_backend.create("mydir/.keep", data=b"")

        # Should fail with IsADirectoryError
        with pytest.raises(IsADirectoryError):
            compat_backend.read("mydir")

        # Should succeed
        compat_backend.create("mydir/file.txt", data=b"content")

        # Should succeed
        content = compat_backend.read("mydir/file.txt")
        assert content == b"content"
