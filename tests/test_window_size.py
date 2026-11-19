import pytest

from ui.window_size import TITLEBAR, WorkArea, fit_window

SEARCH = dict(width=1180, height=760, min_width=1000, min_height=640)
TASKBAR = 48


def area(width, height, scaling=1.0, x=0, y=0):
    """Work area of a screen with a bottom taskbar, in physical px."""
    return WorkArea(x=x, y=y, width=width, height=height - round(TASKBAR * scaling))


def test_large_screen_keeps_the_wanted_size_centered():
    fit = fit_window(area=area(1920, 1080), scaling=1.0, **SEARCH)

    assert (fit.width, fit.height, fit.min_width, fit.min_height) == (1180, 760, 1000, 640)
    assert fit.x == (1920 - 1180) // 2
    assert fit.y == (1080 - TASKBAR - (760 + TITLEBAR)) // 2


def test_short_laptop_screen_reduces_the_height_to_fit_above_the_taskbar():
    fit = fit_window(area=area(1366, 768), scaling=1.0, **SEARCH)

    assert fit.height == 768 - TASKBAR - TITLEBAR
    assert fit.width == 1180
    assert fit.y == 0


def test_windows_zoom_is_taken_into_account():
    fit = fit_window(area=area(1920, 1080, 1.5), scaling=1.5, **SEARCH)

    # 1080 physical px at 150% are 720 logical px.
    assert fit.height == 720 - TASKBAR - TITLEBAR
    assert fit.width == 1180
    assert fit.x == round((1920 - 1180 * 1.5) / 2)


def test_minimum_never_exceeds_the_screen():
    fit = fit_window(area=area(1024, 600, 1.25), scaling=1.25, **SEARCH)

    assert fit.width == int(1024 / 1.25)
    assert fit.height == int((600 - 60) / 1.25) - TITLEBAR
    assert (fit.min_width, fit.min_height) == (fit.width, fit.height)
    assert fit.x == 0


def test_position_is_relative_to_the_work_area():
    # Second monitor to the right, or a taskbar on the left/top.
    fit = fit_window(area=WorkArea(x=1920, y=40, width=1920, height=1040), scaling=1.0, **SEARCH)

    assert fit.x == 1920 + (1920 - 1180) // 2
    assert fit.y >= 40


@pytest.mark.parametrize("scaling", [1.0, 1.25, 1.5, 2.0])
@pytest.mark.parametrize("screen", [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)])
def test_window_always_fits_the_work_area(scaling, screen):
    work = area(*screen, scaling)

    fit = fit_window(area=work, scaling=scaling, **SEARCH)

    assert fit.x + fit.width * scaling <= work.x + work.width
    assert fit.y + (fit.height + TITLEBAR) * scaling <= work.y + work.height + 1
    assert fit.min_width <= fit.width and fit.min_height <= fit.height
