from fastapi import APIRouter

from app.api.routes import (
    agent,
    alerts,
    auth,
    devices,
    health,
    metrics,
    ml,
    network,
    reports,
    topology,
    ws,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(network.router)
api_router.include_router(metrics.router)
api_router.include_router(devices.router)
api_router.include_router(topology.router)
api_router.include_router(agent.router)
api_router.include_router(alerts.router)
api_router.include_router(ml.router)
api_router.include_router(reports.router)
api_router.include_router(ws.router)

__all__ = ["api_router", "health"]
