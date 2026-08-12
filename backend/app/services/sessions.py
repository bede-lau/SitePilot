from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ConversationSession


async def get_or_create_session(db: AsyncSession, phone_number: str) -> ConversationSession:
    result = await db.execute(
        select(ConversationSession).where(ConversationSession.phone_number == phone_number)
    )
    session = result.scalar_one_or_none()
    if session is None:
        session = ConversationSession(phone_number=phone_number, state="idle", context={})
        db.add(session)
        await db.commit()
        await db.refresh(session)
    return session
