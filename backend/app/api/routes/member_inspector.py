from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.member_actions import MemberAction
from app.models.guild_roles import DiscordGuildRole
from app.models.member_cases import MemberCase
from app.models.member_evidence import MemberCaseAppeal, MemberCaseEvidence
from app.models.members import DiscordMember
from app.models.verification import VerificationRequest
from app.schemas.member_inspector import MemberInspectorResponse, MemberInspectorSummary, MemberTimelineItem
from app.services.member_service import MemberService

router = APIRouter(tags=["Member Inspector"])


@router.get("/discord/guilds/{guild_id}/members/{discord_user_id}/inspector", response_model=MemberInspectorResponse)
async def inspect_member(
    guild_id: int,
    discord_user_id: int,
    timeline_limit: int = Query(default=100, ge=10, le=300),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    member = await MemberService(session).get(guild_id, discord_user_id)
    member_row = (await session.execute(select(DiscordMember).where(
        DiscordMember.guild_id == guild_id,
        DiscordMember.discord_user_id == discord_user_id,
    ))).scalar_one()

    cases = (await session.execute(select(MemberCase).where(MemberCase.member_id == member_row.id))).scalars().all()
    case_ids = [c.id for c in cases]
    evidence = []
    appeals = []
    if case_ids:
        evidence = (await session.execute(select(MemberCaseEvidence).where(MemberCaseEvidence.case_id.in_(case_ids)))).scalars().all()
        appeals = (await session.execute(select(MemberCaseAppeal).where(MemberCaseAppeal.case_id.in_(case_ids)))).scalars().all()
    actions = (await session.execute(select(MemberAction).where(
        MemberAction.guild_id == guild_id,
        MemberAction.discord_user_id == discord_user_id,
    ))).scalars().all()
    verifications = (await session.execute(select(VerificationRequest).where(
        VerificationRequest.guild_id == guild_id,
        VerificationRequest.discord_user_id == discord_user_id,
    ).order_by(VerificationRequest.created_at.desc()).limit(20))).scalars().all()

    timeline: list[MemberTimelineItem] = []
    for item in cases:
        timeline.append(MemberTimelineItem(id=str(item.id), kind="case", title=item.title, detail=item.description,
            status=item.status, severity=item.severity, occurred_at=item.created_at,
            metadata={"category": item.category, "priority": item.priority}))
    for item in evidence:
        timeline.append(MemberTimelineItem(id=str(item.id), kind="evidence", title=item.title, detail=item.notes,
            status=item.evidence_type, occurred_at=item.created_at, metadata={"source_url": item.source_url}))
    for item in appeals:
        timeline.append(MemberTimelineItem(id=str(item.id), kind="appeal", title="Member appeal", detail=item.statement,
            status=item.status, occurred_at=item.created_at, metadata={"decision": item.decision}))
    for item in actions:
        timeline.append(MemberTimelineItem(id=str(item.id), kind="action", title=str(item.action_type.value), detail=item.result_message,
            status=str(item.status.value), occurred_at=item.created_at, metadata={"attempt_count": item.attempt_count}))
    for item in verifications:
        timeline.append(MemberTimelineItem(id=str(item.id), kind="verification", title=f"Verification: {item.alliance}", detail=item.result_message,
            status=item.status, occurred_at=item.created_at, metadata={"nickname": item.nickname, "requested_nickname": item.requested_nickname}))
    if member_row.joined_at:
        timeline.append(MemberTimelineItem(id=f"joined-{discord_user_id}", kind="member", title="Joined server", status="active", occurred_at=member_row.joined_at))
    if member_row.left_at:
        timeline.append(MemberTimelineItem(id=f"left-{discord_user_id}", kind="member", title="Left server", status="left", occurred_at=member_row.left_at))

    timeline.sort(key=lambda x: x.occurred_at, reverse=True)
    role_ids = [int(r.discord_role_id) for r in member.roles]
    permission_mask = 0
    if role_ids:
        role_rows = (await session.execute(select(DiscordGuildRole).where(
            DiscordGuildRole.guild_id == guild_id,
            DiscordGuildRole.discord_role_id.in_(role_ids),
        ))).scalars().all()
        for role in role_rows:
            permission_mask |= int(role.permissions or 0)
    permission_bits = {
        0: "Create instant invite", 1: "Kick members", 2: "Ban members", 3: "Administrator",
        4: "Manage channels", 5: "Manage server", 6: "Add reactions", 7: "View audit log",
        10: "View channels", 11: "Send messages", 13: "Manage messages", 14: "Embed links",
        15: "Attach files", 17: "Mention everyone", 18: "Use external emojis", 20: "Connect voice",
        21: "Speak", 24: "Move members", 28: "Manage roles", 29: "Manage webhooks",
        30: "Manage emojis", 34: "Manage threads", 36: "Use application commands", 40: "Moderate members",
    }
    permissions = [name for bit, name in permission_bits.items() if permission_mask & (1 << bit)]
    verification_payload = [{
        "id": str(v.id), "alliance": v.alliance, "nickname": v.nickname,
        "requested_nickname": v.requested_nickname, "status": v.status,
        "result_message": v.result_message, "created_at": v.created_at,
        "decided_at": v.decided_at,
    } for v in verifications]

    return MemberInspectorResponse(
        member=member,
        summary=MemberInspectorSummary(
            open_cases=sum(1 for c in cases if c.status in {"open", "investigating"}),
            resolved_cases=sum(1 for c in cases if c.status in {"resolved", "dismissed"}),
            appeals=len(appeals), evidence=len(evidence), actions=len(actions), verification_requests=len(verifications),
        ),
        permissions=permissions,
        verification=verification_payload,
        timeline=timeline[:timeline_limit],
    )
