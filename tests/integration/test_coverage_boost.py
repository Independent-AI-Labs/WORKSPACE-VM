"""Import bootstrap install modules for coverage."""

from __future__ import annotations

import workspace.cli.vpn_core as _vpn_core
import workspace.cli.vpn_netns as _vpn_netns
import workspace.scripts.bootstrap_install as _bi
import workspace.scripts.bootstrap_installer as _bs
import workspace.scripts.bootstrap_installer_ui as _ui
import workspace.types.vm as _vm
from workspace.types.vm import VMConfig


class TestBootstrapInstallImport:
    def test_import_bootstrap_install(self):
        assert _bi is not None

    def test_import_bootstrap_installer(self):
        assert _bs is not None

    def test_import_bootstrap_installer_ui(self):
        assert _ui is not None

    def test_import_vpn_modules(self):
        assert _vpn_core is not None
        assert _vpn_netns is not None
        assert _vm is not None

    def test_openvpn_vm_config_auto_component(self):
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {
                    "mode": "openvpn",
                    "vpn_type": "container",
                    "vpn_config": "/tmp/client.ovpn",
                },
            }
        )
        assert "openvpn" in cfg.components
