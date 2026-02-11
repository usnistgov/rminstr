# -*- coding: utf-8 -*-
"""Module with custom pathing funcitons."""

import os
from pathlib import Path
__all__ = ['validate_path', 'new_local_dir', 'new_dir']


def validate_path(
    path, check_dirs: list[str] = None, accept_duplicates: bool = False
) -> str:
    """
    Validate if path is an existing file.

    Parameters
    ----------
    filename : str
        The file path to check.

    check_dirs : list[str], optional
        If true, will check in the directories for a file matching the
        original name. If found, will return a valid file
        path from one of those directories. The default is True.

    accept_duplicates : bool, optional
        If true and files with the same basename found in the search
        directories, will return the first file found. Else, will throw an
        error. The default is False.

    Returns
    -------
    str
        Valid file path.

    """
    # make a list of directories to check, original first
    base_dir = os.path.dirname(os.path.abspath(path))
    if check_dirs is None:
        check_dirs = [base_dir]
    elif type(check_dirs) is str:
        check_dirs = [base_dir, check_dirs]
    else:
        check_dirs = [base_dir] + check_dirs

    # loop through directories and search for files w/ matching basenames
    matches = []
    file = os.path.basename(path)
    for d in check_dirs:
        new_path = os.path.join(d, file)
        if os.path.exists(new_path):
            matches.append(new_path)

    # check for edge case exceptions
    # more then 1 file exists
    if len(matches) > 1 and not accept_duplicates:
        msg = ''
        for s in matches:
            msg += '\n ' + os.path.dirname(s)
        msg += '\n'

        raise Exception(file + ' exists in multiple locations:\n ' + msg)
    #
    elif len(matches) == 0:
        msg = ''
        for s in check_dirs:
            msg += '\n ' + s
        msg += '\n'
        raise FileNotFoundError(file + ' not found in : \n' + msg)
    else:
        return matches[0]


def new_local_dir(base_name: str):
    """
    Create local directory with an iterated name.

    Returns
    -------
    rel_path
        Relative path to newly create local directory.

    """
    cwd = os.getcwd()
    curr = next(os.walk(cwd))[1]
    n = len([d for d in curr if base_name in d])

    complete = False
    while not complete:
        try:
            rel_path = base_name + '_' + str(n)
            os.mkdir(rel_path)
            complete = True
        except FileExistsError:
            n += 1
    return rel_path


def new_dir(base_dir: str, base_name: str):
    """
    Create a directory with an iterated name inside base_dir.

    Returns
    -------
    path.
        Absolute path to newly create local directory.

    """
    cwd = base_dir
    n = len([d for d in Path(cwd).iterdir() if base_name in d.stem])

    complete = False
    while not complete:
        try:
            path = os.path.join(cwd, base_name + '_' + str(n))
            os.mkdir(path)
            complete = True
        except FileExistsError:
            n += 1
    return path