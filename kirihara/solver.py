import json
import os
import re
import random
from typing import Dict, List, Any, Optional, Tuple
from kirihara.models import (
    TestQuestionSet, SubmittedPayload, QuestionAnswer,
    AnswerResult, Question, MainQuestion
)
from kirihara.utils import clean_html

CACHE_FILE = "kirihara_cache.json"

class KiriharaSolver:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
        self.cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        target_file = CACHE_FILE
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        target_file = CACHE_FILE
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _build_compact_prompt(self, question_set: TestQuestionSet) -> str:
        """Construct a minimal-token prompt for batch solving English & Classical Japanese (古文)."""
        lines = [
            f"Subject: {question_set.bookName} / {question_set.title}",
            "Task: Solve all questions accurately (English vocabulary/grammar or Classical Japanese 古文単語/古文文法).",
            "Return ONLY a valid JSON object: {\"<question_id>\": [<chosen_choice_id(s)>]}",
            "Rules:",
            "1. For multiple-choice / fill-in-the-blank / listening / translation: return [chosen_choice_id]",
            "2. For word ordering / rearrangement (type=1): return list of choice_ids in exact 1st-to-last order sequence",
            "Questions:"
        ]
        for mq in question_set.mainQuestions:
            q_type_str = "Ordering" if mq.type == 1 else "Multiple Choice"
            lines.append(f"\n[Section: {clean_html(mq.text)} ({q_type_str})]")
            for q in mq.questions:
                q_text = clean_html(q.text)
                if q.audioUrl:
                    m = re.search(r'Level_\d+_(\d+)_e\.mp3', q.audioUrl)
                    if m:
                        q_text += f" (Audio word #{m.group(1)})"
                options_str = " | ".join([f"{opt.id}:{clean_html(opt.text)}" for opt in q.options])
                lines.append(f"Q#{q.id}: {q_text} -> Options: [{options_str}]")
        return "\n".join(lines)

    def _call_gemini(self, prompt: str) -> Dict[str, List[int]]:
        """Call Gemini API using google-genai SDK."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or .env file.")

        from google import genai
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        text = response.text.strip()
        return json.loads(text)

    def solve_test(
        self,
        distribution_id: int,
        question_set: TestQuestionSet,
        target_accuracy: float = 1.0
    ) -> SubmittedPayload:
        """Solve all questions in test, using local cache first to save tokens."""
        cache_key = f"test_set_{question_set.id}"
        solved_map = self.cache.get(cache_key)

        if not solved_map:
            prompt = self._build_compact_prompt(question_set)
            solved_map = self._call_gemini(prompt)
            self.cache[cache_key] = solved_map
            self._save_cache()

        test_answers: List[QuestionAnswer] = []

        for mq in question_set.mainQuestions:
            for q in mq.questions:
                q_id_str = str(q.id)
                chosen_ids = solved_map.get(q_id_str, [])

                # Accuracy control (intentionally pick wrong answer if rolled)
                if target_accuracy < 1.0 and random.random() > target_accuracy and len(q.options) > 1:
                    wrong_opts = [opt.id for opt in q.options if opt.id not in chosen_ids]
                    if wrong_opts:
                        chosen_ids = [random.choice(wrong_opts)]

                if not chosen_ids and q.options:
                    chosen_ids = [q.options[0].id]

                if mq.type == 1:
                    # Ordering: order starts at 1
                    results = [AnswerResult(id=cid, order=idx+1) for idx, cid in enumerate(chosen_ids)]
                else:
                    # Single choice: order is 0
                    results = [AnswerResult(id=chosen_ids[0], order=0)]

                test_answers.append(QuestionAnswer(testQuestionId=q.id, results=results))

        return SubmittedPayload(distributionId=distribution_id, testAnswers=test_answers)

    def format_preview(self, question_set: TestQuestionSet, payload: SubmittedPayload) -> List[str]:
        """Generate human-readable preview lines with question text and chosen answer labels."""
        lines = []
        # Build lookup for questions and options
        q_map = {}
        for mq in question_set.mainQuestions:
            for q in mq.questions:
                opt_map = {opt.id: clean_html(opt.text) for opt in q.options}
                q_map[q.id] = (clean_html(q.text), opt_map, mq.type)

        for ans in payload.testAnswers:
            q_id = ans.testQuestionId
            q_info = q_map.get(q_id)
            if not q_info:
                res_str = ", ".join([f"ID:{r.id}" for r in ans.results])
                lines.append(f"Q#{q_id}: {res_str}")
                continue

            q_text, opt_map, q_type = q_info
            if q_type == 1:
                # Ordering
                sorted_results = sorted(ans.results, key=lambda r: r.order)
                words = [opt_map.get(r.id, str(r.id)) for r in sorted_results]
                sentence = " ".join(words)
                lines.append(f"Q#{q_id} [並び替え]: {q_text}\n    -> 完成文: 「{sentence}」")
            else:
                chosen_id = ans.results[0].id if ans.results else None
                chosen_text = opt_map.get(chosen_id, str(chosen_id))
                lines.append(f"Q#{q_id}: {q_text} -> 選択解答: 【 {chosen_text} 】 (ID: {chosen_id})")

        return lines
