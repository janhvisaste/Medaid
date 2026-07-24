"""
Celery tasks for asynchronous medical report processing.

Fixes applied:
  - Bug #1: Was calling processor.process_report() which didn't exist.
  - Bug #2: Was setting report.status on a model that had no status field.
  Both are now fixed: status field exists, and we call the correct pipeline.
"""

import logging

from celery import shared_task
from django.db import transaction

from .llm_quota import note_global_usage
from .models import MedicalReport, MedicalTest, AbnormalResult
from .report_processor import get_report_processor

logger = logging.getLogger(__name__)


@shared_task
def refresh_openrouter_fallback_model_task():
    """Warm the OpenRouter failover-model cache out-of-band.

    The triage path only ever reads this cache (never issues the HTTP call
    itself), so this task is what keeps the resolved model current. Scheduled
    via CELERY_BEAT_SCHEDULE at half the cache TTL so a single missed run
    cannot let the cache go cold.
    """
    from .llm_providers.catalog import refresh_fallback_openrouter_model

    try:
        resolved = refresh_fallback_openrouter_model()
        logger.info("task.openrouter_fallback_refreshed", extra={"model_id": resolved})
        return resolved
    except Exception:
        # Never let this bring down the worker - triage degrades to the
        # configured default on its own if the cache goes cold.
        logger.exception("task.openrouter_fallback_refresh_failed")
        return None


@shared_task
def process_medical_report_task(report_id, gender=None, age=None, past_history=None):
    """
    Asynchronously process a medical report through the OCR + LLM pipeline.

    Steps:
        1. Mark report as 'processing'
        2. Read file bytes
        3. Run OCR extraction (3-tier fallback)
        4. Run LLM insight generation
        5. Persist results (extracted_text, structured_data, insights_text)
        6. Create MedicalTest + AbnormalResult rows
        7. Mark report as 'completed' (or 'failed')
    """
    try:
        report = MedicalReport.objects.get(id=report_id)
    except MedicalReport.DoesNotExist:
        logger.error("task.report_not_found", extra={"report_id": report_id})
        return

    # Mark as processing
    report.status = "processing"
    report.save(update_fields=["status", "updated_at"])

    try:
        # Read file bytes from storage
        report.file.open("rb")
        file_bytes = report.file.read()
        report.file.close()

        content_type = report.file_type or ""

        # Build user context for the insight engine
        user_context = {
            "age": age or "Unknown",
            "gender": gender or "Unknown",
            "past_history": past_history or [],
        }

        # Run the full pipeline
        processor = get_report_processor()
        result = processor.extract_and_analyze(
            file_bytes=file_bytes,
            file_name=report.file_name,
            content_type=content_type,
            user_context=user_context,
            request_id=f"task-{report_id}",
            user_id=report.user_id,
        )

        if not result.get("success"):
            report.status = "failed"
            report.save(update_fields=["status", "updated_at"])
            logger.warning(
                "task.processing_failed",
                extra={"report_id": report_id, "error": result.get("error")},
            )
            return

        # Account for the report-insight Gemini call this pipeline just made
        # against the SHARED global quota. This background task has no user
        # awaiting a 429, so it cannot be gated with check_llm_quota; but its
        # LLM usage must still count so async report processing is not a
        # quota-free loophole that silently drains the shared free-tier/paid
        # budget the interactive report-insight gate is protecting. Noted on
        # the success branch only, so a report that failed OCR (and therefore
        # never reached the Gemini call) is not counted.
        note_global_usage("report_insight")

        # Persist results in a transaction
        with transaction.atomic():
            report.extracted_text = result.get("extracted_text", "")
            report.structured_data = result.get("structured_data", {})
            report.insights_text = result.get("insights_text", "")
            report.ocr_path = result.get("ocr_path", "unknown")
            report.status = "completed"
            report.save(update_fields=[
                "extracted_text", "structured_data", "insights_text",
                "ocr_path", "status", "updated_at",
            ])

            # Clear any existing tests from previous analysis
            report.tests.all().delete()

            # Create MedicalTest and AbnormalResult rows from structured data
            structured = result.get("structured_data", {})
            tests = structured.get("tests", [])

            for test_data in tests:
                if not isinstance(test_data, dict):
                    continue

                test_name = test_data.get("test_name", "")
                value_str = test_data.get("value", "")
                unit = test_data.get("unit", "")
                reference_range = test_data.get("reference_range", "Not specified")
                status = test_data.get("status", "unknown")
                is_abnormal = status not in ("normal", "unknown")

                # Try to parse numeric value; if it fails, store as 0.0
                try:
                    test_value = float(value_str.replace(",", "").strip())
                except (ValueError, TypeError, AttributeError):
                    test_value = 0.0

                test = MedicalTest.objects.create(
                    medical_report=report,
                    test_name=test_name,
                    test_value=test_value,
                    test_unit=unit,
                    reference_range=reference_range,
                    is_abnormal=is_abnormal,
                )

                if is_abnormal:
                    # Find the matching abnormal finding for interpretation
                    abnormal_findings = structured.get("abnormal_findings", [])
                    interpretation = ""
                    concern_level = "Low"
                    for finding in abnormal_findings:
                        if finding.get("test_name", "").lower() == test_name.lower():
                            interpretation = finding.get("explanation", "")
                            break

                    if status == "critical":
                        concern_level = "High"
                    elif status in ("high", "low"):
                        concern_level = "Moderate"

                    AbnormalResult.objects.create(
                        medical_test=test,
                        status=status.capitalize(),
                        concern_level=concern_level,
                        interpretation=interpretation,
                    )

        logger.info(
            "task.processing_complete",
            extra={
                "report_id": report_id,
                "ocr_path": result.get("ocr_path"),
                "tests_count": len(tests),
                "degraded": structured.get("degraded", False),
            },
        )

    except Exception as e:
        logger.exception("task.unexpected_error", extra={"report_id": report_id})
        try:
            report.status = "failed"
            report.save(update_fields=["status", "updated_at"])
        except Exception:
            pass
