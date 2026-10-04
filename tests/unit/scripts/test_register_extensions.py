"""Unit tests for register_extensions.py."""

import stat
from pathlib import Path

from workspace.scripts.register_extensions import (
    create_wrapper,
    fix_stale_shebang,
)


class TestCreateWrapper:
    """Tests for create_wrapper function."""

    def test_creates_executable_wrapper(self, tmp_path):
        """Test wrapper is created with exec permission."""
        wrapper = tmp_path / "test-cmd"
        create_wrapper(wrapper, Path("/fake/root"), "scripts/main.py")
        assert wrapper.exists()
        assert wrapper.stat().st_mode & stat.S_IXUSR
        content = wrapper.read_text()
        assert "run" in content
        assert "scripts/main.py" in content


class TestFixStaleShebang:
    """Tests for fix_stale_shebang function."""

    def test_skips_nonexistent_file(self, tmp_path):
        """Test does nothing for missing file."""
        fix_stale_shebang(tmp_path / "nope", tmp_path)

    def test_fixes_stale_python_shebang(self, tmp_path):
        """Test rewrites stale Python shebang."""
        binary = tmp_path / "script"
        # Use a shebang path that does not exist on disk
        binary.write_text("#!/nonexistent/xxxxx/python3\nprint('hi')\n")
        fix_stale_shebang(binary, tmp_path)
        content = binary.read_text()
        assert "/nonexistent" not in content
        assert ".venv/bin/python3" in content

    def test_fixes_inline_python_paths(self, tmp_path):
        """Test rewrites inline interpreter paths in wrappers."""
        binary = tmp_path / "wrapper"
        binary.write_text('#!/usr/bin/env bash\nexec "/old/path/python3" "$@"\n')
        fix_stale_shebang(binary, tmp_path)
        content = binary.read_text()
        assert ".venv/bin/python" in content

    def test_preserves_variable_inline_python_path(self, tmp_path):
        """Regression: a variable-based interpreter path is not hardcoded."""
        binary = tmp_path / "wrapper"
        original = '#!/usr/bin/env bash\nexec "$VENV_DIR/bin/python" "$@"\n'
        binary.write_text(original)
        fix_stale_shebang(binary, tmp_path)
        assert binary.read_text() == original

    def test_preserves_existing_inline_python_path(self, tmp_path):
        """An inline path that resolves is left untouched."""
        interp = tmp_path / "elsewhere" / "python3"
        interp.parent.mkdir(parents=True)
        interp.write_text("")
        binary = tmp_path / "wrapper"
        original = f'#!/usr/bin/env bash\nexec "{interp}" "$@"\n'
        binary.write_text(original)
        fix_stale_shebang(binary, tmp_path)
        assert binary.read_text() == original

    def test_skips_binary_file(self, tmp_path):
        """Test skips non-text files without raising."""
        binary = tmp_path / "binary"
        binary.write_bytes(b"\x00\x01\x02\xff")
        fix_stale_shebang(binary, tmp_path)

    def test_skips_no_python_in_shebang(self, tmp_path):
        """Test leaves non-python shebangs alone."""
        script = tmp_path / "bash_script"
        script.write_text("#!/usr/bin/env bash\necho hi\n")
        fix_stale_shebang(script, tmp_path)
        assert script.read_text().startswith("#!/usr/bin/env bash")
