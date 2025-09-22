from .root import router as root_router
from .tabs import router as tabs_router
from .view import router as view_router
from .actions import router as actions_router

routers = (root_router, tabs_router, view_router, actions_router)
