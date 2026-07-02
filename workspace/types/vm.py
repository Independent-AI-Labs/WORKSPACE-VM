"""VM configuration type for make vm."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class _VMConfigError(ValueError):
    """Base for VM configuration validation errors."""


class _SSHCustomRequiresFilesError(_VMConfigError):
    pass


class _ProxyRequiresURLError(_VMConfigError):
    pass


class _OpenVPNRequiresConfigError(_VMConfigError):
    pass


class _OpenVPNRequiresNetNSError(_VMConfigError):
    pass


class VMProviderConfig(BaseModel):
    """Provider configuration for the container's opencode.json."""

    name: str
    options: dict[str, str] = Field(default_factory=dict)


class VMCredentialsConfig(BaseModel):
    """API key provisioning mode."""

    mode: Literal["none", "clone", "api"] = "none"


class VMSSHConfig(BaseModel):
    """SSH key and host dotfile provisioning."""

    mode: Literal["none", "inherit", "custom"] = "none"
    files: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_files_for_custom(self) -> VMSSHConfig:
        if self.mode == "custom" and not self.files:
            raise _SSHCustomRequiresFilesError
        return self


class VMFileEntry(BaseModel):
    """A file or directory to pre-copy into the workspace volume."""

    src: str
    dst: str


class VMSyncEntry(BaseModel):
    """Directory-based sync rule for make vm sync."""

    dir: str
    strategy: Literal["merge", "overwrite", "skip"] = "merge"
    exclude: list[str] = Field(default_factory=list)


class VMResourcesConfig(BaseModel):
    """Container resource limits."""

    memory: str = "4g"
    cpus: int = 2
    pids_limit: int = 256


class VMNetworkConfig(BaseModel):
    """Network isolation configuration."""

    mode: Literal["none", "bridge", "host", "openvpn"] = "none"
    network_name: str = "ami-vm-net"
    policy: Literal["none", "internet", "proxy", "unrestricted"] = "unrestricted"
    proxy_url: str = ""
    whitelist: list[str] = Field(default_factory=list)
    vpn_type: Literal["container", "netns"] = "container"
    vpn_config: str = ""
    vpn_netns: str = ""

    @model_validator(mode="after")
    def _require_proxy_url_for_proxy_policy(self) -> VMNetworkConfig:
        if self.mode == "bridge" and self.policy == "proxy" and not self.proxy_url:
            raise _ProxyRequiresURLError
        return self

    @model_validator(mode="after")
    def _require_vpn_config_for_openvpn_container(self) -> VMNetworkConfig:
        if (
            self.mode == "openvpn"
            and self.vpn_type == "container"
            and not self.vpn_config
        ):
            raise _OpenVPNRequiresConfigError
        return self

    @model_validator(mode="after")
    def _require_vpn_netns_for_openvpn_netns(self) -> VMNetworkConfig:
        if self.mode == "openvpn" and self.vpn_type == "netns" and not self.vpn_netns:
            raise _OpenVPNRequiresNetNSError
        return self


class VMSecurityConfig(BaseModel):
    """Container security hardening."""

    purge_sudo: bool = True
    no_new_privileges: bool = True
    read_only_rootfs: bool = True
    cap_drop: list[str] = Field(default_factory=lambda: ["ALL"])
    cap_add: list[str] = Field(default_factory=list)


class VMConfig(BaseModel):
    """Complete VM configuration - passed to make vm <config.yaml>.

    Only 'components' is required. All other fields have sensible defaults.
    """

    components: list[str] = Field(...)
    extra_apt: list[str] = Field(default_factory=list)

    resources: VMResourcesConfig = Field(default_factory=VMResourcesConfig)
    provider: VMProviderConfig | None = None
    credentials: VMCredentialsConfig = Field(default_factory=VMCredentialsConfig)
    ssh: VMSSHConfig = Field(default_factory=VMSSHConfig)

    files: list[VMFileEntry] = Field(default_factory=list)
    sync: list[VMSyncEntry] = Field(default_factory=list)
    mounts: list[str] = Field(default_factory=list)

    network: VMNetworkConfig = Field(default_factory=VMNetworkConfig)
    web_ui: bool = True
    env: dict[str, str] = Field(default_factory=dict)
    security: VMSecurityConfig = Field(default_factory=VMSecurityConfig)
