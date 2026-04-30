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
"""
Tests for simplified wrapper API.
"""

import pytest
from idaes.core.util.doctesting import Docstring
from ..simple_wrap import _Wrapper
from ..common import RESULT_FLOWSHEET_KEY


# pacify linter by defining functions
# (will be overwritten by exec() below)
def fi_wrap_my_main_function(x, y, z=None):
    return None


def fi_wrap_build_flowsheet():
    return None


def fi_wrap_solve_flowsheet():
    return None


# redefine 2 functions that will be needed by original name
def build_flowsheet():
    return fi_wrap_build_flowsheet()


def solve_flowsheet():
    return fi_wrap_solve_flowsheet()


#  load the functions from the docstring
_ds1 = Docstring(_Wrapper.__doc__)
exec(_ds1.code("simple-wrapper-usage", func_prefix="fi_wrap_"))


@pytest.mark.unit
def test_wrap_docstr():
    model, solve_result = fi_wrap_my_main_function("arg1", "arg2", keyword="foo")
    print(f"solve_result={solve_result}")
    # model should be whatever the fake build returns
    assert type(model) == type(fi_wrap_build_flowsheet())
    # empty solve dict should only have the 'extra' key with the added object
    assert len(solve_result) == 1
    assert solve_result[RESULT_FLOWSHEET_KEY]
