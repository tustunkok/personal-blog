from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Fingerprint, Reaction


class ReactionService:
    REACTION_TYPES = ["like", "clap", "bookmark", "insightful", "mind-blown"]

    def __init__(self, db: Session):
        self.db = db

    def add_reaction(
        self,
        post_id: int,
        reaction_type: str,
        ip: str | None = None,
        user_agent: str | None = None,
        fingerprint: str | None = None,
        scroll_position: float | None = None,
        time_to_react: float | None = None,
    ) -> Reaction | None:
        if reaction_type not in self.REACTION_TYPES:
            return None

        fingerprint_id = None
        if fingerprint:
            existing = (
                self.db.query(Reaction)
                .filter(
                    Reaction.post_id == post_id,
                    Reaction.reaction_type == reaction_type,
                    Reaction.fingerprint_hash == fingerprint,
                )
                .first()
            )
            if existing:
                return None

            fp = (
                self.db.query(Fingerprint)
                .filter(Fingerprint.hash == fingerprint)
                .first()
            )
            if fp:
                fingerprint_id = fp.id

        reaction = Reaction(
            post_id=post_id,
            reaction_type=reaction_type,
            fingerprint_id=fingerprint_id,
            fingerprint_hash=fingerprint,
            ip=ip,
            user_agent=user_agent,
            scroll_position=scroll_position,
            time_to_react=time_to_react,
        )
        self.db.add(reaction)
        self.db.commit()
        self.db.refresh(reaction)
        return reaction

    def get_counts(self, post_id: int) -> dict[str, int]:
        counts: dict[str, int] = {}
        rows = (
            self.db.query(Reaction.reaction_type, func.count(Reaction.id))
            .filter(Reaction.post_id == post_id)
            .group_by(Reaction.reaction_type)
            .all()
        )
        for rtype, count in rows:
            counts[rtype] = count
        for rtype in self.REACTION_TYPES:
            if rtype not in counts:
                counts[rtype] = 0
        return counts
