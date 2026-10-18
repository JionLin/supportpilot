"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    """Return service health status.

    Returns:
        dict[str, str]: JSON body with status ok when the process is up.
    """
    return {"status": "ok"}
