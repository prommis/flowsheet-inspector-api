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
from idaes.models.unit_models import (
    Flash,
    Heater,
    Mixer,
    PressureChanger,
    Separator as Splitter,
    StoichiometricReactor,
)
from idaes.models.unit_models.pressure_changer import ThermodynamicAssumption

# from idaes.core.scaling import AutoScaler, set_scaling_factor
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes_fi.structfs import FlowsheetRunner
from idaes_fi.structfs.fsrunner import Context

import hda_ideal_VLE as thermo_props
import hda_reaction as reaction_props

_FS = FlowsheetRunner()


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
    m.fs.thermo_params = thermo_props.HDAParameterBlock()
    m.fs.reaction_params = reaction_props.HDAReactionParameterBlock(
        property_package=m.fs.thermo_params
    )


def add_units(m):
    """Add Unit Models to their flowsheet to represent each unit operation
    in the process.
    """
    m.fs.M101 = Mixer(
        property_package=m.fs.thermo_params,
        inlet_list=["toluene_feed", "hydrogen_feed", "vapor_recycle"],
    )

    m.fs.H101 = Heater(
        property_package=m.fs.thermo_params,
        has_pressure_change=False,
        has_phase_equilibrium=True,
    )

    m.fs.R101 = StoichiometricReactor(
        property_package=m.fs.thermo_params,
        reaction_package=m.fs.reaction_params,
        has_heat_of_reaction=True,
        has_heat_transfer=True,
        has_pressure_change=False,
    )

    m.fs.F101 = Flash(
        property_package=m.fs.thermo_params,
        has_heat_transfer=True,
        has_pressure_change=True,
    )

    m.fs.S101 = Splitter(
        property_package=m.fs.thermo_params,
        ideal_separation=False,
        outlet_list=["purge", "recycle"],
    )

    m.fs.C101 = PressureChanger(
        property_package=m.fs.thermo_params,
        compressor=True,
        thermodynamic_assumption=ThermodynamicAssumption.isothermal,
    )

    m.fs.F102 = Flash(
        property_package=m.fs.thermo_params,
        has_heat_transfer=True,
        has_pressure_change=True,
    )


def connect_units(m):
    """Declare Arcs (or streams) which connect the outlet of each unit operation
    to the inlet of the next."""
    # add Arcs
    m.fs.s03 = Arc(source=m.fs.M101.outlet, destination=m.fs.H101.inlet)
    m.fs.s04 = Arc(source=m.fs.H101.outlet, destination=m.fs.R101.inlet)
    m.fs.s05 = Arc(source=m.fs.R101.outlet, destination=m.fs.F101.inlet)
    m.fs.s06 = Arc(source=m.fs.F101.vap_outlet, destination=m.fs.S101.inlet)
    m.fs.s10 = Arc(source=m.fs.F101.liq_outlet, destination=m.fs.F102.inlet)
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
    # assert degrees_of_freedom(m) == 0
    results = context.solver.solve(m, tee=context["tee"])
    # assert results.solver.termination_condition == TerminationCondition.optimal


# @_FS.step("set_autoscaling")
# def set_autoscaling(context):
#     """Set autoscaling"""
#     m = context.model


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
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("name", help="Flowsheet name")
    p.add_argument("--last", help="last step [build]", default="build")
    a = p.parse_args()

    _FS.set_report_target(name=a.name)
    # run all flowsheet steps, in order
    _FS.run_steps(last=a.last)
    # also could run just some, e.g. to run up to 'solve_initial':
    # _FS.run_steps(last="solve_initial")
    print(f"Ran flowsheet {a.name}")
