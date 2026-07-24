"""DRF serializers for the isolated reference-compatible endpoint."""

from rest_framework import serializers


class ReferenceCompatRequestSerializer(serializers.Serializer):
    report_data = serializers.JSONField(required=False, allow_null=True, default=None)
    user_inputs = serializers.JSONField(required=False, default=dict)
    user_profile = serializers.JSONField(required=False, allow_null=True, default=None)


class ReferenceConditionSerializer(serializers.Serializer):
    disease = serializers.CharField()
    confidence = serializers.FloatField()


class ReferenceAssessmentSerializer(serializers.Serializer):
    possible_conditions = ReferenceConditionSerializer(many=True)
    risk_level = serializers.ChoiceField(choices=["Low", "Medium", "High", "Emergency"])
    risk_proba = serializers.FloatField()
    reason = serializers.CharField(allow_blank=True)
    recommendations = serializers.ListField(child=serializers.CharField())
