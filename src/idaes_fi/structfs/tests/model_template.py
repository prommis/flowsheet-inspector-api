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

# from idaes.core.scaling import AutoScaler, set_scaling_factor
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes_fi.structfs import FlowsheetRunner, Context

_FS = FlowsheetRunner(name="my flowsheet", module=__name__)


@_FS.step("build")
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


def add_property_packages(m):
    """Add the property packages we intend to use to the flowsheet."""
    # e.g., m.fs.properties_1 = MyPropertyPackage.PhysicalParameterBlock()


def add_units(m):
    """Add Unit Models to their flowsheet to represent each unit operation
    in the process.
    """
    # e.g., m.fs.unit01 = UnitModel(property_package=m.fs.properties_1)


def connect_units(m):
    """Declare Arcs (or streams) which connect the outlet of each unit operation
    to the inlet of the next."""
    # add Arcs
    # e.g., m.fs.arc_1 = Arc(source=m.fs.unit01.outlet, destination=m.fs.unit02.inlet)
    # Once all Arcs in a flowsheet have been defined, it is necessary
    # to expand these Arcs using the Pyomo TransformationFactory.
    TransformationFactory("network.expand_arcs").apply_to(m)


@_FS.step("set_solver")
def set_solver(context):
    """Set the optimization solver"""
    context.solver = SolverFactory("ipopt")


@_FS.step("set_operating_conditions")
def set_operating_conditions(context):
    """ "Set variables, etc. corresponding to operating conditions"""
    m = context.model


@_FS.step("set_scaling")
def set_scaling(context):
    """Set manual scaling factors"""
    m = context.model


@_FS.step("solve_initial")
def solve_initial(context):
    """Perform initial solve of the square model"""
    m = context.model
    assert degrees_of_freedom(m) == 0
    results = context.solver.solve(m, tee=context["tee"])
    assert results.solver.termination_condition == TerminationCondition.optimal


@_FS.step("set_autoscaling")
def set_autoscaling(context):
    """Set autoscaling"""
    m = context.model


@_FS.step("add_costing")
def add_costing(context):
    """Add costing variables (if present)"""
    m = context.model


@_FS.step("initialize_costing")
def initialize_costing(context):
    """Initialize costing"""
    m = context.model


@_FS.step("setup_optimization")
def setup_optimization(context):
    """Increase degrees of freedom in the model (e.g. unfix variables)
    and set objective function for optimization.
    """
    m = context.model


@_FS.step("solve_optimization")
def solve_optimization(context):
    """Solve the optimization problem."""
    m = context.model
    context.results = context.solver.solve(m, tee=context.tee)


if __name__ == "__main__":
    # run all flowsheet steps, in order
    _FS.run_steps()
    # also could run just some, e.g. to run up to 'solve_initial':
    # _FS.run_steps(last="solve_initial")
