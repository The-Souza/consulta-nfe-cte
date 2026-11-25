import json
from pathlib import Path

import pytest

import local_config


@pytest.fixture
def config(tmp_path) -> Path:
    return tmp_path / "config.json"


class TestRead:
    def test_a_missing_file_is_empty(self, config):
        assert local_config.read(config) == {}

    @pytest.mark.parametrize("content", ["{not json", "", "[1, 2]", '"text"', "null"])
    def test_unreadable_or_non_object_content_is_empty(self, config, content):
        config.write_text(content, encoding="utf-8")
        assert local_config.read(config) == {}

    def test_reads_what_was_written(self, config):
        local_config.write({"email": "user@example.com", "work_folder": "C:/Canhotos"}, config)
        assert local_config.read(config) == {"email": "user@example.com", "work_folder": "C:/Canhotos"}

    def test_writes_utf8_json(self, config):
        local_config.write({"work_folder": "C:/Canhotos ação"}, config)
        assert json.loads(config.read_text(encoding="utf-8")) == {"work_folder": "C:/Canhotos ação"}

    def test_a_write_leaves_no_temporary_file(self, config):
        local_config.write({"a": 1}, config)
        assert [p.name for p in config.parent.iterdir()] == ["config.json"]


class TestWorkFolder:
    def test_none_until_chosen(self, config):
        assert local_config.work_folder(config) is None

    @pytest.mark.parametrize("value", ["", 3, None, ["C:/x"]])
    def test_an_invalid_value_counts_as_not_chosen(self, config, value):
        local_config.write({"work_folder": value}, config)
        assert local_config.work_folder(config) is None

    def test_saves_and_reads_the_folder(self, config, tmp_path):
        local_config.set_work_folder(tmp_path / "Canhotos", config)
        assert local_config.work_folder(config) == tmp_path / "Canhotos"

    def test_changing_the_folder_replaces_it(self, config, tmp_path):
        local_config.set_work_folder(tmp_path / "a", config)
        local_config.set_work_folder(tmp_path / "b", config)
        assert local_config.work_folder(config) == tmp_path / "b"

    def test_keeps_the_other_settings(self, config, tmp_path):
        local_config.write({"email": "user@example.com"}, config)
        local_config.set_work_folder(tmp_path / "Canhotos", config)
        assert local_config.read(config)["email"] == "user@example.com"

    def test_a_folder_that_no_longer_exists_is_still_returned(self, config, tmp_path):
        """The screen decides what to say when the saved folder is gone (for example, an unplugged drive)."""
        local_config.set_work_folder(tmp_path / "gone", config)
        assert local_config.work_folder(config) == tmp_path / "gone"
