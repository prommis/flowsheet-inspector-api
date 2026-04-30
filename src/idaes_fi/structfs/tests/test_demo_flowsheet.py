"""
Tests that utilize the demo_flowsheet_structured.py module in this
directory.
"""

# stdlib
from pathlib import Path

# third-party
import pytest

# package
from ..runner import ReportDB
from .demo_flowsheet_structured import FS
from .demo_flowsheet_fi_main import main
from ..common import ActionNames


@pytest.mark.unit
def test_fs_ok():
    assert FS is not None
    assert hasattr(FS, "run_steps")


@pytest.mark.integration
def test_fs_run_steps(tmp_path):

    dbpath = tmp_path / "test_fs_run_steps.db"
    FS.set_report_db(dbfile=dbpath)
    FS.run_steps()
    db = FS.get_report_db()
    assert Path(db._filename) == dbpath

    _check_report_ok(db)


@pytest.mark.integration
def test_fi_main(tmp_path):
    dbpath = tmp_path / "test_fs_run_steps.db"
    main(dbfile=dbpath)

    db = ReportDB(dbpath)
    assert Path(db._filename) == dbpath

    _check_report_ok(db)


def _check_report_ok(db):
    rpt = db.get_last_report()
    assert rpt
    actions = rpt["actions"]
    last_solve = actions[ActionNames.SOLVER_RESULTS.value]["results"][-1]["solver"]
    print(last_solve)
    assert last_solve["Status"] == "ok"
    assert last_solve["Termination condition"] == "optimal"

    last_row = db.get_last_meta()
    assert last_row
    print(f"last row: {last_row}")
    assert last_row["name"] == "Demo Flowsheet"
    assert bool(last_row["run_status"]) == True
