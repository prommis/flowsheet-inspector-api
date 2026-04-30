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
    _find_global_flowsheet,
    _find_wrapped_main,
    Context,
    run_flowsheet,
)
from ..common import ActionNames

from .flash_flowsheet import FS as flash_fs
import idaes_fi.structfs as structfs
from idaes.core.util.doctesting import Docstring
from pyomo.environ import assert_optimal_termination


def set_tmp_db(fs, p):
    dbpath = p / "test_fsrunner.db"
    fs.set_report_db(dbfile=dbpath)


@pytest.mark.unit
def test_annotation(tmp_path):
    set_tmp_db(flash_fs, tmp_path)

    runner = flash_fs
    runner.run_steps("build")
    print(runner.timings.history)

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


#####
# Test the code blocks in the structfs/__init__.py
#####

# pacify linters:
sfi_before_build_model = sfi_before_set_operating_conditions = sfi_before_init_model = (
    sfi_before_solve
) = lambda x: None
SolverStatus, FS = None, None

#  load the functions from the docstring
_ds1 = Docstring(structfs.__doc__)
exec(_ds1.code("before", func_prefix="sfi_before_"))
exec(_ds1.code("after", func_prefix="sfi_after_"))


@pytest.mark.unit
def test_sfi_before():
    m = sfi_before_build_model()
    sfi_before_set_operating_conditions(m)
    sfi_before_init_model(m)
    result = sfi_before_solve(m)
    assert result.solver.status == SolverStatus.ok


@pytest.mark.unit
def test_sfi_after(tmp_path):
    set_tmp_db(FS, tmp_path)

    FS.run_steps()
    assert FS.results.solver.status == SolverStatus.ok


# pacify linters
annotate_vars_example = lambda x: None
# load example function from docstring
_ds2 = Docstring(BaseFlowsheetRunner.annotate_var.__doc__)
exec(_ds2.code("annotate_vars"))


@pytest.mark.unit
def test_ann_docs():
    annotate_vars_example(fr := FlowsheetRunner())
    ex = fr.annotated_vars["example"]
    assert ex["fullname"] == "ScalarVar"
    assert ex["title"] == "Example variable"


#####
# Test utilities to find wrapped functions
#####


@pytest.mark.unit
def test_find_wrapped():
    from . import test_simple_wrap

    assert _find_global_flowsheet(test_simple_wrap) == {}
    assert _find_wrapped_main(test_simple_wrap)
