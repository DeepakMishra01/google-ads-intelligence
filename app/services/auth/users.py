"""User provisioning + access queries for Google sign-in and RBAC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User, UserAccount, UserRole
from app.services.auth.google import GoogleIdentity


class AuthUserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    def upsert_from_google(
        self,
        identity: GoogleIdentity,
        *,
        allowed_domains: list[str],
        admin_emails: list[str],
    ) -> User:
        """Create/refresh a user from a verified Google identity.

        Enforces the sign-in policy: the email must be on an allowed domain OR in
        the admin list. Admins get the admin role; everyone else is a manager with
        no account grants until an admin assigns them. Raises ``PermissionError``
        if the account is not allowed to sign in.
        """
        if not identity.email_verified:
            raise PermissionError("Your Google email is not verified.")

        email = identity.email.lower()
        domain = email.split("@")[-1]
        is_admin = email in admin_emails
        if not is_admin and allowed_domains and domain not in allowed_domains:
            raise PermissionError(
                "This account isn't allowed to sign in. Ask an admin for access."
            )
        if not is_admin and not allowed_domains:
            # No domains configured and not an admin — refuse rather than fail open.
            raise PermissionError("Sign-in is restricted. Ask an admin for access.")

        user = self.db.execute(
            select(User).where(User.google_sub == identity.sub)
        ).scalar_one_or_none()
        if user is None:
            user = self.db.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()

        role = UserRole.ADMIN.value if is_admin else None
        if user is None:
            user = User(
                email=email,
                full_name=identity.name,
                role=role or UserRole.MANAGER.value,
                google_sub=identity.sub,
                picture=identity.picture,
                is_active=True,
            )
            self.db.add(user)
        else:
            user.email = email
            user.google_sub = identity.sub
            user.full_name = identity.name or user.full_name
            user.picture = identity.picture or user.picture
            # Admin-list membership is authoritative and can promote; it never
            # silently demotes an admin who was granted the role in-app.
            if is_admin:
                user.role = UserRole.ADMIN.value
        user.last_login_at = datetime.now(timezone.utc)
        self.db.flush()
        return user

    # ------------------------------------------------------------------ #
    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def allowed_account_ids(self, user: User) -> set[int] | None:
        """Accounts a user may see. None means 'all' (admins).

        For a manager this is the UNION of explicit admin grants (``user_accounts``)
        and the accounts of the campaigns/campuses they OWN in the Accountability
        tab (``ad_copy_generations.owner_user_id``). So assigning ownership there
        immediately scopes their access — no separate grant step needed.
        """
        if user.role == UserRole.ADMIN.value:
            return None
        from app.models.ad_copy import AdCopyGeneration

        granted = set(
            self.db.execute(
                select(UserAccount.account_id).where(UserAccount.user_id == user.id)
            ).scalars()
        )
        owned = set(
            self.db.execute(
                select(AdCopyGeneration.account_id).where(
                    AdCopyGeneration.owner_user_id == user.id,
                    AdCopyGeneration.account_id.isnot(None),
                )
            ).scalars()
        )
        return granted | owned

    def list_users_with_access(self) -> list[dict[str, Any]]:
        users = self.db.execute(select(User).order_by(User.email)).scalars().all()
        grants: dict[int, list[int]] = {}
        for uid, aid in self.db.execute(
            select(UserAccount.user_id, UserAccount.account_id)
        ).all():
            grants.setdefault(uid, []).append(aid)
        return [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "picture": u.picture,
                "last_login_at": u.last_login_at,
                "account_ids": sorted(grants.get(u.id, [])),
            }
            for u in users
        ]

    def set_role(self, user_id: int, role: str) -> User | None:
        if role not in (UserRole.ADMIN.value, UserRole.MANAGER.value):
            raise ValueError("role must be 'admin' or 'manager'")
        user = self.db.get(User, user_id)
        if user is None:
            return None
        user.role = role
        self.db.flush()
        return user

    def set_active(self, user_id: int, is_active: bool) -> User | None:
        user = self.db.get(User, user_id)
        if user is None:
            return None
        user.is_active = is_active
        self.db.flush()
        return user

    def delete_user(self, user_id: int) -> bool:
        """Remove a user entirely. ``user_accounts`` grants cascade-delete; any
        ad-copy generations they own/submitted keep their history (the user FK is
        set NULL). Returns False if the user doesn't exist."""
        user = self.db.get(User, user_id)
        if user is None:
            return False
        self.db.delete(user)
        self.db.flush()
        return True

    def set_accounts(self, user_id: int, account_ids: list[int]) -> User | None:
        """Replace a manager's account grants with ``account_ids``."""
        user = self.db.get(User, user_id)
        if user is None:
            return None
        # Only keep ids that are real, non-manager accounts.
        valid = set(
            self.db.execute(
                select(Account.id).where(
                    Account.id.in_(account_ids), Account.is_manager.isnot(True)
                )
            ).scalars()
        )
        self.db.execute(delete(UserAccount).where(UserAccount.user_id == user_id))
        for aid in valid:
            self.db.add(UserAccount(user_id=user_id, account_id=aid))
        self.db.flush()
        return user
