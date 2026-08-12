import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ActivityLog, ConversationSession, InspectionReport, Project
from app.services.events import broadcast
from app.services.llm_client import analyze_photo
from app.services.media import download_telegram_media
from app.services.messaging import send_document, send_message
from app.services.pdf import generate_inspection_pdf

logger = logging.getLogger("fieldbot.inspection")


async def _resolve_project(db: AsyncSession, session: ConversationSession) -> Project | None:
    project_id = session.context.get("project_id") if session.context else None
    if project_id:
        return await db.get(Project, project_id)
    return None


async def run_inspection(db: AsyncSession, session: ConversationSession, from_number: str, media_file_ids: list[str]) -> None:
    project = await _resolve_project(db, session)
    if project is None:
        send_message(from_number, "Which project is this for? Reply with the project name.")
        return

    per_photo_results = []
    for file_id in media_file_ids:
        image_bytes = await download_telegram_media(file_id)
        result = await analyze_photo(image_bytes)
        per_photo_results.append(result)

    if not per_photo_results:
        send_message(from_number, "No photos received. Please attach site photos.")
        return

    # Canonical count = max single-photo detection, capped at project total (per plan.txt 6b step 3)
    panels_detected = min(max(r.get("panels_detected", 0) for r in per_photo_results), project.total_panels)
    panels_with_issues = max(r.get("panels_with_issues", 0) for r in per_photo_results)
    issues = [issue for r in per_photo_results for issue in r.get("issues", [])]

    completion_pct = round((panels_detected / project.total_panels) * 100, 2) if project.total_panels else 0.0

    inspection = InspectionReport(
        project_id=project.id,
        submitted_by_phone=from_number,
        photo_urls=media_file_ids,
        panels_detected=panels_detected,
        panels_with_issues=panels_with_issues,
        issues=issues,
        completion_pct=completion_pct,
        ai_analysis_raw={"per_photo": per_photo_results},
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)

    log1 = ActivityLog(
        event_type="inspection_created",
        description=f"AI inspection report created for {project.name}",
        entity_type="inspection_report",
        entity_id=inspection.id,
    )
    db.add(log1)
    await db.commit()

    await broadcast("inspection_created", log1.description, "inspection_report", inspection.id)

    reply = (
        "Site Inspection Complete ✅\n\n"
        f"Project: {project.name}\n"
        f"\U0001F4F8 Photos analyzed: {len(media_file_ids)}\n"
        f"\U0001F522 Panels detected: {panels_detected} of {project.total_panels}\n"
        f"⚠️ Issues flagged: {panels_with_issues}\n"
        f"\U0001F4C8 Completion: {completion_pct:.0f}%"
    )
    if issues:
        reply += "\n\nIssues found:\n" + "\n".join(f"• {issue}" for issue in issues)
    send_message(from_number, reply)

    pdf_bytes = generate_inspection_pdf(project, inspection)
    send_document(from_number, pdf_bytes, f"inspection_{inspection.id}.pdf", caption="Full inspection report")

    session.state = "awaiting_followup_choice"
    session.context = {**(session.context or {}), "last_inspection_id": inspection.id}
    await db.commit()
    send_message(
        from_number,
        "What would you like to do next?\n"
        "• Reply \"invoice\" to draft a progress-claim invoice\n"
        "• Reply \"po\" to send a purchase order for materials",
    )
