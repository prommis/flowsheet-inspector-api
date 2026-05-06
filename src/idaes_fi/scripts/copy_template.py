#!/usr/bin/env python3
"""
Instantiate model from template
"""

import argparse
from io import StringIO
import logging
from pathlib import Path
import sys

from idaes_fi.structfs import common

_log = logging.getLogger(__name__)


class TemplateCopier:
    """Create a copy of template file with variables
    in double curly braces (e.g. `{{variable}}`), filling in
    values from a provided mapping.
    """

    def __init__(
        self,
        source: str | Path,
        target: str | Path,
        variables: dict[str, str],
    ):
        """Constructor.

        Args:
            source: Source file.
            target: Target file.
            variables: Mapping of names to values
        """
        self._src, self._tgt, self._vars = source, target, variables

    def run(self):
        """Perform the copy.

        Raises:
            IOError: if source/target files don't exist
        """
        if self._src == "-":
            source_stream = StringIO(DEFAULT_TEMPLATE)
        else:
            source_stream = Path(self._src).open("r")

        if self._tgt == "-":
            target_stream = sys.stdout
        else:
            target_stream = Path(self._tgt).open("w")

        # simple templated replacements of key/value pairs in self.variables
        # by adding double curly braces around each key
        replacements = {f"{{{{{key}}}}}": v for key, v in self._vars.items()}
        for line in source_stream:
            if "{{" in line:  # skip most lines here
                for key, value in replacements.items():
                    line = line.replace(key, value)
            target_stream.write(line)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", help="output file (default=console)", default="-")
    parser.add_argument("--source", help="input (template) file", default="-")
    parser.add_argument(
        "--var",
        help="Variable 'key=value' pair",
        nargs="*",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity; use twice for debug logging",
    )
    args = parser.parse_args(args=args)

    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    _log.setLevel(log_level)

    tmpl = TemplateCopier(
        source=args.source,
        target=args.target,
        variables=var_map,
    )

    retcode = 0
    try:
        tmpl.run()
    except IOError as err:
        _log.error(f"File error: {err}")
        retcode = 1

    if retcode == 0:
        print(f"Success: New file created at {tmpl._tgt}")
    else:
        print(f"Error: No new file created")

    return retcode


DEFAULT_TEMPLATE = '''
"""
Template for creating a new IDAES/PrOMMiS/WaterTAP flowsheet.
"""

# Pyomo/IDAES imports
from pyomo.environ import (
    Constraint,
    Var,
    ConcreteModel,
    Expression,
    Objective,
    SolverFactory,
    TerminationCondition,
    TransformationFactory,
    value,
)
from pyomo.network import Arc, SequentialDecomposition
from idaes.core import FlowsheetBlock

from idaes.core.scaling import AutoScaler, set_scaling_factor
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes_fi.structfs.fsrunner import FlowsheetRunner, Context
from idaes_fi.structfs.common import Steps  # step names

_FS = FlowsheetRunner(name="{{name}}", module=__name__)


@_FS.step(Steps.build)
def build_model(context: Context):
    """Create a model object which represents the problem to be solved.

    Args:
        context: Structured flowsheet context object with ".model" attribute to store the model.
    """
    m = ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    add_property_packages(m)
    add_units(m)
    connect_units(m)
    context.model = m


# begin: substeps of "build"


@_FS.substep(Steps.build + ".add_property_packages")
def add_property_packages(m):
    """Add the property packages we intend to use to the flowsheet."""
    # e.g., m.fs.properties_1 = MyPropertyPackage.PhysicalParameterBlock()
    pass


@_FS.substep(Steps.build + ".add_units")
def add_units(m):
    """Add Unit Models to their flowsheet to represent each unit operation
    in the process.
    """
    # e.g., m.fs.unit01 = UnitModel(property_package=m.fs.properties_1)
    pass


@_FS.substep(Steps.build + ".connect_units")
def connect_units(m):
    """Declare Arcs (or streams) which connect the outlet of each unit operation
    to the inlet of the next."""
    # add Arcs
    # e.g., m.fs.arc_1 = Arc(source=m.fs.unit01.outlet, destination=m.fs.unit02.inlet)
    # Once all Arcs in a flowsheet have been defined, it is necessary
    # to expand these Arcs using the Pyomo TransformationFactory.
    TransformationFactory("network.expand_arcs").apply_to(m)


# end: substeps of "build"


@_FS.step(Steps.set_solver)
def set_solver(context):
    """Set the optimization solver"""
    context.solver = SolverFactory("ipopt")


@_FS.step(Steps.set_operating_conditions)
def set_operating_conditions(context):
    """ "Set variables, etc. corresponding to operating conditions"""
    m = context.model


@_FS.step(Steps.set_scaling)
def set_scaling(context):
    """Set manual scaling factors, before initializing"""
    m = context.model


@_FS.step(Steps.solve_initial)
def solve_initial(context):
    """Perform initial solve of the square model"""
    m = context.model
    assert degrees_of_freedom(m) == 0
    results = context.solver.solve(m, tee=context["tee"])
    assert results.solver.termination_condition == TerminationCondition.optimal


@_FS.step(Steps.set_autoscaling)
def set_autoscaling(context):
    """Set autoscaling (as opposed to manual scaling)"""
    m = context.model


@_FS.step(Steps.add_costing)
def add_costing(context):
    """Add costing variables (if present)"""
    m = context.model


@_FS.step(Steps.initialize_costing)
def initialize_costing(context):
    """Initialize costing"""
    m = context.model


@_FS.step(Steps.setup_optimization)
def setup_optimization(context):
    """Increase degrees of freedom in the model (e.g. unfix variables)
    and set objective function for optimization.
    """
    m = context.model


@_FS.step(Steps.solve_optimization)
def solve_optimization(context):
    """Solve the optimization problem."""
    m = context.model
    context.results = context.solver.solve(m, tee=context.tee)


if __name__ == "__main__":

    # run all flowsheet steps, in order
    _FS.run_steps()
    # also could run just some, e.g. to run up to 'solve_initial':
    # _FS.run_steps(last="solve_initial")
'''

if __name__ == "__main__":
    sys.exit(main())
