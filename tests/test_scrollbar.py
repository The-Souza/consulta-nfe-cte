import pytest

from ui.widgets.scrollbar import hide_when_idle, needs_scroll

BG = "#ffffff"


class FakeScrollbar:
    """Records what the wrapper asks of a CTkScrollbar."""

    def __init__(self):
        self.positions: list[tuple[str, str]] = []
        self.colors: list[tuple[str, str]] = []
        self.on_set = None  # simulates Tk calling the command again while set() redraws

    def set(self, first, last):
        self.positions.append((first, last))
        if self.on_set:
            nested, self.on_set = self.on_set, None
            nested()

    def get(self):
        first, last = self.positions[-1]
        return float(first), float(last)

    def configure(self, button_color, button_hover_color):
        self.colors.append((button_color, button_hover_color))

    def cget(self, name):
        assert name == "bg_color"
        return BG


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        ("0.0", "1.0", False),
        (0, 1, False),
        ("0.0", "0.5", True),
        ("0.25", "1.0", True),
        ("0.2", "0.7", True),
    ],
)
def test_needs_scroll(first, last, expected):
    assert needs_scroll(first, last) is expected


def test_handle_is_hidden_when_everything_fits():
    bar = FakeScrollbar()
    command = hide_when_idle(bar, "#aaa", "#bbb")

    command("0.0", "1.0")

    assert bar.positions == [("0.0", "1.0")]
    assert bar.colors == [(BG, BG)]


def test_handle_shows_again_when_there_is_something_to_scroll():
    bar = FakeScrollbar()
    command = hide_when_idle(bar, "#aaa", "#bbb")

    command("0.0", "1.0")
    command("0.0", "0.4")

    assert bar.colors == [(BG, BG), ("#aaa", "#bbb")]


def test_a_newer_position_arriving_during_set_wins():
    # Many rows added at once: while set(0, 1) redraws, Tk already reports the new position
    bar = FakeScrollbar()
    command = hide_when_idle(bar, "#aaa", "#bbb")
    bar.on_set = lambda: command("0.0", "0.25")

    command("0.0", "1.0")

    assert bar.colors == [("#aaa", "#bbb")]


def test_colors_change_only_when_the_state_flips():
    bar = FakeScrollbar()
    command = hide_when_idle(bar, "#aaa", "#bbb")

    for first, last in [("0.0", "0.4"), ("0.1", "0.5"), ("0.6", "1.0"), ("0.0", "1.0"), ("0.0", "1.0")]:
        command(first, last)

    assert bar.colors == [("#aaa", "#bbb"), (BG, BG)]
    assert len(bar.positions) == 5
