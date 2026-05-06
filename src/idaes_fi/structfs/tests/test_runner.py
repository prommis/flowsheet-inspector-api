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
import pytest
from pydantic import BaseModel
from ..runner import Runner, Action
from .. import runner_actions

## -- setup --

simple = Runner(("notrun-1", "hello", "hello.dude", "world", "notrun-2"))


@pytest.fixture
def tmp_simple_db(tmp_path):
    dbpath = tmp_path / "test_runner_simple.db"
    simple.set_report_db(dbfile=dbpath)


@simple.step("hello")
def say_hello(context):
    context["greeting"] = "Hello"
    dude("yo")


@simple.substep("hello", "dude")
def dude(s):
    print(f"{s}! this is called from hello, not directly by runner")


@simple.step("world")
def say_to_world(context):
    msg = f"{context['greeting']}, World!"
    print(msg)
    context["greeting"] = msg


empty = Runner(("hi", "bye"))


@pytest.fixture
def tmp_empty_db(tmp_path):
    dbpath = tmp_path / "test_runner_empty.db"
    empty.set_report_db(dbfile=dbpath)


# -- end setup --


@pytest.mark.unit
def test_simple_run_all(tmp_simple_db):
    simple.run_steps()
    assert simple._context["greeting"] == "Hello, World!"


@pytest.mark.unit
def test_runner_actions():

    rn = Runner(("a step",))

    def do_nothing(context):
        print("do nothing")

    rn.add_action("nothing", do_nothing)
    rn.get_action("nothing")
    with pytest.raises(KeyError):
        rn.get_action("something")
    rn.remove_action("nothing")
    with pytest.raises(KeyError):
        rn.get_action("nothing")


@pytest.mark.unit
def test_run_steps_order(tmp_simple_db):
    with pytest.raises(ValueError):
        simple.run_steps("world", "hello")


@pytest.mark.unit
def test_run_steps_args(tmp_simple_db):
    simple.run_steps(first="hello")
    simple.run_steps(last="world")


@pytest.mark.unit
def test_run_1step(tmp_simple_db):
    simple.run_step("hello")


@pytest.mark.unit
def test_run_empty_steps():
    empty.run_steps()


@pytest.mark.unit
def test_run_bad_steps():
    with pytest.raises(KeyError):
        simple.run_steps("howdy", "pardner")

    with pytest.raises(KeyError):
        simple.run_step("notrun-1")


@pytest.mark.unit
def test_runner_context():
    simple.run_steps()
    assert simple["greeting"]


@pytest.mark.unit
def test_add_bad_step():
    with pytest.raises(KeyError):

        @simple.step("bad")
        def do_bad(ctx):
            return

    with pytest.raises(KeyError):

        @simple.substep("bad", "sub")
        def do_bad2(ctx):
            return

    # undefined step cannot have a substep

    with pytest.raises(ValueError):

        @simple.substep("notrun-1", "sub")
        def do_bad3(ctx):
            return


class RunActionExample(Action):
    def report(self) -> dict:
        return {"example": True}


class ReportModel(BaseModel):
    ok: bool = True


class ReportModelAction(Action):
    def report(self) -> ReportModel:
        return ReportModel()


class DelegatingAction(Action):
    def report(self):
        return Action.report(self)


@pytest.mark.unit
def test_runaction(tmp_simple_db):
    simple.reset()
    simple.add_action("foo", RunActionExample)
    simple.run_steps()
    assert simple.get_action("foo").report() == {"example": True}


@pytest.mark.unit
def test_run_steps_conflicting_args_and_endpoint_skip(tmp_path):
    calls = []
    rn = Runner(("a", "b", "c"))
    rn.set_report_db(dbfile=tmp_path / "test_runner_rn.sqlite")

    @rn.step("a")
    def step_a(ctx):
        calls.append("a")

    @rn.step("b")
    def step_b(ctx):
        calls.append("b")

    @rn.step("c")
    def step_c(ctx):
        calls.append("c")

    with pytest.raises(ValueError, match="Cannot specify both 'after' and 'first'"):
        rn.run_steps(first="a", after="a")

    with pytest.raises(ValueError, match="Cannot specify both 'before' and 'last'"):
        rn.run_steps(last="c", before="c")

    rn.run_steps(after="a", before="c")
    assert calls == ["b"]
    assert rn._last_run_steps == ["b"]


@pytest.mark.unit
def test_find_step_no_defined_steps_and_normalize_name(tmp_path):
    rn = Runner(("a", "b"))
    rn.set_report_db(dbfile=tmp_path / "test_runner_rn.sqlite")
    assert rn._find_step() == -1
    assert rn._find_step(reverse=True) == -1
    assert rn.normalize_name(None) == Runner.STEP_ANY


@pytest.mark.unit
def test_runner_report_with_model_and_dict_actions(tmp_path):
    rn = Runner(("run",))
    rn.set_report_db(dbfile=tmp_path / "test_runner_rn.sqlite")

    @rn.step("run")
    def do_run(ctx):
        ctx["ran"] = True

    rn.add_action("dict_action", RunActionExample)
    rn.add_action("model_action", ReportModelAction)

    rn.run_steps()
    report = rn.report()

    assert report["actions"]["dict_action"] == {"example": True}
    assert report["actions"]["model_action"] == {"ok": True}
    assert report["last_run"] == ["run"]


@pytest.mark.unit
def test_action_default_report_returns_none():
    action = DelegatingAction(simple)
    assert action.report() is None
