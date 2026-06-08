from aiogram import Router

from app.handlers import budgets, common, screenshots, stats


def get_root_router() -> Router:
    """Aggregate all feature routers into a single root router."""
    router = Router(name="root")
    router.include_router(common.router)
    router.include_router(budgets.router)
    router.include_router(stats.router)
    # Screenshot router is last: it handles bare photos.
    router.include_router(screenshots.router)
    return router


__all__ = ["get_root_router"]
