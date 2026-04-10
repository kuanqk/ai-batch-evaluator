from rest_framework import serializers

from .models import Evaluation, EvaluationJob


class EvaluationJobSerializer(serializers.ModelSerializer):
    progress_percent = serializers.FloatField(read_only=True)

    class Meta:
        model = EvaluationJob
        fields = [
            "id", "name", "source_file", "status", "total", "processed",
            "failed", "paused", "progress_percent", "webhook_url", "evaluator_config",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "processed", "failed", "created_at", "updated_at"]


class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = [
            "id", "job", "evaluator_config", "material_id", "file_path", "file_url",
            "city", "trainer", "group_name", "file_name",
            "teacher_name", "topic",
            "scores", "total_score", "score_percentage", "score_level",
            "feedback", "llm_result", "status", "current_step", "error",
            "extraction_method", "doc_lang", "file_size_bytes", "doc_chars",
            "prompt_tokens", "completion_tokens",
            "used_vision_ocr", "used_fix_docx", "was_empty_doc",
            "created_at", "started_at", "processed_at", "updated_at",
        ]
        read_only_fields = fields
