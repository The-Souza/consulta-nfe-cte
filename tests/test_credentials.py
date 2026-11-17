import json
from unittest import mock

import keyring.errors
import pytest

import credentials


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(credentials, "_CONFIG", path)
    return path


@pytest.fixture
def fake_keyring():
    with mock.patch.object(credentials, "keyring") as fake:
        fake.errors = keyring.errors
        yield fake


def test_clear_removes_saved_password_and_email(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com"}), encoding="utf-8")

    credentials.clear()

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")
    assert "email" not in json.loads(config_file.read_text(encoding="utf-8"))


def test_clear_keeps_other_config_keys(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com", "other": 1}), encoding="utf-8")

    credentials.clear()

    assert json.loads(config_file.read_text(encoding="utf-8")) == {"other": 1}


def test_clear_without_saved_login_does_nothing(config_file, fake_keyring):
    credentials.clear()

    fake_keyring.delete_password.assert_not_called()
    assert not config_file.exists()


def test_clear_ignores_missing_keyring_entry(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com"}), encoding="utf-8")
    fake_keyring.delete_password.side_effect = keyring.errors.PasswordDeleteError("not found")

    credentials.clear()

    assert "email" not in json.loads(config_file.read_text(encoding="utf-8"))


def test_clear_with_corrupt_config_does_not_raise(config_file, fake_keyring):
    config_file.write_text("{not json", encoding="utf-8")

    credentials.clear()

    fake_keyring.delete_password.assert_not_called()
