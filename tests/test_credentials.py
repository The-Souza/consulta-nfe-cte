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


def test_clear_removes_password_of_login_email_when_different_from_saved(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "saved@example.com"}), encoding="utf-8")

    credentials.clear("other@example.com")

    deleted = {c.args[1] for c in fake_keyring.delete_password.call_args_list}
    assert deleted == {"saved@example.com", "other@example.com"}


def test_clear_deletes_once_when_login_email_is_the_saved_one(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com"}), encoding="utf-8")

    credentials.clear("user@example.com")

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")


def test_clear_without_config_still_removes_login_password(config_file, fake_keyring):
    credentials.clear("user@example.com")

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")
    assert not config_file.exists()


def test_clear_with_corrupt_config_still_removes_login_password(config_file, fake_keyring):
    config_file.write_text("{not json", encoding="utf-8")

    credentials.clear("user@example.com")

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")


@pytest.mark.parametrize("content", ["[]", "null", '"text"', "42"])
def test_clear_with_non_object_json_does_not_raise(config_file, fake_keyring, content):
    config_file.write_text(content, encoding="utf-8")

    credentials.clear("user@example.com")

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")


def test_clear_ignores_keyring_backend_errors(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com"}), encoding="utf-8")
    fake_keyring.delete_password.side_effect = keyring.errors.KeyringError("backend unavailable")

    credentials.clear()

    assert "email" not in json.loads(config_file.read_text(encoding="utf-8"))


def test_clear_ignores_non_keyring_backend_errors(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com"}), encoding="utf-8")
    fake_keyring.delete_password.side_effect = RuntimeError("credential manager access denied")

    credentials.clear("other@example.com")

    assert fake_keyring.delete_password.call_count == 2
    assert "email" not in json.loads(config_file.read_text(encoding="utf-8"))


def test_clear_ignores_config_write_errors(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com"}), encoding="utf-8")

    with mock.patch.object(type(config_file), "write_text", side_effect=PermissionError("read-only")):
        credentials.clear()

    fake_keyring.delete_password.assert_called_once()
