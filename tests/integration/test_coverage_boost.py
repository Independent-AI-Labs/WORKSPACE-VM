"""Import bootstrap install modules for coverage."""

from __future__ import annotations

import workspace.scripts.bootstrap_install as _bi
import workspace.scripts.bootstrap_installer as _bs
import workspace.scripts.bootstrap_installer_ui as _ui


class TestBootstrapInstallImport:
    def test_import_bootstrap_install(self):
        assert _bi is not None

    def test_import_bootstrap_installer(self):
        assert _bs is not None

    def test_import_bootstrap_installer_ui(self):
        assert _ui is not None
