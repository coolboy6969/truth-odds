import re
import html
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from app.models.entities import DiscoveredSpeakerCandidate, Speaker, Statement, Event
from app.services.prediction_service import PredictionService
from app.extractor.llm_extractor import LLMPredictionExtractor
from app.engine.auto_analysis import AutoEventAnalysisEngine
from app.engine.scoring import ForecasterScorer
from app.oracles.auto_oracle import AutoOracleService
from app.discovery.speaker_discovery import is_valid_analyst_name, STOP_WORDS, normalize_analyst_url


class RealWorldAnalystDiscoveryService:
    """
    Autonomous real-world discovery service that scans open global news feeds,
    crypto/macro media (Cointelegraph, Google News RSS, etc.), extracts real analysts,
    their concrete predictions, target numbers, and records them with direct source attribution.
    """

    NON_PERSON_WORDS = STOP_WORDS

    VERBS_REGEX = (
        r'(?:says|predicts|warns|forecasts|praises|bets|apologizes|sees|expects|calls|targets|notes|'
        r'believes|argues|claims|points out|заявил|заявила|спрогнозировал|предсказал|предупредил|'
        r'призвал|считает|ожидает|отметил|отметила|уверен|уверена)'
    )
    TITLES_REGEX = (
        r'(?:analyst|expert|economist|investor|trader|strategist|billionaire|'
        r'аналитик|эксперт|экономист|инвестор|трейдер|стратег|миллиардер)'
    )

    PATTERNS = [
        rf'{TITLES_REGEX}\s+([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)\s+(?:{VERBS_REGEX}|:)',
        rf'{TITLES_REGEX}\s+([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)',
        rf'([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)\s*:\s*',
        rf'([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)\s+{VERBS_REGEX}',
        r'(?:interview with|discussion with|talking to|ft\.|feat\.|интервью с|беседа с)\s+([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)'
    ]

    @classmethod
    def clean_extracted_name(cls, raw_name: str) -> Optional[str]:
        if not raw_name:
            return None
        cleaned = raw_name.strip()
        leading_pattern = r'^(?:analyst|expert|economist|trader|investor|аналитик|эксперт|трейдер|инвестор|for|для)\s+'
        while re.search(leading_pattern, cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(leading_pattern, '', cleaned, flags=re.IGNORECASE).strip()

        trailing_pattern = r'\s+(?:on|in|for|who|at|by|says|predicts|warns|на|в|для|кто|заявил|считает|о)$'
        while re.search(trailing_pattern, cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(trailing_pattern, '', cleaned, flags=re.IGNORECASE).strip()

        if not is_valid_analyst_name(cleaned):
            return None

        words = cleaned.split()
        return " ".join(w.capitalize() for w in words)

    @classmethod
    def extract_speaker_from_text(cls, text: str, default_hint: Optional[str] = None) -> Optional[str]:
        if default_hint:
            cleaned_hint = cls.clean_extracted_name(default_hint)
            if cleaned_hint and cleaned_hint.lower() in text.lower():
                return cleaned_hint

        for pattern in cls.PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = cls.clean_extracted_name(match.group(1))
                if candidate:
                    return candidate

        return cls.clean_extracted_name(default_hint) if default_hint else None

    @classmethod
    async def fetch_google_news(cls, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetches live news articles via open Google News RSS feeds.
        Automatically switches locale to Russian if query contains Cyrillic.
        """
        is_cyrillic = bool(re.search(r'[а-яё]', query, re.IGNORECASE))
        if is_cyrillic:
            encoded = urllib.parse.quote(query)
            feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=ru&gl=RU&ceid=RU:ru"
        else:
            encoded = urllib.parse.quote(query)
            feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

        articles = []
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(feed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    items = root.findall('.//item')
                    for it in items[:limit]:
                        raw_title = it.findtext('title') or ''
                        publisher = ""
                        title = raw_title
                        if " - " in raw_title:
                            parts = raw_title.rsplit(" - ", 1)
                            title = parts[0].strip()
                            publisher = parts[1].strip()

                        raw_desc = it.findtext('description') or ''
                        clean_desc = re.sub(r'<[^>]+>', ' ', html.unescape(raw_desc)).strip()
                        link = it.findtext('link') or ""
                        pub_date = it.findtext('pubDate') or ""

                        articles.append({
                            "title": title,
                            "publisher": publisher or "Google News",
                            "description": clean_desc,
                            "url": link,
                            "published_at": pub_date,
                            "source": "google_news"
                        })
        except Exception as e:
            print(f"[Discovery] Error fetching Google News for '{query}': {e}")

        return articles

    @classmethod
    async def fetch_cointelegraph(cls, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetches live crypto articles directly from Cointelegraph RSS feed.
        """
        feed_url = "https://cointelegraph.com/rss"
        articles = []
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(feed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    items = root.findall('.//item')
                    for it in items[:limit]:
                        title = it.findtext('title') or ''
                        raw_desc = it.findtext('description') or ''
                        clean_desc = re.sub(r'<[^>]+>', ' ', html.unescape(raw_desc)).strip()
                        link = it.findtext('link') or ""
                        pub_date = it.findtext('pubDate') or ""

                        articles.append({
                            "title": title,
                            "publisher": "Cointelegraph",
                            "description": clean_desc,
                            "url": link,
                            "published_at": pub_date,
                            "source": "cointelegraph"
                        })
        except Exception as e:
            print(f"[Discovery] Error fetching Cointelegraph feed: {e}")

        return articles

    @classmethod
    async def search_real_world(
        cls,
        query: str,
        db: Session,
        limit: int = 15,
        auto_record: bool = False
    ) -> Dict[str, Any]:
        """
        Conducts a real-world search for an analyst or a forecasting topic.
        Extracts real articles, identifies speakers and concrete statements,
        and records candidates or official forecasts into the database.
        """
        query_clean = query.strip()
        if not query_clean:
            return {"success": False, "error": "Пустой поисковый запрос", "candidates": []}

        # Check if query is likely a person name
        is_person_query = is_valid_analyst_name(query_clean)
        speaker_hint = cls.clean_extracted_name(query_clean) if is_person_query else None

        # Build search query for media
        if is_person_query:
            search_query = f"{query_clean} predicts OR forecasts OR says OR прогноз"
        else:
            search_query = f"{query_clean} analyst predicts OR forecast OR прогноз"

        articles = await cls.fetch_google_news(search_query, limit=limit)

        # Also search Cointelegraph if crypto related or empty
        if len(articles) < 5 or any(w in query_clean.lower() for w in ["bitcoin", "crypto", "биткоин", "крипта", "eth", "sol"]):
            ct_articles = await cls.fetch_cointelegraph(limit=10)
            # Filter relevant
            ct_matched = [
                a for a in ct_articles
                if any(w.lower() in (a['title'] + " " + a['description']).lower() for w in query_clean.split())
            ]
            articles.extend(ct_matched)

        if not articles:
            return {
                "success": True,
                "query": query_clean,
                "total_articles": 0,
                "candidates_found": 0,
                "candidates": [],
                "message": "По вашему запросу не найдено свежих публикаций в мировых медиа."
            }

        # Process articles and extract claims
        return await cls._process_articles_and_register(
            articles=articles,
            db=db,
            speaker_hint=speaker_hint,
            auto_record=auto_record
        )

    @classmethod
    async def scan_live_media(
        cls,
        db: Session,
        max_articles: int = 30,
        auto_record: bool = False
    ) -> Dict[str, Any]:
        """
        Performs a full sweep across global financial and crypto media streams
        to autonomously uncover real analysts making predictions right now.
        """
        all_articles = []

        # 1. Cointelegraph fresh stream
        ct_articles = await cls.fetch_cointelegraph(limit=15)
        all_articles.extend(ct_articles)

        # 2. Google News: Crypto analysts
        gn_crypto = await cls.fetch_google_news("cryptocurrency analyst predicts OR forecasts", limit=15)
        all_articles.extend(gn_crypto)

        # 3. Google News: Macro analysts
        gn_macro = await cls.fetch_google_news("Wall Street economist predicts recession OR inflation OR Fed", limit=10)
        all_articles.extend(gn_macro)

        # 4. Google News: Russian crypto & macro forecasts
        gn_ru = await cls.fetch_google_news("аналитик спрогнозировал курс биткоина или доллара", limit=10)
        all_articles.extend(gn_ru)

        # Deduplicate articles by title
        seen_titles = set()
        unique_articles = []
        for art in all_articles:
            norm_title = re.sub(r'\W+', '', art['title'].lower())
            if norm_title not in seen_titles:
                seen_titles.add(norm_title)
                unique_articles.append(art)

        trimmed = unique_articles[:max_articles]
        return await cls._process_articles_and_register(
            articles=trimmed,
            db=db,
            speaker_hint=None,
            auto_record=auto_record
        )

    @classmethod
    async def _process_articles_and_register(
        cls,
        articles: List[Dict[str, Any]],
        db: Session,
        speaker_hint: Optional[str] = None,
        auto_record: bool = False
    ) -> Dict[str, Any]:
        discovered_candidates = {}
        total_claims_found = 0

        for art in articles:
            combined_text = f"{art['title']}. {art['description']}"
            speaker_name = cls.extract_speaker_from_text(art['title'], default_hint=speaker_hint)
            if not speaker_name:
                speaker_name = cls.extract_speaker_from_text(combined_text, default_hint=speaker_hint)

            if not speaker_name or not is_valid_analyst_name(speaker_name):
                continue

            # Extract concrete predictions from text
            predictions = await LLMPredictionExtractor.extract_predictions(
                combined_text,
                default_speaker=speaker_name
            )

            # Ensure domain inference is refined
            inferred_domain = AutoEventAnalysisEngine.infer_domain(art['title'])

            for pred in predictions:
                pred['domain'] = inferred_domain
                pred['source_url'] = art['url']
                pred['publisher'] = art['publisher']
                pred['published_at'] = art['published_at']

            total_claims_found += len(predictions)

            clean_url = (art.get('url') or '').strip()
            norm_url = normalize_analyst_url(clean_url)

            # Register or update in DiscoveredSpeakerCandidate with strict deduplication
            cand = db.query(DiscoveredSpeakerCandidate).filter(
                DiscoveredSpeakerCandidate.name.ilike(speaker_name)
            ).first()

            # If URLs repeat, it is the exact same analyst: match by normalized source_url
            if not cand and norm_url:
                for c in db.query(DiscoveredSpeakerCandidate).all():
                    if c.source_url and normalize_analyst_url(c.source_url) == norm_url:
                        cand = c
                        break

            quote_snippet = f"[{art['publisher']}] «{art['title']}»"

            if cand:
                cand.mention_count += 1
                cand.claim_density_score = min(1.0, cand.claim_density_score + 0.1)
                if clean_url and not cand.source_url:
                    cand.source_url = clean_url
                if not cand.context_quote or len(cand.context_quote) < 30:
                    cand.context_quote = quote_snippet

                # Append extracted predictions safely and deduplicate by hypothesis
                existing_preds = cand.extracted_predictions or []
                if isinstance(existing_preds, list):
                    existing_hyps = {p.get('event_hypothesis', '').lower().strip() for p in existing_preds if p.get('event_hypothesis')}
                    for p in predictions:
                        hyp = (p.get('event_hypothesis') or '').lower().strip()
                        if hyp and hyp not in existing_hyps:
                            existing_preds.append(p)
                            existing_hyps.add(hyp)
                    cand.extracted_predictions = existing_preds[:10]
            else:
                cand = DiscoveredSpeakerCandidate(
                    name=speaker_name,
                    discovered_via_channel=art['publisher'] or "Мировые медиа",
                    context_quote=quote_snippet,
                    source_url=clean_url or None,
                    mention_count=1,
                    claim_density_score=0.75 if predictions else 0.50,
                    status="CANDIDATE",
                    extracted_predictions=predictions[:10]
                )
                db.add(cand)

            db.commit()
            db.refresh(cand)

            if auto_record and cand.status == "CANDIDATE":
                cls.approve_and_record_claims(db, cand.id)

            discovered_candidates[cand.name] = {
                "id": cand.id,
                "name": cand.name,
                "channel": cand.discovered_via_channel,
                "mentions": cand.mention_count,
                "score": cand.claim_density_score,
                "context_quote": cand.context_quote,
                "source_url": cand.source_url,
                "status": cand.status,
                "claims_count": len(cand.extracted_predictions or [])
            }

        return {
            "success": True,
            "total_articles": len(articles),
            "candidates_found": len(discovered_candidates),
            "total_claims_found": total_claims_found,
            "candidates": list(discovered_candidates.values())
        }

    @classmethod
    def approve_and_record_claims(cls, db: Session, candidate_id: str) -> Dict[str, Any]:
        """
        Approves a candidate forecaster, turns them into an accepted Speaker,
        and automatically converts all their discovered real-world statements into official
        TruthOdds statements, recalculating the Bayesian probability for events!
        """
        candidate = db.query(DiscoveredSpeakerCandidate).filter(
            DiscoveredSpeakerCandidate.id == candidate_id
        ).first()

        if not candidate:
            return {"success": False, "error": "Кандидат не найден"}

        # 1. Create or get Speaker
        speaker = PredictionService.get_or_create_speaker(
            db=db,
            name=candidate.name,
            handle_or_channel=f"Мировые медиа ({candidate.discovered_via_channel})"
        )
        speaker.bio = f"Найден в медиа. Источники: {candidate.discovered_via_channel} (упоминаний: {candidate.mention_count})"

        candidate.status = "APPROVED"
        db.commit()

        # 2. Convert extracted predictions into real Statements
        predictions = candidate.extracted_predictions or []
        recorded_statements = []

        # If no structured predictions, create a statement from context quote if informative
        if not predictions and candidate.context_quote:
            predictions = [{
                "event_hypothesis": candidate.context_quote.split('»')[0].replace('[', '').replace(']', '').strip()[:180],
                "domain": AutoEventAnalysisEngine.infer_domain(candidate.context_quote),
                "speaker_confidence": 0.75,
                "raw_quote": candidate.context_quote,
                "source_url": candidate.source_url or "https://news.google.com"
            }]

        for pred in predictions:
            hypothesis = pred.get("event_hypothesis")
            if not hypothesis:
                continue

            conf = float(pred.get("speaker_confidence") or 0.70)
            raw_quote = pred.get("raw_quote") or candidate.context_quote or hypothesis
            src_url = pred.get("source_url") or candidate.source_url or "https://news.google.com"
            dom = pred.get("domain") or AutoEventAnalysisEngine.infer_domain(hypothesis)

            stmt = PredictionService.record_statement(
                db=db,
                speaker_name=speaker.name,
                event_title=hypothesis,
                speaker_confidence=conf,
                raw_quote=raw_quote,
                source_url=src_url,
                source_platform="media",
                event_domain=dom,
                base_rate=0.5
            )
            recorded_statements.append({
                "statement_id": stmt.id,
                "event": hypothesis,
                "confidence": conf
            })

        # Run AutoOracle spot check for any crypto price targets
        try:
            AutoOracleService.check_all_active_events(db=db, auto_resolve=False)
        except Exception as e:
            print(f"[Discovery] Oracle check error: {e}")

        db.commit()
        db.refresh(speaker)

        return {
            "success": True,
            "speaker_id": speaker.id,
            "speaker_name": speaker.name,
            "statements_recorded": len(recorded_statements),
            "statements": recorded_statements
        }
