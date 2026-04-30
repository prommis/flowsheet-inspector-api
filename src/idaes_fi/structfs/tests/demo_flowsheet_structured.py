"""
Import functions from demo flowsheet and wrap them with the FlowsheetRunner
"""

from ..fsrunner import FlowsheetRunner, Steps
from .demo_flowsheet import *

FS = FlowsheetRunner(name="Demo Flowsheet", tags="test demo", module=__name__)


@FS.step(Steps.build)
def build(ctx):
    ctx.model = build_flowsheet()


@FS.step(Steps.set_operating_conditions)
def set_operating_conditions(ctx):
    set_dof(ctx.model)


@FS.step(Steps.set_scaling)
def runner_set_scaling(ctx):
    set_scaling(ctx.model)


@FS.step(Steps.solve_initial)
def solve_initial(ctx):
    initialize_flowsheet(ctx.model)


@FS.step(Steps.set_solver)
def set_solver(ctx):
    ctx.solver = get_solver("ipopt")


@FS.step(Steps.solve_optimization)
def runner_solve_flowsheet(ctx):
    ctx.results = solve_flowsheet(ctx.model, ctx.solver, stee=True)


if __name__ == "__main__":
    FS.run_steps()
