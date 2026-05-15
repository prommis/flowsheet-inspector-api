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
"""Model variable extraction action."""

import logging
import re

import pyomo.environ as pyo
from pydantic import BaseModel, Field
from pyomo.core.base.param import IndexedParam
from pyomo.core.base.var import IndexedVar
from pyomo.network.port import Port

from ..action_base import Action
from ..fsrunner import BaseFlowsheetRunner


class ModelVariables(Action):
    """Extract and format model variables."""

    VAR_TYPE, PARAM_TYPE = "V", "P"

    class Report(BaseModel):
        """Report for ModelVariables."""

        #: Tree of variables
        variables: dict = Field(default={})
        port_aliases: dict = Field(default={})

    def __init__(self, runner, **kwargs):
        """Initialize model variable extraction state.

        Args:
            runner: Flowsheet runner that owns this action.
            **kwargs: Additional keyword arguments passed to `Action`.
        """
        assert isinstance(runner, BaseFlowsheetRunner)  # makes no sense otherwise
        super().__init__(runner, **kwargs)
        self._vars = {}
        self._port_vars = {}
        self._ports = {}

    def after_run(self):
        """Actions performed after the run."""
        self._saved_paths = {}  # fast lookup used in _add_block()
        self.log = logging.getLogger(self.log.name)
        self._extract_vars(self._runner.model)

    def _extract_vars(self, m):
        var_tree = {}
        port_aliases = {}
        for c in m.component_objects():
            # get component type
            if self._is_var(c):
                subtype = self.VAR_TYPE
            elif self._is_param(c):
                subtype = self.PARAM_TYPE
            else:
                # find and extract aliases to vars on assoc. ports
                if hasattr(c, "component_data_objects"):
                    for port_data in c.component_data_objects(Port, descend_into=False):
                        comp_name = port_data.name  # proper name of port's component
                        for port_name, port_var in port_data.vars.items():
                            if isinstance(port_var, pyo.Var):  # only variables
                                port_aliases[f"{comp_name}.{port_name}"] = port_var.name
                continue  # do nothing else
            # start new block
            b = [subtype]
            # add its variables
            items = []
            indexed = False
            #   add each value from an indexed var/param,
            #   this also works ok for non-indexed ones
            for index in c:
                v = c[index]
                indexed = index is not None
                v_value = self._safe_scalar_value(v)
                if subtype == self.VAR_TYPE:
                    # index, value, fixed, stale, lower bound, upper bound, domain
                    item = (
                        index,
                        v_value,
                        v.fixed,
                        v.stale,
                        v.lb,
                        v.ub,
                        str(v.domain),
                    )
                else:
                    # index, value
                    item = (index, v_value)
                items.append(item)
            b.append(indexed)
            b.append(items)
            # add block to tree
            self._add_block(var_tree, c.name, b)

        self._vars = var_tree
        self._ports = port_aliases

    @staticmethod
    def _safe_scalar_value(v):
        """Get value, allowing for uninitialized values.
        An uninitialized value will return None.
        """
        if isinstance(v, float) or isinstance(v, int):
            return v
        if not v.is_fixed() and v.stale:
            # avoids logged errors from uninitialized vars
            return None
        try:
            return pyo.value(v)
        except ValueError:
            return None

    def _get_values(self, c, subtype) -> tuple[list, bool]:
        """Add each value from an indexed var/param,
        This also works ok for non-indexed ones.

        Returns:
            (list of items, indexed flag)
        """
        items = []
        indexed = False
        for index in c:
            v = c[index]
            indexed = index is not None
            if subtype == self.VAR_TYPE:
                # index, value, units, is-fixed, is-stale, lower-bound, upper-bound, domain
                item = (
                    index,
                    pyo.value(v),
                    self._unitstr(c),
                    v.fixed,
                    v.stale,
                    v.lb,
                    v.ub,
                    str(v.domain),
                )
            else:
                # index, value, units, domain
                item = (index, pyo.value(v), self._unitstr(c))
            items.append(item)
        return items, indexed

    @staticmethod
    def _unitstr(c):
        # Convert Pyomo units obj to string
        s = str(c.get_units())
        # Replace 'None' with an empty string
        return "" if s == "None" else s

    @staticmethod
    def _is_var(c):
        return c.is_variable_type() or isinstance(c, IndexedVar)

    @staticmethod
    def _is_param(c):
        return c.is_parameter_type() or isinstance(c, IndexedParam)

    @staticmethod
    def _add_block(tree: dict, name: str, block):
        # get parts of the name
        # - mostly logic to handle 'foo.bar[0.0].baz' crap
        p = name.split(".")
        parts, i, n = [], 0, len(p)
        while i < n:
            cur = p[i]
            # since split('.') creates ('foo[0.', '0]') from 'foo[0.0]',
            # we need to rejoin them
            if i < n - 1 and re.match(r".*\[\d+$", cur):
                next_ = p[i + 1]
                parts.append(cur + "." + next_)
                i += 2
            else:
                parts.append(cur)
                i += 1
        # insert in tree by walking down each
        # key in 'parts', adding empty dicts
        # as we go
        t, prev = tree, None
        for p in parts:
            prev = t
            if p not in t:
                t[p] = {}
            t = t[p]
        # add the block in the final dict
        prev[p] = block

    def report(self) -> Report:
        """Report containing model variable values."""
        return self.Report(variables=self._vars, port_aliases=self._ports)
