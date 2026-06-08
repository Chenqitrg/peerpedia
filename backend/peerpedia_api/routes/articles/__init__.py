"""Article API routes — split into CRUD, Git, and Publish sub-modules."""
# Import sub-modules to register their route handlers on the router.
from . import (
    _crud,  # noqa: F401
    _git,  # noqa: F401
    _publish,  # noqa: F401
)
from ._router import router

__all__ = ["router"]
