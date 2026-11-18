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


def _saved(config_file) -> dict:
    return json.loads(config_file.read_text(encoding="utf-8"))


def _deleted(fake_keyring) -> set[str]:
    return {c.args[1] for c in fake_keyring.delete_password.call_args_list}


# forget_password ------------------------------------------------------------

def test_forget_password_removes_password_and_keeps_email(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com"}), encoding="utf-8")

    credentials.forget_password("user@example.com")

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")
    assert _saved(config_file) == {"email": "user@example.com"}


def test_forget_password_saves_the_login_email(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "saved@example.com"}), encoding="utf-8")

    credentials.forget_password("other@example.com")

    assert _deleted(fake_keyring) == {"saved@example.com", "other@example.com"}
    assert _saved(config_file)["email"] == "other@example.com"


def test_forget_password_without_config_creates_it_with_email(config_file, fake_keyring):
    credentials.forget_password("user@example.com")

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")
    assert _saved(config_file) == {"email": "user@example.com"}


def test_forget_password_keeps_other_config_keys(config_file, fake_keyring):
    config_file.write_text(json.dumps({"email": "user@example.com", "other": 1}), encoding="utf-8")

    credentials.forget_password("user@example.com")

    assert _saved(config_file) == {"email": "user@example.com", "other": 1}


def test_forget_password_ignores_missing_keyring_entry(config_file, fake_keyring):
    fake_keyring.delete_password.side_effect = keyring.errors.PasswordDeleteError("not found")

    credentials.forget_password("user@example.com")

    assert _saved(config_file) == {"email": "user@example.com"}


@pytest.mark.parametrize("content", ["{not json", "[]", "null", '"text"', "42"])
def test_forget_password_replaces_unreadable_config(config_file, fake_keyring, content):
    config_file.write_text(content, encoding="utf-8")

    credentials.forget_password("user@example.com")

    fake_keyring.delete_password.assert_called_once_with(credentials._KEYRING_SERVICE, "user@example.com")
    assert _saved(config_file) == {"email": "user@example.com"}


@pytest.mark.parametrize(
    "error", [keyring.errors.KeyringError("backend unavailable"), RuntimeError("access denied")]
)
def test_forget_password_ignores_keyring_errors(config_file, fake_keyring, error):
    config_file.write_text(json.dumps({"email": "saved@example.com"}), encoding="utf-8")
    fake_keyring.delete_password.side_effect = error

    credentials.forget_password("other@example.com")

    assert fake_keyring.delete_password.call_count == 2
    assert _saved(config_file)["email"] == "other@example.com"


def test_forget_password_ignores_config_write_errors(config_file, fake_keyring):
    with mock.patch.object(type(config_file), "write_text", side_effect=PermissionError("read-only")):
        credentials.forget_password("user@example.com")

    fake_keyring.delete_password.assert_called_once()


# remember_by_default --------------------------------------------------------

@pytest.mark.parametrize(
    ("email", "password", "expected"),
    [
        ("", "", True),                       # first use: nothing saved yet
        ("user@example.com", "secret", True),  # chose to remember
        ("user@example.com", "", False),       # chose to keep only the email
    ],
)
def test_remember_by_default_follows_saved_state(email, password, expected):
    assert credentials.remember_by_default(email, password) is expected
