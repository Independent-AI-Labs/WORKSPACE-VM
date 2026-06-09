"""Unit tests for VM idempotency — no containers needed."""

from __future__ import annotations

import pytest

from workspace.cli.vm_manager import _config_sha256, _generate_password
from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7

pytestmark = pytest.mark.e2e

_PASSWORD_LEN = 32
_UNIQUENESS_COUNT = 50
_SHA256_HEX_LEN = 16


class TestPasswordIdempotency:
    def test_length(self) -> None:
        pw = _generate_password(_PASSWORD_LEN)
        assert len(pw) == _PASSWORD_LEN

    def test_alphanumeric(self) -> None:
        pw = _generate_password(64)
        assert pw.isalnum()

    def test_uniqueness(self) -> None:
        passwords = {
            _generate_password(_PASSWORD_LEN) for _ in range(_UNIQUENESS_COUNT)
        }
        assert len(passwords) == _UNIQUENESS_COUNT


class TestConfigSHA256Idempotency:
    def test_stable(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        digest = _config_sha256(cfg)
        assert len(digest) == _SHA256_HEX_LEN
        assert digest == _config_sha256(cfg)

    def test_different_configs_produce_different_hash(self) -> None:
        a = VMConfig.model_validate({"components": ["opencode"]})
        b = VMConfig.model_validate({"components": ["opencode", "traefik"]})
        assert _config_sha256(a) != _config_sha256(b)


class TestUUIDIdempotency:
    _UUID_LEN = 36

    def test_format(self) -> None:
        uid = uuid7()
        assert isinstance(uid, str)
        assert len(uid) == self._UUID_LEN

    def test_uniqueness(self) -> None:
        uuids = {uuid7() for _ in range(_UNIQUENESS_COUNT)}
        assert len(uuids) == _UNIQUENESS_COUNT
