"""Tests for pyclaw.agents.planner — task plan management."""

from pathlib import Path

from pyclaw.agents.planner import (
    Plan,
    PlanManager,
    PlanStatus,
    Step,
    StepDetector,
    StepProgress,
    StepStatus,
    extract_step_declarations,
    is_continue_intent,
)


class TestPlan:
    def test_create_plan(self) -> None:
        plan = Plan(id="test-1", goal="Build a web app")
        assert plan.status == PlanStatus.PENDING
        assert plan.is_complete is False

    def test_plan_with_steps(self) -> None:
        steps = [
            Step(id=1, description="Setup project"),
            Step(id=2, description="Build frontend"),
            Step(id=3, description="Deploy"),
        ]
        plan = Plan(id="test-2", goal="Full stack app", steps=steps)
        plan.start()
        assert plan.status == PlanStatus.RUNNING
        assert plan.current_step is not None
        assert plan.current_step.id == 1
        assert plan.current_step.status == StepStatus.RUNNING

    def test_advance_step(self) -> None:
        steps = [
            Step(id=1, description="Step 1"),
            Step(id=2, description="Step 2"),
        ]
        plan = Plan(id="test-3", goal="Two steps", steps=steps)
        plan.start()

        has_next = plan.advance_step("Done with step 1")
        assert has_next is True
        assert plan.current_step_index == 1
        assert plan.steps[0].status == StepStatus.COMPLETED
        assert plan.steps[1].status == StepStatus.RUNNING

        has_next = plan.advance_step("Done with step 2")
        assert has_next is False
        assert plan.status == PlanStatus.COMPLETED

    def test_serialization(self) -> None:
        steps = [Step(id=1, description="Test step", progress=StepProgress(current=3, total=10))]
        plan = Plan(id="ser-1", goal="Serialize me", steps=steps)
        d = plan.to_dict()
        restored = Plan.from_dict(d)
        assert restored.id == "ser-1"
        assert restored.goal == "Serialize me"
        assert restored.steps[0].progress.current == 3

    def test_context_string(self) -> None:
        steps = [
            Step(id=1, description="First", status=StepStatus.COMPLETED, result="ok"),
            Step(id=2, description="Second", status=StepStatus.RUNNING),
        ]
        plan = Plan(id="ctx-1", goal="Test context", steps=steps, current_step_index=1)
        ctx = plan.to_context_string()
        assert "Test context" in ctx
        assert "✓" in ctx
        assert "→" in ctx

    def test_progress_summary(self) -> None:
        steps = [
            Step(id=1, description="A", status=StepStatus.COMPLETED),
            Step(id=2, description="B", status=StepStatus.RUNNING),
        ]
        plan = Plan(id="prog-1", goal="Progress test", steps=steps, current_step_index=1)
        summary = plan.generate_progress_summary()
        assert "1/2" in summary
        assert "50%" in summary


class TestStepDetector:
    def test_done_marker(self) -> None:
        detector = StepDetector()
        assert detector.is_step_complete("[done]", 0) is True
        assert detector.is_step_complete("[完成]", 0) is True
        assert detector.is_step_complete("[Step Done]", 0) is True

    def test_transition_words(self) -> None:
        detector = StepDetector()
        assert detector.is_step_complete("Now let's move to the next part", 0) is True
        assert detector.is_step_complete("接下来我们需要", 0) is True

    def test_iteration_timeout(self) -> None:
        detector = StepDetector(max_iterations_per_step=3)
        assert detector.is_step_complete("still working", 2) is False
        assert detector.is_step_complete("still working", 3) is True

    def test_no_completion(self) -> None:
        detector = StepDetector()
        assert detector.is_step_complete("Working on the implementation", 1) is False


class TestStepDeclarations:
    def test_extract_steps(self) -> None:
        text = """
        [Step 1] Setup the database
        [Step 2] Build the API
        [Step 3] Write tests
        """
        steps = extract_step_declarations(text)
        assert len(steps) == 3
        assert steps[0] == "Setup the database"
        assert steps[2] == "Write tests"

    def test_no_steps(self) -> None:
        assert extract_step_declarations("Just some text") == []


class TestContinueIntent:
    def test_continue_messages(self) -> None:
        assert is_continue_intent("继续") is True
        assert is_continue_intent("continue") is True
        assert is_continue_intent("go on") is True
        assert is_continue_intent("proceed") is True

    def test_not_continue(self) -> None:
        assert is_continue_intent("something else") is False
        assert is_continue_intent("继续做别的事情") is False


class TestPlanManager:
    def test_create_and_get(self, tmp_path: Path) -> None:
        mgr = PlanManager(tmp_path)
        plan = mgr.create("plan-1", "Test goal", ["Step A", "Step B"])
        assert len(plan.steps) == 2

        retrieved = mgr.get("plan-1")
        assert retrieved is not None
        assert retrieved.goal == "Test goal"

    def test_persistence(self, tmp_path: Path) -> None:
        mgr1 = PlanManager(tmp_path)
        mgr1.create("persist-1", "Persist test", ["One", "Two"])

        mgr2 = PlanManager(tmp_path)
        loaded = mgr2.get("persist-1")
        assert loaded is not None
        assert loaded.goal == "Persist test"

    def test_delete(self, tmp_path: Path) -> None:
        mgr = PlanManager(tmp_path)
        mgr.create("del-1", "Delete me", ["X"])
        assert mgr.delete("del-1") is True
        assert mgr.get("del-1") is None

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        mgr = PlanManager(tmp_path)
        assert mgr.get("nope") is None
