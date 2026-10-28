from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    renderer_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
def health(request):
    """Confirm that Django is running.

    This endpoint deliberately performs no database or cache access, and it
    returns no configuration, version, host, or environment details. It can
    therefore answer while MySQL is unavailable. It is a liveness probe, not a
    database-readiness check; no database-aware readiness endpoint exists yet.
    """
    response = Response(
        {
            "status": "ok",
            "service": "bolu-wall-engine-api",
        }
    )
    response["Cache-Control"] = "no-store"
    return response
