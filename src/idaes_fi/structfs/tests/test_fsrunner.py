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
from pathlib import Path
from types import SimpleNamespace

import pytest
from pyomo.environ import ConcreteModel, SolverStatus, TerminationCondition, Var
from idaes.core import FlowsheetBlock
from .. import fsrunner
from ..fsrunner import (
    FlowsheetRunner,
    BaseFlowsheetRunner,
    Context,
    run_flowsheet,
)
from ..runner import Runner
from ..common import ActionNames, Steps

from .flash_flowsheet import FS as flash_fs
import idaes_fi.structfs as structfs
from pyomo.environ import assert_optimal_termination


def set_tmp_db(fs, p):
    dbpath = p / "test_fsrunner.db"
    fs.set_report_db(dbfile=dbpath)


@pytest.mark.unit
def test_context_accessors():
    model = ConcreteModel()
    solver = SimpleNamespace()
    ctx = Context(model=model, solver=solver, tee=False)

    assert ctx.model is model
    assert ctx.solver is solver
    assert ctx.tee is False
    assert ctx.results == {}
    assert "results" not in ctx

    new_model = ConcreteModel()
    new_solver = SimpleNamespace()
    results = SimpleNamespace()
    ctx.model = new_model
    ctx.solver = new_solver
    ctx.results = results

    assert ctx["model"] is new_model
    assert ctx["solver"] is new_solver
    assert ctx["results"] is results
    assert ctx.model is new_model
    assert ctx.solver is new_solver
    assert ctx.results is results


@pytest.mark.unit
def test_context_solve_uses_configured_solver():
    model = ConcreteModel()
    results = SimpleNamespace()
    solver = SimpleNamespace(calls=[])

    def solve(model_arg, tee):
        solver.calls.append((model_arg, tee))
        return results

    solver.solve = solve
    ctx = Context(model=model, solver=solver, tee=True)

    ctx.solve()

    assert len(solver.calls) == 1
    assert solver.calls[0][0] is model
    assert solver.calls[0][1] is True
    assert ctx.results is results


@pytest.mark.unit
def test_context_solve_builds_default_solver(monkeypatch):
    model = ConcreteModel()
    results = SimpleNamespace()
    solver = SimpleNamespace(calls=[])
    created = []

    def solve(model_arg, tee):
        solver.calls.append((model_arg, tee))
        return results

    def solver_factory(name):
        created.append(name)
        solver.solve = solve
        return solver

    monkeypatch.setattr(fsrunner, "SolverFactory", solver_factory)
    ctx = Context(model=model, solver=None, tee=False)

    ctx.solve()

    assert created == [fsrunner.DEFAULT_SOLVER_NAME]
    assert ctx.solver is solver
    assert len(solver.calls) == 1
    assert solver.calls[0][0] is model
    assert solver.calls[0][1] is False
    assert ctx.results is results


@pytest.mark.unit
def test_annotation(tmp_path):
    set_tmp_db(flash_fs, tmp_path)

    runner = flash_fs
    runner.run_steps(Steps.build)

    ann = runner.annotate_var  # alias
    flash = runner.model.fs.flash  # alias
    category = "flash"
    kw = {"input_category": category, "output_category": category}

    ann(
        flash.inlet.flow_mol,
        key="fs.flash.inlet.flow_mol",
        title="Inlet molar flow",
        desc="Flash inlet molar flow rate",
        **kw,
    ).fix(1)
    ann(flash.inlet.temperature, units="Centipedes", **kw).fix(368)
    ann(flash.inlet.pressure, **kw).fix(101325)
    ann(flash.inlet.mole_frac_comp[0, "benzene"], **kw).fix(0.5)
    ann(flash.inlet.mole_frac_comp[0, "toluene"], **kw).fix(0.5)
    ann(flash.heat_duty, **kw).fix(0)
    ann(flash.deltaP, is_input=False, **kw).fix(0)
    with pytest.raises(ValueError):
        # won't even look at variable before failing
        ann(None, is_input=False, is_output=False)

    ann = runner.annotated_vars
    print("-" * 40)
    print(ann)
    print("-" * 40)
    assert ann["fs.flash.inlet.flow_mol"]["title"] == "Inlet molar flow"
    assert (
        ann["fs.flash.inlet.flow_mol"]["description"] == "Flash inlet molar flow rate"
    )
    assert ann["fs.flash.inlet.flow_mol"]["input_category"] == category
    assert ann["fs.flash.inlet.flow_mol"]["output_category"] == category
    assert runner.model.fs.flash.inlet.flow_mol[0].value == 1
    assert ann["fs.flash._temperature_inlet_ref"]["units"] == "Centipedes"
    assert ann["fs.flash.deltaP"]["is_input"] == False


