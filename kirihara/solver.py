import json
import os
import re
import random
import time
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
        self.last_inference_time: float = 0.0
        self.last_was_cached: bool = False

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

    def clear_cache(self) -> int:
        """Clear all inference cache items and persist empty cache."""
        count = len(self.cache)
        self.cache = {}
        target_file = CACHE_FILE
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return count

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

    def _extract_answers_from_thinking_text(self, text: str, question_set: TestQuestionSet) -> Dict[str, List[int]]:
        """Smart fallback to match choice IDs from LLM reasoning/explanations."""
        import re
        result = {}
        for mq in question_set.mainQuestions:
            is_ordering = (mq.type == 1)
            for q in mq.questions:
                q_id_str = str(q.id)
                opt_ids = [opt.id for opt in q.options]
                if not opt_ids:
                    continue

                # 設問ブロックを切り出し
                block = ""
                m = re.search(r'(?:Q#|question[_\s]*id\s*[:=]?\s*|設問|問)?\b' + str(q.id) + r'\b([\s\S]*?)(?=(?:Q#|question[_\s]*id\s*[:=]?\s*|設問|問)\b\d{4,9}\b|$)', text, re.IGNORECASE)
                if m:
                    block = m.group(1)

                target_text = block if block else text
                found_ids = []

                if is_ordering:
                    opt_pattern = r'\b(' + '|'.join(map(str, opt_ids)) + r')\b'
                    matches = re.findall(opt_pattern, target_text)
                    unique_ordered = []
                    for mid_str in matches:
                        mid = int(mid_str)
                        if mid not in unique_ordered:
                            unique_ordered.append(mid)
                    for oid in opt_ids:
                        if oid not in unique_ordered:
                            unique_ordered.append(oid)
                    found_ids = unique_ordered
                else:
                    opt_pattern = r'\b(' + '|'.join(map(str, opt_ids)) + r')\b'
                    am = re.search(r'(?:Option|Choice|Answer|正解|解答|ChoiceID|ID)[\s:]*\[?' + opt_pattern + r'\]?', target_text, re.IGNORECASE)
                    if am:
                        found_ids = [int(am.group(1))]
                    else:
                        am2 = re.search(opt_pattern, target_text)
                        if am2:
                            found_ids = [int(am2.group(1))]
                        else:
                            for opt in q.options:
                                clean_opt = clean_html(opt.text).strip()
                                if len(clean_opt) >= 2 and clean_opt in target_text:
                                    found_ids = [opt.id]
                                    break

                if found_ids:
                    result[q_id_str] = found_ids
                else:
                    result[q_id_str] = opt_ids if is_ordering else [opt_ids[0]]

        return result

    def _call_gemini(self, prompt: str, question_set: Optional[TestQuestionSet] = None) -> Dict[str, List[int]]:
        """Call Gemini/Gemma API using google-genai SDK or direct REST with robust parsing."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or .env file.")

        import re
        from google import genai
        client = genai.Client(api_key=self.api_key)
        
        config = {
            "temperature": 0.1,
            "max_output_tokens": 8192
        }
        if "gemma" not in self.model.lower():
            config["response_mime_type"] = "application/json"

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )
        text = (response.text or "").strip()
        
        # 1. ```json ... ``` ブロックを探索
        blocks = re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.IGNORECASE)
        if blocks:
            try:
                return json.loads(blocks[-1])
            except Exception:
                pass

        # 2. 直接パース
        try:
            return json.loads(text)
        except Exception:
            pass

        # 3. テキスト中の { ... } を抽出
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass

        # 4. 正規表現によるフォールバック
        extracted = {}
        matches = re.findall(r'(?:Q#|question[_\s]*id\s*[:=]?\s*)?["\']?(\d{4,9})["\']?\s*[:=]\s*\[?(\d+(?:\s*,\s*\d+)*)\]?', text, re.IGNORECASE)
        for q_id, choices_str in matches:
            c_vals = [int(x.strip()) for x in choices_str.split(',') if x.strip().isdigit()]
            if c_vals:
                extracted[q_id] = c_vals

        if extracted:
            return extracted

        # 5. 問題セットとのスマートマッチング抽出
        if question_set:
            smart_extracted = self._extract_answers_from_thinking_text(text, question_set)
            if smart_extracted:
                return smart_extracted

        raise ValueError(f"モデル ({self.model}) からの応答JSONのパースに失敗しました: {text[:150]}")

    def solve_test(
        self,
        distribution_id: int,
        question_set: TestQuestionSet,
        target_accuracy: float = 1.0,
        no_cache: bool = False
    ) -> SubmittedPayload:
        """Solve all questions in test, optionally bypassing local cache."""
        cache_key = f"test_set_{question_set.id}"
        solved_map = None if no_cache else self.cache.get(cache_key)

        if solved_map:
            self.last_was_cached = True
            self.last_inference_time = 0.0
        else:
            self.last_was_cached = False
            t_start = time.time()
            prompt = self._build_compact_prompt(question_set)
            solved_map = self._call_gemini(prompt, question_set)
            self.last_inference_time = time.time() - t_start
            self.cache[cache_key] = solved_map
            self._save_cache()

        self.last_raw_solved_map = solved_map
        self.last_wrong_questions = set()

        test_answers: List[QuestionAnswer] = []

        for mq in question_set.mainQuestions:
            for q in mq.questions:
                q_id_str = str(q.id)
                raw_chosen = solved_map.get(q_id_str, [])
                if not isinstance(raw_chosen, list):
                    raw_chosen = [raw_chosen]
                chosen_ids = list(raw_chosen)

                # Accuracy control (intentionally pick wrong answer if rolled)
                if target_accuracy < 1.0 and random.random() > target_accuracy and len(q.options) > 1:
                    if mq.type == 1:
                        shuffled = list(chosen_ids)
                        random.shuffle(shuffled)
                        if shuffled == chosen_ids and len(shuffled) > 1:
                            shuffled[0], shuffled[1] = shuffled[1], shuffled[0]
                        chosen_ids = shuffled
                        self.last_wrong_questions.add(q.id)
                    else:
                        wrong_opts = [opt.id for opt in q.options if opt.id not in raw_chosen]
                        if wrong_opts:
                            chosen_ids = [random.choice(wrong_opts)]
                            self.last_wrong_questions.add(q.id)

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
        """Generate human-readable preview lines with question text, original AI answer and chosen answer labels."""
        lines = []
        # Build lookup for questions and options
        q_map = {}
        for mq in question_set.mainQuestions:
            for q in mq.questions:
                opt_map = {opt.id: clean_html(opt.text) for opt in q.options}
                q_map[q.id] = (clean_html(q.text), opt_map, mq.type)

        raw_map = getattr(self, "last_raw_solved_map", {}) or {}
        wrong_set = getattr(self, "last_wrong_questions", set()) or set()

        for ans in payload.testAnswers:
            q_id = ans.testQuestionId
            q_info = q_map.get(q_id)
            if not q_info:
                res_str = ", ".join([f"ID:{r.id}" for r in ans.results])
                lines.append(f"Q#{q_id}: {res_str}")
                continue

            q_text, opt_map, q_type = q_info
            is_intentional_wrong = q_id in wrong_set
            raw_chosen = raw_map.get(str(q_id), [])
            if not isinstance(raw_chosen, list):
                raw_chosen = [raw_chosen]

            if q_type == 1:
                # Ordering
                sorted_results = sorted(ans.results, key=lambda r: r.order)
                submitted_words = [opt_map.get(r.id, str(r.id)) for r in sorted_results]
                submitted_sentence = " ".join(submitted_words)

                orig_words = [opt_map.get(cid, str(cid)) for cid in raw_chosen]
                orig_sentence = " ".join(orig_words)

                if is_intentional_wrong:
                    lines.append(f"Q#{q_id} [語順整序] (※正答率調整のため故意の誤答): {q_text}\n    -> [AI正解文]: 「{orig_sentence}」\n    -> [提出予定文]: 「{submitted_sentence}」")
                else:
                    lines.append(f"Q#{q_id} [語順整序] [正解提出]: {q_text}\n    -> 完成文: 「{submitted_sentence}」")
            else:
                chosen_id = ans.results[0].id if ans.results else None
                chosen_text = opt_map.get(chosen_id, str(chosen_id))
                orig_id = raw_chosen[0] if raw_chosen else chosen_id
                orig_text = opt_map.get(orig_id, str(orig_id))

                if is_intentional_wrong:
                    lines.append(f"Q#{q_id} (※正答率調整のため故意の誤答): {q_text}\n    -> [AI正解]: 【 {orig_text} 】 (ID:{orig_id})\n    -> [提出解答(誤答)]: 【 {chosen_text} 】 (ID:{chosen_id})")
                else:
                    lines.append(f"Q#{q_id} [正解提出]: {q_text} -> 【 {chosen_text} 】")

        return lines
