#################################################################################
# The Institute for the Design of Advanced Energy Systems Integrated Platform
# Framework (IDAES IP) was produced under the DOE Institute for the
# Design of Advanced Energy Systems (IDAES).
#
# Copyright (c) 2018-2026 by the software owners: The Regents of the
# University of California, through Lawrence Berkeley National Laboratory,
# National Technology & Engineering Solutions of Sandia, LLC, Carnegie Mellon
# University, West Virginia University Research Corporation, et al.
# All rights reserved.  Please see the files COPYRIGHT.md and LICENSE.md
# for full copyright and license information.
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
            assert "stream_table.after_run" in runner.failed_actions

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
