"""JWT-protected HTTP boundary for reference-compatible triage."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .assess import integrate_report_and_run_assessment
from .serializers import ReferenceCompatRequestSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assess_reference_compat(request):
    """Assess using the reference body contract without changing V2 routes."""
    serializer = ReferenceCompatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = integrate_report_and_run_assessment(**serializer.validated_data)
    return Response(result, status=status.HTTP_200_OK)
