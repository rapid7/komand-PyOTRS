""" This is PyOTRS provide python access to OTRS

.. note::

   Implements: https://otrs.github.io/doc/api/otrs/5.0/Perl/index.html

"""

from .lib import Article  # noqa
from .lib import Attachment  # noqa
from .lib import Client  # noqa
from .lib import DynamicField  # noqa
from .lib import SessionStore  # noqa
from .lib import Ticket  # noqa

# Set default logging handler to avoid "No handler found" warnings.
import logging
# Python 2.7+
try:  # pragma: no cover
    from logging import NullHandler
except ImportError:  # pragma: no cover
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logging.getLogger(__name__).addHandler(NullHandler())
