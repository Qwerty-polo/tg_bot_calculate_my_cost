from aiogram import Router

from app.handlers import budgets, common, reset, screenshots, stats


def get_root_router() -> Router:
    """Aggregate all feature routers into a single root router."""
    router = Router(name="root")
    router.include_router(common.router)
    # Reset is early so its menu button / callbacks win over other handlers.
    router.include_router(reset.router)
    router.include_router(budgets.router)
    router.include_router(stats.router)
    # Screenshot router is last: it handles bare photos.
    router.include_router(screenshots.router)
    return router


__all__ = ["get_root_router"]
