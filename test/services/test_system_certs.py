"""证书包加载后补充系统根证书，且不关闭校验、不递归。"""

import ssl

import certifi
import pytest

import app  # noqa: F401  导入即安装补丁
from app.utils import system_certs


@pytest.fixture
def patched():
    system_certs.install()
    yield
    system_certs.install()


def test_package_import_installs_patch():
    assert (
        ssl.SSLContext.load_verify_locations
        is system_certs._load_verify_locations_with_system_store
    )


def test_cafile_context_also_loads_system_store_once(patched, monkeypatch):
    calls = []
    original = ssl.SSLContext.load_default_certs

    def record(self, purpose=ssl.Purpose.SERVER_AUTH):
        calls.append(purpose)
        return original(self, purpose)

    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", record)
    ctx = ssl.create_default_context(cafile=certifi.where())
    assert calls == [ssl.Purpose.SERVER_AUTH]
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert ctx.cert_store_stats()["x509_ca"] > 0


def test_system_store_failure_keeps_requested_bundle(patched, monkeypatch):
    def broken(self, purpose=ssl.Purpose.SERVER_AUTH):
        raise ssl.SSLError("no system store")

    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", broken)
    ctx = ssl.create_default_context(cafile=certifi.where())
    assert ctx.cert_store_stats()["x509_ca"] > 0


def test_env_opt_out_leaves_ssl_untouched(monkeypatch):
    system_certs.uninstall()
    try:
        monkeypatch.setenv(system_certs.DISABLE_ENV, "1")
        assert system_certs.install() is False
        assert (
            ssl.SSLContext.load_verify_locations
            is system_certs._original_load_verify_locations
        )
    finally:
        monkeypatch.delenv(system_certs.DISABLE_ENV)
        system_certs.install()
