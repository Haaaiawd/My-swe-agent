"""Unit tests for Observer.

Covers: submission marker detection (returncode==0 vs !=0), ANSI stripping,
Unicode normalization, template rendering, fallback on render failure.
"""

from __future__ import annotations

from core.models import ExecutionResult
from core.observer import SUBMISSION_MARKER, observe_result


class MockRenderer:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def render(self, template: str, context: dict) -> str:
        if self.should_fail:
            raise RuntimeError("render failed")
        return context.get("stdout", "")


class TestObserveResult:
    def test_submission_detected(self):
        raw = f"{SUBMISSION_MARKER}\nmy patch content"
        result = ExecutionResult(returncode=0, stdout=raw, stderr="", stdout_original=raw)
        obs = observe_result(result, {})
        assert obs.submitted is True
        assert obs.submission_text == "my patch content"

    def test_submission_rejected_on_nonzero_returncode(self):
        raw = f"{SUBMISSION_MARKER}\nmy patch"
        result = ExecutionResult(returncode=1, stdout=raw, stderr="", stdout_original=raw)
        obs = observe_result(result, {})
        assert obs.submitted is False

    def test_ansi_stripped(self):
        raw = f"\x1b[32m{SUBMISSION_MARKER}\x1b[0m\nok"
        result = ExecutionResult(returncode=0, stdout=raw, stderr="", stdout_original=raw)
        obs = observe_result(result, {})
        assert obs.submitted is True

    def test_unicode_normalize(self):
        # e with combining acute -> NFC precomposed e-acute
        raw = "COMPLETE\u0041\u0301TASK_AND_SUBMIT_FINAL_OUTPUT"  # not the marker
        result = ExecutionResult(returncode=0, stdout=raw, stderr="", stdout_original=raw)
        obs = observe_result(result, {})
        assert obs.submitted is False

    def test_template_render(self):
        result = ExecutionResult(returncode=0, stdout="hi", stderr="", stdout_original="hi")
        renderer = MockRenderer()
        obs = observe_result(result, {"observation_template": "T"}, template_renderer=renderer)
        assert obs.content == "hi"

    def test_template_fallback(self):
        result = ExecutionResult(returncode=0, stdout="hi", stderr="", stdout_original="orig")
        renderer = MockRenderer(should_fail=True)
        obs = observe_result(result, {"observation_template": "T"}, template_renderer=renderer)
        assert obs.content == "orig"

    def test_no_submission_marker(self):
        result = ExecutionResult(returncode=0, stdout="hello", stderr="", stdout_original="hello")
        obs = observe_result(result, {})
        assert obs.submitted is False
        assert obs.submission_text is None
