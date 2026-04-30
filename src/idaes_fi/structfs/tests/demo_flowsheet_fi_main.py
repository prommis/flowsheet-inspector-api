"""
Import functions from demo flowsheet, call them in a main()
function decorated with @fi_main
"""

from .. import fi_main
from .demo_flowsheet import *


@fi_main(name="Demo Flowsheet")
def main():
    model = build_flowsheet()
    set_dof(model)
    set_scaling(model)
    initialize_flowsheet(model)
    solver = get_solver("ipopt")
    results = solve_flowsheet(model, solver, stee=True)
    return model, results


if __name__ == "__main__":
    main()
