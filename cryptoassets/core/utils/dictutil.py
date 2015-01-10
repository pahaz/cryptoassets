


class MergeError(Exception):
    pass


def merge_dict(a, b):
    """merges b into a and return merged result.

    NOTE: tuples and arbitrary objects are not handled as it is totally ambiguous what should happen

    Courtesy of http://stackoverflow.com/a/15836901/315168
    """
    key = None
    # ## debug output
    # sys.stderr.write("DEBUG: %s to %s\n" %(b,a))
    try:
        if a is None or isinstance(a, str) or isinstance(a, int) or isinstance(a, float):
            # border case for first run or if a is a primitive
            a = b
        elif isinstance(a, list):
            # lists can be only appended
            if isinstance(b, list):
                # merge lists
                a.extend(b)
            else:
                # append to list
                a.append(b)
        elif isinstance(a, dict):
            # dicts must be merged
            if isinstance(b, dict):
                for key in b:
                    if key in a:
                        a[key] = merge_dict(a[key], b[key])
                    else:
                        a[key] = b[key]
            else:
                raise MergeError('Cannot merge non-dict "%s" into dict "%s"' % (b, a))
        else:
            raise MergeError('NOT IMPLEMENTED "%s" into "%s"' % (b, a))
    except TypeError as e:
        raise MergeError('TypeError "%s" in key "%s" when merging "%s" into "%s"' % (e, key, b, a))
    return a
