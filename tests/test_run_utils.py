from pathlib import Path

import pytest

from src.run_utils import prepare_run_directory


def test_run_directory_is_independent_and_tracks_latest(tmp_path: Path):
    output = prepare_run_directory(tmp_path / "outputs", "lesson_001")
    assert output.name == "lesson_001"
    assert (tmp_path / "outputs" / "latest.txt").read_text(encoding="ascii") == "lesson_001"
    (output / "result.txt").write_text("done", encoding="ascii")
    with pytest.raises(FileExistsError):
        prepare_run_directory(tmp_path / "outputs", "lesson_001")
