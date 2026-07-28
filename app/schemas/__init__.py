"""Pydantic request/response schemas."""

from app.schemas.ad_copy import (
    AdCopyGenerateRequest,
    AdCopyGenerateResponse,
    AdCopyHistoryResponse,
    CampusSearchResponse,
    FinalUrlResponse,
    LandingPageSummary,
)
from app.schemas.common import Message, ORMModel, Page
from app.schemas.dashboard import (
    BudgetUtilizationRow,
    CampaignPerformanceRow,
    CampaignTrendPoint,
    DailySpendPoint,
    KeywordHealthRow,
    SearchTermRow,
)
from app.schemas.entities import (
    AccountRead,
    AdGroupRead,
    AdRead,
    BudgetRead,
    CampaignRead,
    KeywordRead,
    SearchTermRead,
)
from app.schemas.snapshots import (
    AdGroupSnapshotRead,
    AdSnapshotRead,
    CampaignSnapshotRead,
    KeywordSnapshotRead,
    SearchTermSnapshotRead,
)
from app.schemas.sync import (
    BackfillRequest,
    SyncLogRead,
    SyncRunResult,
    SyncStatusResponse,
    SyncTriggerRequest,
)

__all__ = [
    "Message",
    "ORMModel",
    "Page",
    "AccountRead",
    "CampaignRead",
    "AdGroupRead",
    "KeywordRead",
    "AdRead",
    "SearchTermRead",
    "BudgetRead",
    "CampaignSnapshotRead",
    "AdGroupSnapshotRead",
    "KeywordSnapshotRead",
    "AdSnapshotRead",
    "SearchTermSnapshotRead",
    "SyncTriggerRequest",
    "BackfillRequest",
    "SyncLogRead",
    "SyncRunResult",
    "SyncStatusResponse",
    "CampaignPerformanceRow",
    "KeywordHealthRow",
    "SearchTermRow",
    "BudgetUtilizationRow",
    "DailySpendPoint",
    "CampaignTrendPoint",
    "AdCopyGenerateRequest",
    "AdCopyGenerateResponse",
    "AdCopyHistoryResponse",
    "CampusSearchResponse",
    "FinalUrlResponse",
    "LandingPageSummary",
]
