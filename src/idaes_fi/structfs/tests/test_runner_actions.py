#################################################################################
# Process Optimization and Modeling for Minerals Sustainability (PrOMMiS) Copyright (c) 2023-2026
#
# “Process Optimization and Modeling for Minerals Sustainability (PrOMMiS)” was produced under the DOE
# Process Optimization and Modeling for Minerals Sustainability (“PrOMMiS”) initiative, and is
# copyrighted by the software owners: The Regents of the University of California, through Lawrence
# Berkeley National Laboratory, National Technology & Engineering Solutions of Sandia, LLC through
# Sandia National Laboratories, Carnegie Mellon University, University of Notre Dame, and West
# Virginia University Research Corporation.
#
# NOTICE. This Software was developed under funding from the U.S. Department of Energy and the
# U.S. Government consequently retains certain rights. As such, the U.S. Government has been granted
# for itself and others acting on its behalf a paid-up, nonexclusive, irrevocable, worldwide license
# in the Software to reproduce, distribute copies to the public, prepare derivative works, and perform
# publicly and display publicly, and to permit other to do so.
#
#################################################################################

# stdlib
import pprint
from types import SimpleNamespace

import pytest
from pytest import approx
from pyomo.opt.results.container import ScalarData

from .. import runner
from . import flash_flowsheet, hda_flowsheet
from ..actions import (
    MermaidDiagram,
    Timer,
    UnitDofChecker,
    StreamTable,
    CaptureSolverOutput,
    GetSolverResults,
    UnitModelReport,
)
from . import flash_flowsheet


@pytest.fixture
def set_tmp_db(tmp_path):
    dbpath = tmp_path / "test_runner_actions.db"
    flash_flowsheet.FS.set_report_db(dbfile=dbpath)
    return dbpath


class FakeRunner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def list_steps(self):
        return ["step1", "step2", "step3"]


class FakeScalar:
    def __init__(self):
        value = 1.0

    def get_value(self):
        return self.value


@pytest.mark.unit
def test_class_timer():
    runner = FakeRunner()
    timer = Timer(runner)

    # fake run
    timer.before_run()
    for step in runner.list_steps():
        timer.before_step(step)
        timer.after_step(step)
    timer.after_run()
    report = timer.report()

    # check report
    for step in runner.list_steps():
        assert report.timings[step] >= 0
    assert report.run_time >= 0


@pytest.mark.unit
def test_unit_dof_action_base(set_tmp_db):
    rn = flash_flowsheet.FS
    rn.reset()

    def check_step(name, data):
        print(f"check_step {name} data: {data}")
        assert "fs.flash" in data
        if name == "solve_initial":
            assert data["fs.flash"] == 0

    def check_run(step_dof, model_dof):
        assert model_dof == 0

    rn.add_action(
        "check_dof",
        UnitDofChecker,
        "fs",
        ["build", "solve_initial"],
        check_step,
        check_run,
    )

    rn.run_steps("build", "solve_initial")

    pprint.pprint(rn.get_action("check_dof").get_dof())


@pytest.mark.unit
def test_unit_dof_action_getters(set_tmp_db):
    rn = flash_flowsheet.FS
    rn.reset()

    aname = "check_dof"
    rn.add_action(
        aname,
        UnitDofChecker,
        "fs",
        ["build", "solve_initial"],
    )
    rn.run_steps()

    act = rn.get_action(aname)

    steps = act.steps()
    dofs = []
    for s in steps:
        step_dof = act.get_dof()[s]
        assert step_dof
        dofs.append(step_dof)
    assert dofs[0] != dofs[1]

    assert act.steps() == act.steps(only_with_data=True)


@pytest.mark.unit
def test_dof_report(set_tmp_db):
    rn = flash_flowsheet.FS
    rn.reset()
    check_steps = (
        "build",
        "set_operating_conditions",
        "initialize",
        "solve_initial",
    )
    rn.add_action("dof", UnitDofChecker, "fs", check_steps)
    rn.run_steps()
    report = rn.get_action("dof").report()
    assert report
    report_data = report.model_dump()
    assert report_data["model"] == 0  # model has DOF=0
    for step_name in check_steps:
        assert step_name in report_data["steps"]
        for unit, value in report_data["steps"][step_name].items():
            assert value >= 0  # DOF > 0 in all (step, unit)


@pytest.mark.unit
def test_mermaid_report(set_tmp_db):
    rn = flash_flowsheet.FS
    rn.reset()
    rn.add_action("diagram", MermaidDiagram)
    rn.run_steps()
    action = rn.get_action("diagram")
    action.set_model_root("fs")
    report = action.report()
    if action.diagram is None:
        print("Connectivity not installed")
        assert report == {}
    else:
        print("Connectivity IS installed")
        assert report.diagram != {}


