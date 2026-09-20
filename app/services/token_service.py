from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.jwt_service import JWTService
from app.db.models.refresh_token import RefreshToken


class TokenService:
    def __init__(self, db: Session):
        self.db = db

    def store_refresh_token(
        self,
        user_id: str,
        token: str,
        family_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        payload = JWTService.decode_token(token)

        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        record = RefreshToken(
            user_id=user_id,
            jti=payload.get("jti"),
            token_hash=token_hash,
            family_id=family_id,
            expires_at=datetime.fromtimestamp(
                payload.get("exp"),
                tz=timezone.utc,
            ),
            revoked=False,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(record)
        self.db.flush()
        return record

    def get_refresh_token(self, token_hash: str):
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def validate_stored_refresh_token(self, token: str):
        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        record = self.get_refresh_token(token_hash)

        if not record:
            return None

        if record.revoked:
            return None

        if record.expires_at <= datetime.now(timezone.utc):
            return None

        return record

    def revoke_refresh_token_family(self, family_id: str):
        records = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .filter(RefreshToken.revoked.is_(False))
            .all()
        )

        now = datetime.now(timezone.utc)

        for record in records:
            record.revoked = True
            record.revoked_at = now

        self.db.commit()
        return records

    def revoke_refresh_token(self, token_hash: str):
        record = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if record and not record.revoked:
            record.revoked = True
            record.revoked_at = datetime.now(timezone.utc)
            self.db.commit()

        return record

    def rotate_refresh_token(self, token: str):
        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        stored_record = self.get_refresh_token(token_hash)

        if not stored_record:
            return None

        # Reuse of an already-revoked token means the token family
        # may have been compromised. Revoke the entire family.
        if stored_record.revoked:
            family_id = stored_record.family_id

            if family_id:
                self.revoke_refresh_token_family(family_id)

            self.db.commit()
            return None

        if stored_record.expires_at <= datetime.now(timezone.utc):
            return None

        old_record = stored_record

        old_record.revoked = True
        old_record.revoked_at = datetime.now(timezone.utc)
        old_record.last_used_at = datetime.now(timezone.utc)

        new_token = JWTService.create_refresh_token(old_record.user_id)

        new_record = self.store_refresh_token(
            user_id=old_record.user_id,
            token=new_token,
            family_id=old_record.family_id or old_record.jti,
            ip_address=old_record.ip_address,
            user_agent=old_record.user_agent,
        )

        old_record.replaced_by = new_record.jti

        self.db.commit()

        return new_token