"""Tests for pyclaw.agents.intent — rule-based intent analyzer."""

import pytest

from pyclaw.agents.intent import IntentAnalyzer, UserIntent


@pytest.fixture
def analyzer() -> IntentAnalyzer:
    return IntentAnalyzer()


class TestStopIntent:
    def test_english_stop(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("stop")
        assert result.intent == UserIntent.STOP
        assert result.is_interrupt is True
        assert result.confidence >= 0.9

    def test_chinese_stop(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("停止")
        assert result.intent == UserIntent.STOP
        assert result.is_interrupt is True

    def test_cancel(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("cancel")
        assert result.intent == UserIntent.STOP

    def test_stop_generating(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("stop generating")
        assert result.intent == UserIntent.STOP

    def test_chinese_enough(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("够了")
        assert result.intent == UserIntent.STOP


class TestCorrectionIntent:
    def test_english_wrong(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("wrong")
        assert result.intent == UserIntent.CORRECTION
        assert result.is_interrupt is True

    def test_chinese_wrong(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("不对")
        assert result.intent == UserIntent.CORRECTION

    def test_actually(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("actually, I want something else")
        assert result.intent == UserIntent.CORRECTION

    def test_wait(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("wait")
        assert result.intent == UserIntent.CORRECTION

    def test_chinese_wait(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("等一下")
        assert result.intent == UserIntent.CORRECTION


class TestAppendIntent:
    def test_english_also(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("also, add the tests")
        assert result.intent == UserIntent.APPEND
        assert result.is_interrupt is False

    def test_chinese_supplement(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("补充一下")
        assert result.intent == UserIntent.APPEND

    def test_by_the_way(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("by the way, check the logs")
        assert result.intent == UserIntent.APPEND

    def test_ps(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("P.S. also fix the typo")
        assert result.intent == UserIntent.APPEND


class TestContinueIntent:
    def test_english_continue(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("continue")
        assert result.intent == UserIntent.CONTINUE
        assert result.is_interrupt is False

    def test_chinese_continue(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("继续")
        assert result.intent == UserIntent.CONTINUE

    def test_go_on(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("go on")
        assert result.intent == UserIntent.CONTINUE


class TestNewTopicIntent:
    def test_normal_message(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("Please write a function that sorts a list")
        assert result.intent == UserIntent.NEW_TOPIC
        assert result.is_interrupt is False

    def test_empty_message(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("")
        assert result.intent == UserIntent.NEW_TOPIC


class TestShortMessageHeuristic:
    def test_short_during_run(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("no", is_agent_running=True)
        assert result.intent == UserIntent.CORRECTION
        assert result.confidence >= 0.5

    def test_short_not_during_run(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("hello world foo bar baz", is_agent_running=False)
        assert result.intent == UserIntent.NEW_TOPIC
