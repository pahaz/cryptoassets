"""Iteration utilities.



"""

import itertools


def grouper(n, iterable):
    """Iterate the list in the chunks of n.

    Courtesy of http://stackoverflow.com/a/8991553/315168
    """
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk
