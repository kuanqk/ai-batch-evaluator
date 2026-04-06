"""Tests for pipeline utilities (no DB, no external services)."""

import pytest


class TestParseBatchUpload:
    def test_csv_basic(self):
        from apps.batch.utils import parse_batch_upload

        content = b"file_path,file_url\nPKS2025/Astana/Ivanov/Group1/plan.docx,https://example.com/1.docx\n"
        rows, skipped = parse_batch_upload(content, "test.csv")
        assert len(rows) == 1
        assert skipped == 0
        assert rows[0]["file_url"] == "https://example.com/1.docx"
        assert rows[0]["city"] == "Astana"
        assert rows[0]["trainer"] == "Ivanov"

    def test_csv_skip_empty_url(self):
        from apps.batch.utils import parse_batch_upload

        content = b"file_path,file_url\nsome/path/a/b/f.docx,\nsome/path/a/b/g.docx,https://ok.com/g.docx\n"
        rows, skipped = parse_batch_upload(content, "test.csv")
        assert len(rows) == 1
        assert skipped == 1

    def test_csv_missing_columns(self):
        from apps.batch.utils import parse_batch_upload

        content = b"url,path\nhttps://x.com,/a/b\n"
        with pytest.raises(ValueError, match="Required columns"):
            parse_batch_upload(content, "test.csv")

    def test_path_with_short_segments(self):
        from apps.batch.utils import parse_batch_upload

        content = b"file_path,file_url\nshort,https://example.com/1.docx\n"
        rows, skipped = parse_batch_upload(content, "test.csv")
        # Short path → meta fields are None but row is still included
        assert len(rows) == 1
        assert rows[0]["city"] is None

    def test_bom_utf8(self):
        from apps.batch.utils import parse_batch_upload

        # Simulate Excel-exported CSV with BOM
        content = "file_path,file_url\nA/B/C/D/E.docx,https://example.com/e.docx\n".encode("utf-8-sig")
        rows, skipped = parse_batch_upload(content, "test.csv")
        assert len(rows) == 1


class TestParseFilePath:
    def test_normal_path(self):
        from pipeline.parser import parse_file_path

        p = parse_file_path("ПКС2025/Астана/Иванов/Группа1/план.docx")
        assert p.program == "ПКС2025"
        assert p.city == "Астана"
        assert p.trainer == "Иванов"
        assert p.group_name == "Группа1"
        assert p.file_name == "план.docx"

    def test_backslash_normalized(self):
        from pipeline.parser import parse_file_path

        p = parse_file_path("A\\B\\C\\D\\file.pdf")
        assert p.city == "B"
        assert p.file_name == "file.pdf"

    def test_too_short_path(self):
        from pipeline.parser import parse_file_path

        with pytest.raises(ValueError):
            parse_file_path("only/three/parts")


class TestLLMParsing:
    def test_parse_plain_json(self):
        from pipeline.llm import parse_llm_response

        raw = '{"key": "value"}'
        result = parse_llm_response(raw)
        assert result == {"key": "value"}

    def test_parse_markdown_fence(self):
        from pipeline.llm import parse_llm_response

        raw = '```json\n{"score": 42}\n```'
        result = parse_llm_response(raw)
        assert result == {"score": 42}

    def test_parse_with_think_block(self):
        from pipeline.llm import parse_llm_response

        raw = '<think>thinking...</redacted_thinking>\n{"result": "ok"}'
        result = parse_llm_response(raw)
        assert result == {"result": "ok"}

    def test_parse_none_returns_none(self):
        from pipeline.llm import parse_llm_response

        assert parse_llm_response(None) is None
        assert parse_llm_response("") is None
        assert parse_llm_response("not json at all { broken") is None

    def test_extract_scores_empty(self):
        from pipeline.llm import extract_scores

        scores, total, level = extract_scores({})
        assert total == 0
        assert level == 1
        assert all(v == 0 for v in scores.values())

    def test_extract_scores_normal(self):
        from pipeline.llm import extract_scores

        parsed = {
            "full_report": {
                "sections": [
                    {
                        "section_number": 1,
                        "criteria": [
                            {"criterion_number": 1, "score": 3},
                            {"criterion_number": 2, "score": 2},
                        ],
                    }
                ]
            }
        }
        scores, total, level = extract_scores(parsed)
        assert scores["s1_c1"] == 3
        assert scores["s1_c2"] == 2
        assert total == 5

    def test_level_from_points(self):
        from pipeline.llm import _level_from_points

        assert _level_from_points(0) == 1
        assert _level_from_points(18) == 1   # <=25%
        assert _level_from_points(30) == 2   # <=50%
        assert _level_from_points(50) == 3   # <=75%
        assert _level_from_points(70) == 4   # >75%