def test_base_flowsheet_runner():
    runner = BaseFlowsheetRunner()
    # build step is 1st step by default
    assert runner.build_step == BaseFlowsheetRunner.STEPS[0]

    solver = SimpleNamespace()
    tee = False
    solver_options = {"options": 1}
    runner = BaseFlowsheetRunner(solver=solver, tee=tee, solver_options=solver_options)

    for target_kw, ok in (({}, True), ({"foo": 1}, False)):
        if ok:
            runner = BaseFlowsheetRunner(**target_kw)
        else:
            with pytest.raises(KeyError):
                runner = BaseFlowsheetRunner(**target_kw)


def test_base_flowsheet_runner_set_solve_steps():
    # whether the "solve_steps"
    class SolveStepAction:
        def __init__(self, runner):
            self.runner = runner
            self.solve_steps = ["solve_initial"]

    class OtherAction:
        def __init__(self, runner):
            self.runner = runner

    runner = BaseFlowsheetRunner()
    first = runner.add_action("first", SolveStepAction)
    second = runner.add_action("second", SolveStepAction)
    other = runner.add_action("other", OtherAction)
    solve_steps = ["custom_solve", "custom_optimize"]

    runner.set_solve_steps(solve_steps)

    assert first.solve_steps == solve_steps
    assert second.solve_steps == solve_steps
    assert not hasattr(other, "solve_steps")


@pytest.mark.parametrize("runnerclass", [BaseFlowsheetRunner, FlowsheetRunner])
def test_flowsheet_runner_run_steps(runnerclass):
    calls = []
    solver = SimpleNamespace(options={})
    s_build, s_init, s_solve = Steps.build, Steps.initialize, Steps.solve_initial
    runner = runnerclass(
        solver=solver,
        tee=False,
        steps=(s_build, s_init, s_solve),
    )

    @runner.step(s_build)
    def build(ctx):
        calls.append(s_build)
        assert isinstance(ctx.model, ConcreteModel)
        assert isinstance(ctx.model.fs, FlowsheetBlock)
        assert ctx.solver is solver
        assert ctx.tee is False
        ctx.model.fs.marker = Var(initialize=1)

    @runner.step(s_init)
    def initialize(ctx):
        calls.append(s_init)
        assert isinstance(ctx.model, ConcreteModel)

    @runner.step(s_solve)
    def solve_initial(ctx):
        calls.append(s_solve)

    def extra_checks(runner):
        if runnerclass is FlowsheetRunner:
            assert runner.failed
            assert len(runner.failed_actions) == 1  # stop after 1 failure

    runner.run_steps(save_report=False)
    extra_checks(runner)

    initial_model = runner.model
    assert calls == [s_build, s_init, s_solve]
    assert initial_model.fs.marker.value == 1

    calls.clear()
    runner.run_steps(first=s_init, last=s_solve, save_report=False)
    extra_checks(runner)

    assert calls == [s_init, s_solve]
    assert runner.model is initial_model

    calls.clear()
    runner.run_steps(first=s_build, last=s_build, save_report=False)
    extra_checks(runner)

    rebuilt_model = runner.model
    assert calls == [s_build]
    assert rebuilt_model is not initial_model
    assert hasattr(rebuilt_model.fs, "marker")

    calls.clear()
    runner.run_steps(after=s_build, before=s_solve, save_report=False)

    # call some syntactic sugar methods
    if runnerclass is FlowsheetRunner:
        for sugar in ("build", "solve_initial"):
            calls.clear()
            getattr(runner, sugar)()
        runner.show_diagram()


