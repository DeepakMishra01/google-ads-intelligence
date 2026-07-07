"""Repository layer - the sole gateway to the database for services."""

from app.repositories.account import AccountRepository
from app.repositories.ad import AdRepository, AdSnapshotRepository
from app.repositories.ad_group import AdGroupRepository, AdGroupSnapshotRepository
from app.repositories.alert import AlertRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.budget import BudgetRepository, BudgetSnapshotRepository
from app.repositories.campaign import (
    CampaignDeviceSnapshotRepository,
    CampaignGeoSnapshotRepository,
    CampaignRepository,
    CampaignSnapshotRepository,
)
from app.repositories.dashboard import DashboardRepository
from app.repositories.keyword import KeywordRepository, KeywordSnapshotRepository
from app.repositories.ops import OpsRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.search_term import (
    SearchTermRepository,
    SearchTermSnapshotRepository,
)
from app.repositories.sync_log import SyncLogRepository

__all__ = [
    "AccountRepository",
    "CampaignRepository",
    "CampaignSnapshotRepository",
    "CampaignDeviceSnapshotRepository",
    "CampaignGeoSnapshotRepository",
    "AdGroupRepository",
    "AdGroupSnapshotRepository",
    "KeywordRepository",
    "KeywordSnapshotRepository",
    "AdRepository",
    "AdSnapshotRepository",
    "SearchTermRepository",
    "SearchTermSnapshotRepository",
    "BudgetRepository",
    "BudgetSnapshotRepository",
    "RecommendationRepository",
    "SyncLogRepository",
    "DashboardRepository",
    "AlertRepository",
    "AuditLogRepository",
    "OpsRepository",
]
