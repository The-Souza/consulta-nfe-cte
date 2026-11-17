import re

import config

SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def test_app_version_is_semver():
    assert SEMVER.fullmatch(config.APP_VERSION)