@pytest.fixture
def empty_fsrunner():
    s_build, s_init, s_solve = Steps.build, Steps.initialize, Steps.solve_initial
    runner = FlowsheetRunner(
        steps=(s_build, s_init, s_solve),
    )

    @runner.step(s_build)
    def build(ctx):
        ctx.model = ConcreteModel()

    @runner.step(s_init)
    def initialize(ctx):
        print("initialize")

    @runner.step(s_solve)
    def solve_initial(ctx):
        print("solve")

    return runner


@pytest.fixture
def empty_fsrunner_build_only():
    runner = FlowsheetRunner(steps=(Steps.build,))

    @runner.step(Steps.build)
    def build(ctx):
        ctx.model = ConcreteModel()

    return runner


def test_with_no_connectivity(empty_fsrunner):
    save, fsrunner.Connectivity = fsrunner.Connectivity, None
    empty_fsrunner.show_diagram()
    fsrunner.Connectivity = save


@pytest.mark.parametrize(
    "solver_name,solver_opts", [("ipopt", {}), ("ipopt", {"tee": True})]
)
def test_set_solver_baseflowsheetrunner_init(solver_name, solver_opts):
    runner = BaseFlowsheetRunner(solver=solver_name, solver_options=solver_opts)
    runner.run_steps()


def test_no_solver_baseflowsheetrunner(empty_fsrunner_build_only):
    runner = empty_fsrunner_build_only

    runner.run_steps()


## Testing the run_flowsheet() function


class DummyFlowsheet:
    def __init__(self):
        self.model = object()
        self.report_target = None
        self.report_db_file = None
        self.run_steps_calls = []

    def set_report_target(self, **target_kw):
        self.report_target = target_kw

    def set_report_db(self, dbfile):
        self.report_db_file = dbfile

    def run_steps(self, **step_kw):
        self.run_steps_calls.append(step_kw)


@pytest.fixture
def fake_module_loader(monkeypatch):
    target_kw = {
        "module": "fake.module",
        "filename": "fake.py",
        "filedir": "/fake",
    }
    loaded = []

    def set_module(module):
        def load_module(module_or_path):
            loaded.append(module_or_path)
            return module

        monkeypatch.setattr(fsrunner, "load_module", load_module)
        monkeypatch.setattr(fsrunner, "_module_target", lambda mod: target_kw.copy())
        return loaded

    return set_module


def test_run_flowsheet_runs_global_runner(fake_module_loader, tmp_path):
    runner = DummyFlowsheet()
    module = SimpleNamespace(FS=runner)
    loaded = fake_module_loader(module)
    dbfile = tmp_path / "reports.db"
    step_kw = {"last": Steps.build}

    fs = run_flowsheet("fake.module", step_kw=step_kw, report_db_file=dbfile)

    assert fs is runner
    assert loaded == ["fake.module"]
    assert runner.report_target == {
        "module": "fake.module",
        "filename": "fake.py",
        "filedir": "/fake",
    }
    assert runner.report_db_file == dbfile
    assert runner.run_steps_calls == [step_kw]


def test_run_flowsheet_selects_named_global_runner(fake_module_loader):
    default = DummyFlowsheet()
    selected = DummyFlowsheet()
    module = SimpleNamespace(FS=default, FS2=selected)
    fake_module_loader(module)

    fs = run_flowsheet("fake.module", fs_attr="FS2")

    assert fs is selected
    assert default.run_steps_calls == []
    assert selected.run_steps_calls == [{}]


def test_run_flowsheet_raises_for_missing_named_runner(fake_module_loader):
    runner = DummyFlowsheet()
    module = SimpleNamespace(FS=runner)
    fake_module_loader(module)

    with pytest.raises(ValueError, match="specified name 'missing'"):
        run_flowsheet("fake.module", fs_attr="missing")

    assert runner.run_steps_calls == []


def test_run_flowsheet_runs_wrapped_main(fake_module_loader):
    runner = DummyFlowsheet()
    calls = []

    def fi_wrapper(**kwargs):
        calls.append(kwargs)
        return object(), {fsrunner.RESULT_FLOWSHEET_KEY: runner}

    module = SimpleNamespace(fi_main=object(), main=fi_wrapper)
    fake_module_loader(module)

    fs = run_flowsheet("fake.module", user_arg=1)

    assert fs is runner
    assert calls == [{"user_arg": 1}]
    assert runner.run_steps_calls == []


