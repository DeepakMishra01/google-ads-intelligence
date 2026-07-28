"""ORM models.

Importing this package registers every model on ``Base.metadata`` - required for
Alembic autogenerate and for ``Base.metadata.create_all`` in tests. Keep this
list exhaustive.
"""

from app.database.base import Base
from app.models.account import Account
from app.models.ad import Ad, AdSnapshot
from app.models.ad_copy import AdCopyGeneration
from app.models.ad_group import AdGroup, AdGroupSnapshot
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.api_token import ApiToken
from app.models.audit_log import AuditLog
from app.models.budget import Budget, BudgetSnapshot
from app.models.campaign import (
    Campaign,
    CampaignDeviceSnapshot,
    CampaignGeoSnapshot,
    CampaignSnapshot,
)
from app.models.keyword import Keyword, KeywordSnapshot
from app.models.recommendation import RecommendationSnapshot
from app.models.search_term import SearchTerm, SearchTermSnapshot
from app.models.sync_log import SyncLog, SyncStatus, SyncType
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "Account",
    "Campaign",
    "CampaignSnapshot",
    "CampaignDeviceSnapshot",
    "CampaignGeoSnapshot",
    "AdGroup",
    "AdGroupSnapshot",
    "Keyword",
    "KeywordSnapshot",
    "Ad",
    "AdSnapshot",
    "AdCopyGeneration",
    "SearchTerm",
    "SearchTermSnapshot",
    "Budget",
    "BudgetSnapshot",
    "RecommendationSnapshot",
    "SyncLog",
    "SyncType",
    "SyncStatus",
    "ApiToken",
    "User",
    "UserRole",
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "AuditLog",
]
