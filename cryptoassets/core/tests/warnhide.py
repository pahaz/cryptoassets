"""Hide some common warnings during the unit tests."""

import warnings

from sqlalchemy.exc import SAWarning


def begone():

    warnings.filterwarnings(
        'ignore',
        r"^Dialect sqlite\+pysqlite does \*not\* support Decimal objects natively\, "
        "and SQLAlchemy must convert from floating point - rounding errors and other "
        "issues may occur\. Please consider storing Decimal numbers as strings or "
        "integers on this platform for lossless storage\.$",
        SAWarning, r'^sqlalchemy\.sql\.type_api$')

    # ResourceWarning: unclosed <ssl.SSLSocket fd=9, family=AddressFamily.AF_INET, type=SocketType.SOCK_STREAM, proto=6, laddr=('192.168.1.4', 56386), raddr=('50.116.26.213', 443)>
    # http://stackoverflow.com/a/26620811/315168
    warnings.filterwarnings("ignore", category=ResourceWarning)  # noqa

