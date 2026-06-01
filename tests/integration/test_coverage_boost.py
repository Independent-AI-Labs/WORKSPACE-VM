"""Import bootstrap install modules for coverage."""

from __future__ import annotations

import ami.scripts.bootstrap_install
import ami.scripts.bootstrap_installer
import ami.scripts.bootstrap_installer_ui


class TestBootstrapInstallImport:
    def test_import_bootstrap_install(self):
        assert ami.scripts.bootstrap_install is not None

    def test_import_bootstrap_installer(self):
        assert ami.scripts.bootstrap_installer is not None

    def test_import_bootstrap_installer_ui(self):
        assert ami.scripts.bootstrap_installer_ui is not None
