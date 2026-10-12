from backend.app.llm.llm_usage import has_budget


def test_llm_budget_is_based_on_input_and_output_character_estimate():
    assert has_budget(100, "question", "context")
    assert not has_budget(499_995, "question", "context")
