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
"""Mermaid diagram action."""

from pydantic import BaseModel

from ..action_base import Action

try:
    from idaes_connectivity.base import Connectivity, Mermaid
except ImportError:
    Connectivity = None


class MermaidDiagram(Action):
    """Action to generate a Mermaid diagram after the run."""

    class Report(BaseModel):
        """Report containing a Mermaid diagram."""

        diagram: list[str]  #: each item is one line

    def __init__(self, runner, **kwargs):
        """Initialize Mermaid diagram generation settings.

        Args:
            runner: Runner that owns this action.
            **kwargs: Additional keyword arguments passed to `Action`.
        """
        super().__init__(runner, **kwargs)
        self._images = False  # TODO: make this configurable
        self._model_root_split = []
        self.diagram = None

    def show_unit_images(self, value: bool):
        """Whether Mermaid displays images for units.

        Args:
            value: If true, display images. Otherwise, don't.
        """
        self._images = bool(value)

    def set_model_root(self, path: str):
        """Set path to root of model to display (default is model itself).

        Args:
            path: Dotted path like "fs" or "fs.component"
        """
        self._model_root_split = path.split(".")

    def after_run(self):
        """Build Mermaid diagram after the run."""
        if Connectivity is None:
            self.diagram = None
        else:
            root = self._runner.model
            for p in self._model_root_split:
                root = getattr(root, p)
            conn = Connectivity(input_model=root)
            self.diagram = Mermaid(conn, component_images=self._images)

    def report(self) -> Report | dict:
        """Report containing the Mermaid diagram.

        Returns:
            Report object if idaes_connectivity is active, otherwise
            an empty dictionary
        """
        if self.diagram is None:
            return {}
        mermaid_lines = self.diagram.write(None).split("\n")
        return self.Report(diagram=mermaid_lines)
