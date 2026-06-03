"""Tests for ArticleStatus state machine."""
import pytest
from peerpedia_core.workflow.state_machine import (
    StateMachine,
    VALID_TRANSITIONS,
    ArticleStatus,
    transition,
    can_transition,
)


class TestValidTransitions:
    """Valid transitions defined in the state machine."""

    def test_draft_to_submitted(self):
        assert can_transition("draft", "submitted") is True

    def test_submitted_to_in_review(self):
        assert can_transition("submitted", "in_review") is True

    def test_in_review_to_accepted(self):
        assert can_transition("in_review", "accepted") is True

    def test_in_review_to_rejected(self):
        assert can_transition("in_review", "rejected") is True

    def test_in_review_to_revisions_requested(self):
        assert can_transition("in_review", "revisions_requested") is True

    def test_accepted_to_published(self):
        assert can_transition("accepted", "published") is True

    def test_revisions_requested_to_submitted(self):
        assert can_transition("revisions_requested", "submitted") is True

    def test_rejected_to_submitted(self):
        assert can_transition("rejected", "submitted") is True


class TestInvalidTransitions:
    """Invalid transitions should return False."""

    def test_draft_to_published_invalid(self):
        assert can_transition("draft", "published") is False

    def test_draft_to_accepted_invalid(self):
        assert can_transition("draft", "accepted") is False

    def test_submitted_to_published_invalid(self):
        assert can_transition("submitted", "published") is False

    def test_published_to_draft_invalid(self):
        assert can_transition("published", "draft") is False

    def test_rejected_to_accepted_invalid(self):
        assert can_transition("rejected", "accepted") is False


class TestTransitionExecution:
    """transition() should execute valid transitions and raise on invalid."""

    def test_transition_returns_new_status(self):
        result = transition("draft", "submitted")
        assert result == "submitted"

    def test_transition_raises_on_invalid(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            transition("draft", "published")

    def test_full_happy_path(self):
        """draft → submitted → in_review → accepted → published"""
        s = transition("draft", "submitted")
        assert s == "submitted"
        s = transition(s, "in_review")
        assert s == "in_review"
        s = transition(s, "accepted")
        assert s == "accepted"
        s = transition(s, "published")
        assert s == "published"

    def test_revise_loop(self):
        """submitted → in_review → revisions_requested → submitted → in_review → accepted"""
        s = transition("draft", "submitted")
        s = transition(s, "in_review")
        s = transition(s, "revisions_requested")
        assert s == "revisions_requested"
        s = transition(s, "submitted")
        s = transition(s, "in_review")
        s = transition(s, "accepted")
        assert s == "accepted"

    def test_reject_path(self):
        """submitted → in_review → rejected → submitted (resubmit)"""
        s = transition("draft", "submitted")
        s = transition(s, "in_review")
        s = transition(s, "rejected")
        assert s == "rejected"
        s = transition(s, "submitted")  # can resubmit
        assert s == "submitted"


class TestStateMachineClass:
    """StateMachine class wraps an article and tracks its status."""

    def test_sm_apply(self):
        sm = StateMachine(article_id="a1", current_status="draft")
        sm.apply("submitted")
        assert sm.current_status == "submitted"
        assert len(sm.history) == 1
        assert sm.history[0] == ("draft", "submitted")

    def test_sm_can_apply(self):
        sm = StateMachine(article_id="a1", current_status="published")
        assert sm.can_apply("draft") is False
        assert sm.can_apply("submitted") is False
