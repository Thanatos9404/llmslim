"""planner_version names the LLMSlim release that made a plan, so it cannot fall behind the planner again.

It was a hand-kept "0.7.0" (and "0.6.0" for plan_context) from 0.7.0 to 0.12.0, while planner output changed. These
checks fail on a release whose plans report any other version.
"""

from __future__ import annotations

import importlib

import pytest

import llmslim
from llmslim import ContextRuntime, plan_context


def test_both_planners_report_the_release_that_made_the_plan():
    plan = plan_context(
        messages=[{"role": "user", "content": "When does Acme renew?"}],
        documents=["Acme renews on 9 November."],
        query="When does Acme renew?",
        max_input_tokens=2000,
        reserve_output_tokens=0,
        safety_margin_tokens=0,
    )
    assert plan.metrics.planner_version == llmslim.__version__
    assert plan.metrics.to_dict()["planner_version"] == llmslim.__version__

    prepared = ContextRuntime(
        max_input_tokens=2000, reserve_output_tokens=0, safety_margin_tokens=0
    ).prepare_sync(user_input="When does Acme renew?", documents=("Acme renews on 9 November.",))
    assert prepared.plan.metrics.planner_version == llmslim.__version__
    assert prepared.trace.planner_version == llmslim.__version__
    assert prepared.trace.to_dict()["planner_version"] == llmslim.__version__
    assert prepared.explanation.startswith(f"{llmslim.__version__}: ")


@pytest.mark.parametrize("module", ["llmslim.planning.planner", "llmslim.planning.progressive"])
def test_the_old_constants_still_import_and_name_the_release(module):
    loaded = importlib.import_module(module)
    assert loaded.PLANNER_VERSION == llmslim.__version__
    with pytest.raises(AttributeError):
        loaded.NOT_A_NAME  # noqa: B018