@pytest.mark.unit
def test_stream_table_action_create(set_tmp_db):
    obj = StreamTable(flash_flowsheet.FS)
    assert obj


@pytest.mark.unit
def test_stream_table_action_report(tmp_path):
    rn = hda_flowsheet.FS  # need a flowsheet with Arcs
    rn.reset()
    rn.set_report_db(dbfile=tmp_path / "stream_table.db")
    rn._actions = {}  # no other actions
    rn.add_action("streamtable", StreamTable)
    rn.build()  # don't need to solve
    report = rn.get_action("streamtable").report()
    print(f"report: {report}")
    # perform some basic checks on the contents
    assert report
    assert report.index[0].startswith("flow_mol")
    assert report.units[0] == "mole / second"
    assert "s03" in report.columns
    assert len(report.columns) == len(report.data[0])
    assert len(report.data) == len(report.index)
    v1 = report.data[0][0]
    assert len(v1) == 2
    assert v1[0] > 0
    assert v1[0] < 1
    assert v1[1] == "unfixed"


@pytest.mark.unit
@pytest.mark.parametrize("failed", [False, True])
def test_capture_solver_output(failed):
    runner = FakeRunner()
    action = CaptureSolverOutput(runner=runner)
    # set a 'solve' step
    solve_step = runner.list_steps()[-1]
    action.solve_steps = [solve_step]

    # message that would be solver output
    message = "solver did something\n"

    # do a 'run'
    action.before_run()
    for step in runner.list_steps():
        action.before_step(step)
        if step == solve_step:
            print(message)
            if failed:
                action.step_failed(step, RuntimeError("whatevs"))
            else:
                action.after_step(step)
        else:
            action.after_step(step)
    action.after_run()

    # check report (captured output)
    rpt = action.report()
    if failed:
        assert solve_step not in rpt.output
    else:
        assert rpt.output[solve_step].rstrip() == message.rstrip()


@pytest.mark.unit
@pytest.mark.parametrize("failed", [False, True])
def test_get_solver_results(failed):
    runner = FakeRunner()
    action = GetSolverResults(runner=runner)
    # set a 'solve' step
    solve_step = runner.list_steps()[-1]
    action.solve_steps = [solve_step]

    # fake solve results
    has_val = ScalarData(2.34)
    added_value = ScalarData(1.23)
    added_dict = ScalarData({"foo": 1, "bar": 1.2, "baz": "hello"})
    if not failed:
        fake_results = {
            "value": added_value,
            "dvalue": added_dict,
            "Solver": [{"int": 1, "float": 0.1, "v": has_val, "s": "x"}],
            "Problem": [{"int": 1}, {"float": 0.1}, {"s": "x"}],
        }
    # do a 'run'
    action.before_run()
    for step in runner.list_steps():
        action.before_step(step)
        # don't do after_step if solve 'failed'
        if step != solve_step:
            action.after_step
        elif not failed:
            # set fake results
            setattr(runner, "results", fake_results)
            action.after_step(step)
    action.after_run()

    # check report
    rpt = action.report()
    if failed:
        assert rpt.results == []
    else:
        r = rpt.results[0]
        # Check that solver results were copied over
        for k, v in fake_results["Solver"][0].items():
            print(k)
            if k == "v":
                assert r.solver[k] == v.value
            else:
                assert r.solver[k] == v
        # Check that problem results were copied over
        for k, v in fake_results["Problem"][0].items():
            if k == "v":
                assert r.problem[k] == v.value
            else:
                assert r.solver[k] == v
        # Check that ScalarData values were copied over
        assert r.values["value"] == added_value.value
        assert r.values["dvalue"] == added_dict.value


@pytest.mark.integration
def test_unit_model_report(set_tmp_db):
    struct_fs = flash_flowsheet.FS
    struct_fs.build()
    runner = FakeRunner()
    runner.model = struct_fs.model
    rpt_action = UnitModelReport(runner)
    rpt_action.after_step("step1")

    rpt = rpt_action.report()
    assert rpt
    print(rpt.model_dump_json(indent=2))

    last = rpt.step_reports[rpt.last_step].reports
    # expect 2 components
    assert len(last) == 2
    for expected in ("fs.flash", "fs.flash.split"):
        assert expected in last


@pytest.mark.unit
def test_unit_model_report_bad_perf():
    action = UnitModelReport(FakeRunner())
    # this component will trigger both the missing-var-section in performance contents
    # and the attribute error for _get_stream_table_contents
    comp = SimpleNamespace(
        {
            "_get_performance_contents": lambda time_point: {"foo": {}},
        }
    )
    action._dof = False  # avoids calls involving `comp`
    print("> get report")
    action._get_report(comp)
