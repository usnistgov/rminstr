"""Module for storing classes/functions that produce simple graphics."""

import sys


def progressbar(msg: str, total: int, progress: int):
    """
    Display a progress bar.

    Call at the end of a loops iteration, re-prints on same line.

    Parameters
    ----------
    msg : str
        Message to print out.
    total : int
        Total number of iterations expected. Start at 0.
    progress : int
        Current iteration.
    """
    barLength, status = 20, ''
    progress = float(progress) / float(total)
    if progress >= 1.0:
        progress, status = 1, '\r\n'
    block = int(round(barLength * progress))
    text = (
        '\r'
        + msg
        + ':[{}] {:.0f}% {}'.format(
            '#' * block + '-' * (barLength - block), round(progress * 100, 0), status
        )
    )
    sys.stdout.write(text)
    sys.stdout.flush()
