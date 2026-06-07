"""Article API routes — split into CRUD, Git, and Publish sub-modules."""
from ._router import router

# Import sub-modules to register their route handlers on the router.
from . import _crud  # noqa: F401
from . import _git  # noqa: F401
from . import _publish  # noqa: F401

__all__ = ["router"]
