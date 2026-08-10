# tests/test_models.py
from kirihara.models import (
    Option, Question, MainQuestion, TestQuestionSet,
    SubmittedPayload, QuestionAnswer, AnswerResult,
    UserInfo, TestItem
)

def test_question_set_parsing():
    raw_json = {
        "id": 108161,
        "title": "8月10日（月）単語テスト",
        "bookName": "データベース3300 基本英単語・熟語",
        "count": 1,
        "mainQuestions": [
            {
                "id": 300733,
                "text": "日本語の意味に合う英語を選びなさい。",
                "type": 0,
                "questions": [
                    {
                        "id": 2453899,
                        "text": "（計画・提案など）を拒絶する<br>",
                        "audioUrl": None,
                        "imageUrl": None,
                        "answerCount": 1,
                        "options": [
                            {"id": 10237654, "text": "regret"},
                            {"id": 10237657, "text": "reject"}
                        ]
                    }
                ]
            }
        ]
    }
    q_set = TestQuestionSet.model_validate(raw_json)
    assert q_set.id == 108161
    assert len(q_set.mainQuestions) == 1
    assert q_set.mainQuestions[0].questions[0].options[1].text == "reject"

def test_submitted_payload_serialization():
    payload = SubmittedPayload(
        distributionId=94506,
        testAnswers=[
            QuestionAnswer(
                testQuestionId=2453899,
                results=[AnswerResult(id=10237657, order=0)]
            ),
            QuestionAnswer(
                testQuestionId=2453913,
                results=[
                    AnswerResult(id=10237713, order=1),
                    AnswerResult(id=10237712, order=2)
                ]
            )
        ]
    )
    dumped = payload.model_dump()
    assert dumped["distributionId"] == 94506
    assert dumped["testAnswers"][0]["results"][0]["id"] == 10237657
    assert dumped["testAnswers"][1]["results"][1]["order"] == 2
