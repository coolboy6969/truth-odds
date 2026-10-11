import re
import json
from typing import Dict, Any, Optional, List
import httpx
from app.config import settings

class LLMPredictionExtractor:
    """
    Extracts structured forecaster statements and predictions from unstructured
    transcripts or social media posts using LLM (Gemini / OpenAI) or smart heuristic fallback.
    """

    SYSTEM_PROMPT = """
You are an expert forecasting analyst and intelligence extractor.
Analyze the following text (transcript, interview, or social media post) and extract any concrete forward-looking predictions, forecasts, or statements made by speakers about future events.

Output a strict JSON array of objects with the following schema:
[
  {
    "speaker_name": "Full name of the speaker",
    "event_hypothesis": "Clear, verifiable statement of the event (e.g., 'Bitcoin reaches $150,000 before 2026-12-31')",
    "domain": "One of: crypto, macro, tech, geopolitics, markets, science, general",
    "speaker_confidence": 0.85, // Estimated probability between 0.01 and 0.99 that the speaker assigns to this event
    "deadline_str": "YYYY-MM-DD or timeframe (e.g., 'end of 2026', 'next month')",
    "raw_quote": "Exact direct quote where the speaker makes this claim",
    "reasoning": "Brief explanation of why this probability was assigned based on speaker's tone and qualifiers"
  }
]

Guidelines:
- If the speaker says "I'm 100% sure", map to 0.95 (calibration upper bound).
- If the speaker says "Very likely", map to ~0.80.
- If "50/50 / maybe", map to 0.50.
- If "Highly unlikely / won't happen", map to 0.10 - 0.20.
- If no clear forward-looking predictions are made, return an empty array [].
"""

    @classmethod
    async def extract_predictions(
        cls, 
        text: str, 
        default_speaker: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs LLM extraction if an API key is set, otherwise falls back to smart local heuristic.
        """
        # If Gemini API Key is configured
        if settings.GEMINI_API_KEY:
            try:
                return await cls._extract_with_gemini(text, default_speaker)
            except Exception as e:
                print(f"[Extractor] Gemini API error, falling back to heuristic: {e}")

        # If OpenAI API Key is configured
        if settings.OPENAI_API_KEY:
            try:
                return await cls._extract_with_openai(text, default_speaker)
            except Exception as e:
                print(f"[Extractor] OpenAI API error, falling back to heuristic: {e}")

        # Fallback to local heuristic parser
        return cls._extract_heuristically(text, default_speaker)

    @classmethod
    async def _extract_with_gemini(cls, text: str, default_speaker: Optional[str]) -> List[Dict[str, Any]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        user_msg = f"Speaker context: {default_speaker or 'Unknown'}\n\nContent:\n{text}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{cls.SYSTEM_PROMPT}\n\n{user_msg}"}]}
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_json)

    @classmethod
    async def _extract_with_openai(cls, text: str, default_speaker: Optional[str]) -> List[Dict[str, Any]]:
        url = "https://api.openai.com/v1/chat/completions"
        user_msg = f"Speaker context: {default_speaker or 'Unknown'}\n\nContent:\n{text}"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "predictions" in parsed:
                return parsed["predictions"]
            return [parsed]

    @classmethod
    def _extract_heuristically(cls, text: str, default_speaker: Optional[str]) -> List[Dict[str, Any]]:
        """
        Deterministic rule-based extractor for testing and offline execution.
        Recognizes statements, percentages, and epistemic markers.
        """
        speaker = default_speaker or "Спикер / Эксперт"
        predictions = []

        # Look for explicit percentage mentions (e.g. "80%", "вероятность 70%", "chance 90%")
        pct_matches = re.finditer(r'([^.!?\n]*?(\b(\d{1,2})\s*%\b)[^.!?\n]*)', text, re.IGNORECASE)
        found = False
        for m in pct_matches:
            sentence = m.group(1).strip()
            val = float(m.group(3)) / 100.0
            if 0.05 <= val <= 0.95:
                domain = cls._guess_domain(sentence)
                predictions.append({
                    "speaker_name": speaker,
                    "event_hypothesis": sentence[:150],
                    "domain": domain,
                    "speaker_confidence": round(val, 2),
                    "deadline_str": "в течение года",
                    "raw_quote": sentence,
                    "reasoning": f"Обнаружено прямое указание вероятности {m.group(2)}"
                })
                found = True

        if found:
            return predictions

        # Look for confidence markers (ru/en), including bearish/skeptical/negated statements
        confidence_rules = [
            (r'(точно|несомненно|гарантирую|definitely|certainly|100%)', 0.90, "Высокая уверенность спикера"),
            (r'(невозможно|этого не будет|абсурд|обнулится|impossible|never)', 0.10, "Категорическое отрицание события"),
            (r'(маловероятно|сомневаюсь|вряд ли|unlikely|doubtful|скептически)', 0.24, "Низкая вероятность события"),
            (r'(\bне\s+(?:достигнет|войдет|превысит|пробьет|вырастет|сможет|будет)|будет\s+ниже|рухнет|обвалится|упадет\s+ниже)', 0.28, "Медвежий или отрицающий сценарий с повышенным скепсисом рынка"),
            (r'(сократит|замедление|коррекция|рецессия|девальваци|комнат\w*\s+ожидания|риск)', 0.42, "Осторожная / сдержанная оценка с балансом рисков ниже 50%"),
            (r'(скорее всего|вероятно|ожидаю|высокие шансы|probably|likely|expect)', 0.72, "Умеренно-высокая вероятность"),
            (r'(возможно|может быть|не исключено|maybe|perhaps|possible)', 0.48, "Дискуссионная / неопределенная оценка"),
        ]

        sentences = [s.strip() for s in re.split(r'[.!?\n]+', text) if len(s.strip()) > 20]
        for s in sentences:
            for pattern, conf, reason in confidence_rules:
                if re.search(pattern, s, re.IGNORECASE):
                    domain = cls._guess_domain(s)
                    predictions.append({
                        "speaker_name": speaker,
                        "event_hypothesis": s[:150],
                        "domain": domain,
                        "speaker_confidence": conf,
                        "deadline_str": "в обозримом будущем",
                        "raw_quote": s,
                        "reasoning": reason
                    })
                    break  # Match only strongest rule per sentence
            if len(predictions) >= 3:
                break

        # If nothing matched, construct a parsed item with calibrated confidence
        if not predictions and len(text.strip()) > 10:
            domain = cls._guess_domain(text)
            first_sent = sentences[0] if sentences else text.strip()
            default_conf = 0.45 if re.search(r'(\bне\s+|ниже|сократ|спад|коррекц|упад|риск)', first_sent, re.IGNORECASE) else 0.58
            predictions.append({
                "speaker_name": speaker,
                "event_hypothesis": first_sent[:150],
                "domain": domain,
                "speaker_confidence": default_conf,
                "deadline_str": "уточняется",
                "raw_quote": first_sent[:200],
                "reasoning": "Калиброванная базовая оценка по контексту заявления"
            })

        return predictions

    @staticmethod
    def _guess_domain(text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["bitcoin", "биткоин", "крипт", "crypto", "btc", "eth", "блокчейн", "solana"]):
            return "crypto"
        if any(w in text_lower for w in ["фрс", "ставка", "инфляци", "рынок", "s&p", "доллар", "fed", "inflation", "economy", "dollar"]):
            return "macro"
        if any(w in text_lower for w in ["ai", "ии", "нейросеть", "agi", "робот", "технолог", "tesla", "openai", "chip"]):
            return "tech"
        if any(w in text_lower for w in ["выборы", "президент", "война", "мир", "переговоры", "санкции", "election", "war", "treaty"]):
            return "geopolitics"
        return "general"
