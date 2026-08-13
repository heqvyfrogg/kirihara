# tests/test_solver.py
import json
import os
from unittest.mock import MagicMock
from kirihara.solver import KiriharaSolver, CACHE_FILE
from kirihara.models import TestQuestionSet, Option, Question, MainQuestion, SubmittedPayload, QuestionAnswer, AnswerResult

def test_build_compact_prompt():
    solver = KiriharaSolver(api_key="mock_key")
    q_set = TestQuestionSet(
        id=108161,
        title="単語テスト",
        bookName="DB3300",
        count=2,
        mainQuestions=[
            MainQuestion(
                id=300733,
                text="日本語の意味に合う英語を選びなさい。",
                type=0,
                questions=[
                    Question(
                        id=2453899,
                        text="（計画・提案など）を拒絶する<br>",
                        options=[
                            Option(id=10237654, text="regret"),
                            Option(id=10237657, text="reject")
                        ]
                    )
                ]
            ),
            MainQuestion(
                id=300776,
                text="正しい語順に並び替えなさい。",
                type=1,
                questions=[
                    Question(
                        id=2453913,
                        text="彼女の試みは成功した。<br>( successful / was / attempt / her ).",
                        options=[
                            Option(id=10237710, text="successful"),
                            Option(id=10237711, text="was"),
                            Option(id=10237712, text="attempt"),
                            Option(id=10237713, text="her")
                        ]
                    )
                ]
            )
        ]
    )
    prompt = solver._build_compact_prompt(q_set)
    assert "2453899" in prompt
    assert "reject" in prompt
    assert "2453913" in prompt
    assert "successful" in prompt

def test_solve_test_mocked_gemini(mocker, tmp_path):
    cache_path = str(tmp_path / "test_cache.json")
    mocker.patch("kirihara.solver.CACHE_FILE", cache_path)
    solver = KiriharaSolver(api_key="mock_key")
    
    # Mock Gemini call
    mock_gemini = mocker.patch.object(
        solver, "_call_gemini",
        return_value={
            "2453899": [10237657],
            "2453913": [10237713, 10237712, 10237711, 10237710]
        }
    )

    q_set = TestQuestionSet(
        id=108161,
        title="単語テスト",
        bookName="DB3300",
        count=2,
        mainQuestions=[
            MainQuestion(
                id=300733,
                text="日本語の意味に合う英語を選びなさい。",
                type=0,
                questions=[
                    Question(
                        id=2453899,
                        text="（計画・提案など）を拒絶する",
                        options=[Option(id=10237654, text="regret"), Option(id=10237657, text="reject")]
                    )
                ]
            ),
            MainQuestion(
                id=300776,
                text="正しい語順に並べなさい。",
                type=1,
                questions=[
                    Question(
                        id=2453913,
                        text="彼女の試みは成功した。",
                        options=[
                            Option(id=10237710, text="successful"),
                            Option(id=10237711, text="was"),
                            Option(id=10237712, text="attempt"),
                            Option(id=10237713, text="her")
                        ]
                    )
                ]
            )
        ]
    )

    payload = solver.solve_test(distribution_id=94506, question_set=q_set, target_accuracy=1.0)
    assert payload.distributionId == 94506
    assert len(payload.testAnswers) == 2
    
    # Single choice answer
    assert payload.testAnswers[0].results[0].id == 10237657
    assert payload.testAnswers[0].results[0].order == 0

    # Ordering answer (orders 1..4)
    assert payload.testAnswers[1].results[0].id == 10237713
    assert payload.testAnswers[1].results[0].order == 1

    # Test format_preview
    preview = solver.format_preview(q_set, payload)
    assert len(preview) == 2
    assert "reject" in preview[0]
    assert "her attempt was successful" in preview[1]

    # Second call should use cache and NOT call Gemini (0 tokens!)
    mock_gemini.reset_mock()
    cached_payload = solver.solve_test(distribution_id=94506, question_set=q_set)
    assert mock_gemini.call_count == 0
    assert len(cached_payload.testAnswers) == 2

    # Third call with no_cache=True should bypass cache and call Gemini
    mock_gemini.reset_mock()
    fresh_payload = solver.solve_test(distribution_id=94506, question_set=q_set, no_cache=True)
    assert mock_gemini.call_count == 1
    assert len(fresh_payload.testAnswers) == 2

def test_solver_model_resolution(monkeypatch):
    # Default model
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    s_default = KiriharaSolver(api_key="mock_key")
    assert s_default.model == "gemini-flash-latest"

    # From env var
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    s_env = KiriharaSolver(api_key="mock_key")
    assert s_env.model == "gemini-3.5-flash"

    # Explicit override
    s_explicit = KiriharaSolver(api_key="mock_key", model="gemini-custom-model")
    assert s_explicit.model == "gemini-custom-model"

def test_clear_cache(tmp_path, monkeypatch):
    test_cache = str(tmp_path / "test_cache.json")
    monkeypatch.setattr("kirihara.solver.CACHE_FILE", test_cache)
    
    solver = KiriharaSolver(api_key="mock_key")
    solver.cache["dummy_key"] = {"1": [100]}
    solver._save_cache()
    assert os.path.exists(test_cache)
    
    cleared = solver.clear_cache()
    assert cleared == 1
    assert solver.cache == {}
    with open(test_cache, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data == {}