def test_run_flowsheet_raises_when_no_flowsheet_found(fake_module_loader):
    module = SimpleNamespace()
    fake_module_loader(module)

    with pytest.raises(ValueError, match="Could not find either"):
        run_flowsheet("fake.module")


def test_run_flowsheet_module_target():
    # bad input
    with pytest.raises(TypeError):
        run_flowsheet(module_or_path={})

    # no wrapped flowsheet
    with pytest.raises(ValueError):
        run_flowsheet(module_or_path="idaes_fi.structfs.tests.demo_flowsheet")

    run_flowsheet(module_or_path="idaes_fi.structfs.tests.demo_flowsheet_structured")


@pytest.mark.parametrize(
    "args,opts,ok,bad",
    [
        (["f00b4r"], {"foo": "bar"}, False, True),
        (["f00b4r"], {}, False, False),  # cannot load
        (["f00b4r", "-v"], {}, False, False),  # cannot load + verbose
        (["f00b4r", "-v", "-v"], {}, False, False),  # cannot load + 2 * verbose
        (["f00b4r", "-q"], {}, False, False),  # cannot load + quiet
        (["f00b4r", "-q", "-v"], {}, False, False),  # cannot load + quiet + verbose
        # demo, no args
        (["idaes_fi.structfs.tests.demo_flowsheet_fi_main"], {}, True, False),
        # demo + verbose
        (["idaes_fi.structfs.tests.demo_flowsheet_fi_main", "-v"], {}, True, False),
        # demo + 2 * verbose
        (
            ["idaes_fi.structfs.tests.demo_flowsheet_fi_main", "-v", "-v"],
            {},
            True,
            False,
        ),
        # demo + quiet
        (["idaes_fi.structfs.tests.demo_flowsheet_fi_main", "-q"], {}, True, False),
        # demo + specific last step
        (
            ["idaes_fi.structfs.tests.demo_flowsheet_structured"],
            {"last": Steps.solve_initial},
            True,
            False,
        ),
        # demo-multi
        (
            ["idaes_fi.structfs.tests.demo_flowsheet_structured_multi"],
            {},
            True,
            False,
        ),
        # demo-multi + FS2
        (
            ["idaes_fi.structfs.tests.demo_flowsheet_structured_multi"],
            {"attr": "FS2"},
            True,
            False,
        ),
        # demo-multi + bad attr
        (
            ["idaes_fi.structfs.tests.demo_flowsheet_structured_multi"],
            {"attr": "baaaa"},
            False,
            False,
        ),
    ],
)
def test_fsrunner_main(args, opts, ok, bad, tmp_path):
    db_file = tmp_path / "test_fsrunner_main.db"
    cmd = args.copy()
    for k, v in opts.items():
        cmd.append(f"--{k}")
        cmd.append(f"{v}")
    cmd.append("--db")
    cmd.append(str(db_file))
    print(f"Run command: {cmd}")
    if bad:  # bad args = exit
        with pytest.raises(SystemExit):
            fsrunner.main(cmd)
    else:
        retcode = fsrunner.main(cmd)
        if ok:
            assert retcode == 0
        else:
            assert retcode != 0


def test_fsrunner_main_no_default_report_db(monkeypatch, capsys):
    class ValueErrorFilename:
        @property
        def filename(self):
            raise ValueError()

    class FakeRunner:

        @classmethod
        def nonexist_report_db(cls, create=True):
            return ValueErrorFilename()

    monkeypatch.setattr(Runner, "get_default_report_db", FakeRunner.nonexist_report_db)

    cmd = ["-h"]
    try:
        fsrunner.main(cmd)
    except SystemExit:
        pass

    captured = capsys.readouterr()
    assert "default=?unknown?" in captured.out


def test__find_wrapped_main():
    def fi_wrapper(*args, **kwargs):
        return

    fake_module = SimpleNamespace(
        fi_main=True, main1=fi_wrapper, main2=fi_wrapper, __name__="fake_module"
    )

    # multiple main()
    with pytest.raises(ValueError):
        fsrunner._find_wrapped_main(fake_module)

    # no main()
    fake_module = SimpleNamespace(fi_main=True, __name__="fake_module")
    result = fsrunner._find_wrapped_main(fake_module)
    assert result is None
