# -*- coding: utf-8 -*-
"""
Reusable behaviours that can be applied to instrument abstractions.

These behaviours include things like forcing a method to only be callable when the instrument
is in a certain state, saving key word arguments of a method to a dictionary defined
by a class attribute, and having certain methods change the state of the instrument afer being called.
"""

import warnings
import sys
import traceback
import logging
from typing import Callable
from functools import wraps


def log_arguments(name: str, path: str, function: Callable) -> Callable:
    """
    Make function save keyword arguments to a log file.

    Parameters
    ----------
    name : str
        Name of instrument. Recommend __name__

    path : str
        Path to log to. Should end in .log

    function : Callable
        Function being wrapped.

    Returns
    -------
    Callable
        Wrapped function.

    """
    lg = logging.basicConfig(filename=path, filemode='w', level=logging.INFO)
    lg = logging.getLogger()
    lg.setLevel(logging.INFO)
    lg.info(name + ' ' + function.__name__ + ' wrapped')

    @wraps(function)
    def wrap(*args, **kwargs):
        lg.info(name + str(kwargs))
        if len(args) == 0:
            out = function(**kwargs)
        else:
            out = function(*args, **kwargs)
        return out

    return wrap


# %% Warnings
# Combine?
def _state_warning(
    current_state: str, function_name: Callable, file_name: str, lineno: int, limit: int
) -> None:
    """
    Raise a warning indicating the state and function being called.

    Parameters
    ----------
    current_state : str
        Currrent state of the machine.

    function_name : Callable
        Name of the functio being called.

    file_name : str
        Name of the file where the function call happened.

    lineno : int
        Line number of call.

    limit : int
        How deep the stack traceback can go when printing.

    Returns
    -------
    None

    """
    msg = 'Attempted to call ' + function_name + ' while in ' + current_state
    _warn_with_traceback(msg, UserWarning, file_name, lineno, limit=limit)


def _warn_with_traceback(
    message: str,
    category: object,
    filename: str,
    lineno: int,
    file: str = None,
    line=None,
    limit=5,
):
    """
    Raise a warning with a message and traceback.

    Code modified from :
    https://stackoverflow.com/questions/22373927/get-traceback-of-warnings

    Parameters
    ----------
    message : str
        Message to write.

    category : object
        Type of warning.

    filename : str
        File name of the log.

    lineno int : TYPE
        Line number.

    file : str, optional
        DESCRIPTION. The default is None.

    line : TYPE, optional
        DESCRIPTION. The default is None.

    limit : TYPE, optional
        How deep the stack traceback can go when printing.. The default is 5.

    Returns
    -------
    None.

    """
    log = file if hasattr(file, 'write') else sys.stderr
    traceback.print_stack(file=log, limit=limit)
    log.write(warnings.formatwarning(message, category, filename, lineno, line))
