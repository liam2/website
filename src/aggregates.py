from __future__ import print_function

import inspect

import numpy as np

from expr import (Variable, BinaryOp, getdtype, expr_eval, traverse_expr,
                  get_tmp_varname, ispresent, FunctionExpr,
                  always, firstarg_dtype)
from exprbases import EvaluableExpression, NumpyAggregate, FilteredExpression
import exprmisc
from context import context_length
from utils import deprecated


class All(NumpyAggregate):
    np_func = np.all
    dtype = always(bool)


class Any(NumpyAggregate):
    np_func = np.any
    dtype = always(bool)


#XXX: inherit from FilteredExpression instead?
class Count(FunctionExpr):
    func_name = 'count'

    def compute(self, context, filter=None):
        if filter is None:
            return context_length(context)
        else:
            #TODO: check this at "compile" time (in __init__), though for
            # that we need to know the type of all temporary variables
            # first
            if not np.issubdtype(filter.dtype, bool):
                raise ValueError("count filter must be a boolean expression")
            return np.sum(filter)

    dtype = always(int)


def argsnotsupported(when, notsupported):
    when = (' when %s' % when) if when else ''
    def decorator(func):
        def decorated(*args, **kwargs):
            # check that extra args use default values
            nargs = len(inspect.getargspec(func).args)
            for (k, defaultvalue), value in zip(notsupported, args[nargs:]):
                if value is not defaultvalue:
                    raise NotImplementedError("'%s' argument is not supported "
                                              "for %s%s"
                                              % (k, func.__name__, when))
            args = args[:nargs]
            return func(*args, **kwargs)
        return decorated
    return decorator

limited = argsnotsupported("skip_na=True", [('out', None), ('keepdims', False)])
nanmin = limited(np.nanmin)
nanmax = limited(np.nanmax)


class Min(NumpyAggregate):
    func_name = 'min'
    np_func = np.amin
    nan_func = (nanmin,)
    dtype = firstarg_dtype


class Max(NumpyAggregate):
    func_name = 'max'
    np_func = np.amax
    nan_func = (nanmax,)
    dtype = firstarg_dtype


def na_sum(a, overwrite=False):
    if np.issubdtype(a.dtype, np.inexact):
        func = np.nansum
    else:
        func = np.sum
        if overwrite:
            a *= ispresent(a)
        else:
            a = a * ispresent(a)
    return func(a)


#class Sum(NumpyAggregate):
#    np_func = np.sum
#    nan_func = (nansum,)
#
#    def dtype(self, context):
#        #TODO: merge this typemap with tsum's
#        typemap = {bool: int, int: int, float: float}
#        return typemap[dtype(self.args[0], context)]


#TODO: inherit from NumpyAggregate, to get support for the axis argument
class Sum(FilteredExpression):
    func_name = 'sum'
    no_eval = ('expr', 'filter')

    def compute(self, context, expr, filter=None, skip_na=True):
        filter_expr = self._getfilter(context, filter)
        if filter_expr is not None:
            expr = BinaryOp('*', expr, filter_expr)

        values = expr_eval(expr, context)
        values = np.asarray(values)

        return na_sum(values) if skip_na else np.sum(values)

    def dtype(self, context):
        #TODO: merge this typemap with tsum's
        typemap = {bool: int, int: int, float: float}
        return typemap[getdtype(self.args[0], context)]


#class Average(NumpyAggregate):
#    func_name = 'avg'
#    np_func = np.mean
#    nan_func = (nanmean,)
#    dtype = always(float)


#TODO: inherit from NumpyAggregate, to get support for the axis argument
class Average(FilteredExpression):
    func_name = 'avg'
    no_eval = ('expr',)

    def compute(self, context, expr, filter=None, skip_na=True):
        #FIXME: either take "contextual filter" into account here (by using
        # self._getfilter), or don't do it in sum & gini
        if filter is not None:
            tmp_varname = get_tmp_varname()
            context = context.copy()
            context[tmp_varname] = filter
            if getdtype(expr, context) is bool:
                # convert expr to int because mul_bbb is not implemented in
                # numexpr
                # expr *= 1
                expr = BinaryOp('*', expr, 1)
            # expr *= filter_values
            expr = BinaryOp('*', expr, Variable(tmp_varname))
        else:
            filter = True

        values = expr_eval(expr, context)
        values = np.asarray(values)

        if skip_na:
            # we should *not* use an inplace operation because filter can be a
            # simple variable
            filter = filter & ispresent(values)

        if filter is True:
            numrows = len(values)
        else:
            numrows = np.sum(filter)

        if numrows:
            if skip_na:
                return na_sum(values) / float(numrows)
            else:
                return np.sum(values) / float(numrows)
        else:
            return float('nan')

    dtype = always(float)


class Std(NumpyAggregate):
    np_func = np.std
    dtype = always(float)


class Median(NumpyAggregate):
    np_func = np.median
    dtype = always(float)


class Percentile(NumpyAggregate):
    np_func = np.percentile
    dtype = always(float)


#TODO: filter and skip_na should be provided by an "Aggregate" mixin that is
# used both here and in NumpyAggregate
class Gini(FilteredExpression):
    func_name = 'gini'
    no_eval = ('filter',)

    def compute(self, context, expr, filter=None, skip_na=True):
        values = np.asarray(expr)

        filter_expr = self._getfilter(context, filter)
        if filter_expr is not None:
            filter_values = expr_eval(filter_expr, context)
        else:
            filter_values = True
        if skip_na:
            # we should *not* use an inplace operation because filter_values
            # can be a simple variable
            filter_values = filter_values & ispresent(values)
        if filter_values is not True:
            values = values[filter_values]

        # from Wikipedia:
        # G = 1/n * (n + 1 - 2 * (sum((n + 1 - i) * a[i]) / sum(a[i])))
        #                        i=1..n                    i=1..n
        # but sum((n + 1 - i) * a[i])
        #    i=1..n
        #   = sum((n - i) * a[i] for i in range(n))
        #   = sum(cumsum(a))
        sorted_values = np.sort(values)
        n = len(values)

        # force float to avoid overflows with integer input expressions
        cumsum = np.cumsum(sorted_values, dtype=float)
        values_sum = cumsum[-1]
        if values_sum == 0:
            print("gini(%s, filter=%s): expression is all zeros (or nan) "
                  "for filter" % (self.expr, filter_expr))
        return (n + 1 - 2 * np.sum(cumsum) / values_sum) / n

    dtype = always(float)


def make_dispatcher(agg_func, elem_func):
    def dispatcher(*args, **kwargs):
        func = agg_func if len(args) == 1 else elem_func
        return func(*args, **kwargs)

    return dispatcher


functions = {
    'all': All, 'any': Any, 'count': Count,
    'min': make_dispatcher(Min, exprmisc.Min),
    'max': make_dispatcher(Max, exprmisc.Max),
    'sum': Sum, 'avg': Average, 'std': Std,
    'median': Median, 'percentile': Percentile,
    'gini': Gini
}

for k, v in functions.items():
    functions['grp' + k] = deprecated(v, "%s is deprecated, please use %s "
                                         "instead" % ('grp' + k, k))
