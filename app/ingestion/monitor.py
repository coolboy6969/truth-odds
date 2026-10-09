import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from app.models.entities import MonitoredSource, Speaker
from app.services.prediction_service import PredictionService

class YouTubeChannelMonitor:
    """
    Monitors YouTube channels for new videos using public XML feeds without API quotas.
    Feeds: https://www.youtube.com/feeds/videos.xml?channel_id=...
    """

    ATOM_NS = {
        'atom': 'http://www.w3.org/2005/Atom',
        'yt': 'http://www.youtube.com/xml/schemas/2015',
        'media': 'http://search.yahoo.com/mrss/'
    }

    @classmethod
    async def fetch_latest_videos(cls, channel_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fetches recent videos from a YouTube channel via RSS.
        """
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        videos = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    return []
                
                root = ET.fromstring(resp.text)
                entries = root.findall('atom:entry', cls.ATOM_NS)

                for entry in entries[:limit]:
                    vid_elem = entry.find('yt:videoId', cls.ATOM_NS)
                    title_elem = entry.find('atom:title', cls.ATOM_NS)
                    link_elem = entry.find('atom:link', cls.ATOM_NS)
                    published_elem = entry.find('atom:published', cls.ATOM_NS)

                    if vid_elem is not None and title_elem is not None:
                        video_id = vid_elem.text
                        videos.append({
                            "video_id": video_id,
                            "title": title_elem.text,
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "published_at": published_elem.text if published_elem is not None else None
                        })
        except Exception as e:
            print(f"[Monitor] Error fetching feed for channel {channel_id}: {e}")

        return videos

    @classmethod
    async def scan_monitored_source(cls, db: Session, source_id: str) -> Dict[str, Any]:
        """
        Scans a specific monitored source, fetches latest video transcripts,
        and extracts any predictions into TruthOdds.
        """
        source = db.query(MonitoredSource).filter(MonitoredSource.id == source_id).first()
        if not source:
            return {"success": False, "error": "Source not found"}

        speaker = db.query(Speaker).filter(Speaker.id == source.speaker_id).first() if source.speaker_id else None
        speaker_name = speaker.name if speaker else source.channel_title

        videos = await cls.fetch_latest_videos(source.channel_identifier, limit=2)
        if not videos:
            return {
                "success": False,
                "channel": source.channel_title,
                "message": "No new videos found or feed unreachable"
            }

        processed = []
        for vid in videos:
            res = await PredictionService.process_media_or_text(
                db=db,
                text_or_url=vid["url"],
                speaker_name=speaker_name,
                source_platform=source.platform
            )
            processed.append({
                "video_title": vid["title"],
                "url": vid["url"],
                "claims_found": res.get("count", 0)
            })

        source.last_scanned_at = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "channel": source.channel_title,
            "videos_scanned": len(processed),
            "results": processed
        }
