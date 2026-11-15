from fastapi.routing import APIRoute

from app.main import app
from app.routers import admin, auth, cases, evaluation, images, meta, simulations
from app.security.deps import get_active_user, get_current_user

# Add every new router here. The completeness test below fails if you forget one.
ROUTERS = [
    auth.router,
    auth.me_router,
    cases.router,
    images.router,
    meta.router,
    admin.router,
    evaluation.router,
    simulations.router,
]

# The only routes allowed to be open without logging in.
PUBLIC = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
}

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _calls(dependant):
    for sub in dependant.dependencies:
        yield sub.call
        yield from _calls(sub)


def _is_protected(route: APIRoute) -> bool:
    for call in _calls(route.dependant):
        if call in (get_current_user, get_active_user):
            return True
        if "require_roles" in getattr(call, "__qualname__", ""):
            return True
    return False


def _all_routes():
    found = []
    for router in ROUTERS:
        found += [r for r in router.routes if isinstance(r, APIRoute)]
    found += [r for r in app.routes if isinstance(r, APIRoute)]  # e.g. /api/health
    for route in found:
        for method in route.methods & HTTP_METHODS:
            yield method, route.path, route


def test_the_walk_sees_every_route_the_app_publishes():
    published = {
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method.upper() in HTTP_METHODS
    }
    walked = {(method, path) for method, path, _ in _all_routes()}
    assert walked == published, (
        f"Missing from the walk: {sorted(published - walked)}; "
        f"not published: {sorted(walked - published)}"
    )


def test_every_route_has_a_permission_dependency():
    unprotected = sorted(
        f"{method} {path}"
        for method, path, route in _all_routes()
        if (method, path) not in PUBLIC and not _is_protected(route)
    )
    assert unprotected == [], f"Routes without a permission dependency: {unprotected}"


def test_public_routes_are_exactly_the_allowed_ones():
    open_routes = {
        (method, path) for method, path, route in _all_routes() if not _is_protected(route)
    }
    assert open_routes == PUBLIC