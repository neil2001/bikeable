from app.models.responses import RouteResponse

_store: dict[str, RouteResponse] = {}


def save_route(route: RouteResponse) -> None:
    _store[route.route_id] = route


def get_route(route_id: str) -> RouteResponse | None:
    return _store.get(route_id)
