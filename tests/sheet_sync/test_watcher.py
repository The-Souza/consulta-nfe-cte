from sheet_sync.watcher import ChangeWatcher

SAVED = 1000.0  # modification time of the sheet as last sent


def test_an_unchanged_sheet_stays_idle():
    watcher = ChangeWatcher(sent_mtime=SAVED)

    assert [watcher.tick(SAVED) for _ in range(3)] == ["idle", "idle", "idle"]


def test_a_change_is_confirmed_before_it_is_sent():
    watcher = ChangeWatcher(sent_mtime=SAVED)

    assert watcher.tick(1010.0) == "confirm"
    assert watcher.tick(1010.0) == "send"


def test_a_sheet_still_being_saved_keeps_waiting():
    watcher = ChangeWatcher(sent_mtime=SAVED)

    assert [watcher.tick(t) for t in (1010.0, 1012.0, 1013.0, 1013.0)] == ["confirm", "confirm", "confirm", "send"]


def test_there_is_no_second_send_without_a_new_change():
    watcher = ChangeWatcher(sent_mtime=SAVED)
    watcher.tick(1010.0)
    watcher.tick(1010.0)

    assert [watcher.tick(1010.0) for _ in range(3)] == ["idle", "idle", "idle"]


def test_a_new_change_after_a_send_is_sent_again():
    watcher = ChangeWatcher(sent_mtime=SAVED)
    watcher.tick(1010.0)
    watcher.tick(1010.0)

    assert [watcher.tick(1020.0), watcher.tick(1020.0)] == ["confirm", "send"]


def test_a_missing_file_stays_idle_without_losing_the_pending_change():
    # Excel replaces the file while saving, so it can be missing for a moment
    watcher = ChangeWatcher(sent_mtime=SAVED)
    watcher.tick(1010.0)

    assert [watcher.tick(None), watcher.tick(1010.0)] == ["idle", "send"]


def test_a_failed_send_is_tried_again_on_the_next_checks():
    watcher = ChangeWatcher(sent_mtime=SAVED)
    watcher.tick(1010.0)
    watcher.tick(1010.0)

    watcher.retry()

    assert [watcher.tick(1010.0), watcher.tick(1010.0)] == ["confirm", "send"]


def test_without_a_known_send_the_first_check_waits_for_confirmation():
    watcher = ChangeWatcher(sent_mtime=None)

    assert [watcher.tick(SAVED), watcher.tick(SAVED)] == ["confirm", "send"]
