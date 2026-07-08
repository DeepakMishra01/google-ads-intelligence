"""Seed realistic DEMO data into the configured database.

Creates two accounts and six campaigns with deliberately varied health so every
Command Center page + the alert engine have interesting data to render:

  * MBA Admissions      - healthy
  * BTech Lead Gen       - limited by budget (high spend)
  * Law College Brand    - low CTR + a sharp CTR drop vs yesterday
  * Pharmacy Diploma     - zero impressions today (outage)
  * Design Retargeting   - CPC spike + a disapproved ad
  * Distance MBA         - paused (ignored by health)

30 days of daily snapshots are generated for campaigns, keywords, budgets, and
search terms. Idempotent: re-running wipes the previous DEMO accounts first.

Run:  .venv/Scripts/python -m scripts.seed_demo
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import delete

from app.database.session import session_scope
from app.models import (
    Account,
    Ad,
    AdGroup,
    Budget,
    BudgetSnapshot,
    Campaign,
    CampaignSnapshot,
    Keyword,
    KeywordSnapshot,
    SearchTerm,
    SearchTermSnapshot,
)

RNG = random.Random(42)
DAYS = 30
TODAY = date.today()
LATEST = TODAY - timedelta(days=1)  # newest complete day ("today" in the console)
PRIOR = LATEST - timedelta(days=1)


def m(x: float) -> int:
    """Currency units -> micros."""
    return int(round(x * 1_000_000))


# (account_key, name, base_impr, base_ctr, base_cpc, budget, conv_rate, scenario)
CAMPAIGNS = [
    ("geu", "MBA Admissions 2026", 4200, 0.055, 22, 6000, 0.032, "healthy"),
    ("geu", "BTech Lead Gen 2026", 6500, 0.042, 27, 5000, 0.028, "budget_limited"),
    ("geu", "Law College Brand", 3000, 0.030, 18, 4000, 0.015, "ctr_drop"),
    ("geu", "Pharmacy Diploma", 1600, 0.035, 16, 2500, 0.020, "zero_impressions"),
    ("dbs", "Design School Retargeting", 2600, 0.045, 20, 3500, 0.030, "cpc_spike"),
    ("dbs", "Distance MBA (Paused)", 2000, 0.040, 19, 3000, 0.022, "paused"),
]

ACCOUNTS = {
    "geu": ("1000000001", "Graphic Era University"),
    "dbs": ("1000000002", "Doon Business School"),
}

# QS profiles per campaign (3 keywords each) — some deliberately poor.
KEYWORDS = {
    "MBA Admissions 2026": [("mba admission", "EXACT", 8), ("best mba college", "PHRASE", 7), ("mba fees", "BROAD", 6)],
    "BTech Lead Gen 2026": [("btech admission", "EXACT", 7), ("engineering college", "PHRASE", 6), ("btech cse", "BROAD", 5)],
    "Law College Brand": [("llb course", "PHRASE", 4), ("law college", "BROAD", 3), ("ba llb", "EXACT", 5)],
    "Pharmacy Diploma": [("d pharma", "EXACT", 6), ("pharmacy course", "PHRASE", 5), ("b pharma admission", "BROAD", 6)],
    "Design School Retargeting": [("design course", "PHRASE", 6), ("fashion design", "BROAD", 5), ("ux design college", "EXACT", 7)],
    "Distance MBA (Paused)": [("distance mba", "EXACT", 6), ("online mba", "PHRASE", 5), ("correspondence mba", "BROAD", 4)],
}

SEARCH_TERMS = {
    "MBA Admissions 2026": ["mba admission 2026 last date", "top mba college in dehradun", "mba fees structure"],
    "BTech Lead Gen 2026": ["btech admission form", "best engineering college uttarakhand", "btech cse cutoff"],
    "Law College Brand": ["cheap law college", "free law course", "law college near me"],
    "Pharmacy Diploma": ["d pharma admission 2026", "pharmacy diploma fees", "b pharma vs d pharma"],
    "Design School Retargeting": ["fashion design course fees", "best design college", "ux bootcamp"],
    "Distance MBA (Paused)": ["distance mba approved", "online mba 1 year", "correspondence mba fees"],
}


def gen_day(scenario: str, impr: float, ctr: float, cpc: float, budget: float, conv_rate: float, d: date):
    """Return (impressions, clicks, cost, conversions) for one day/scenario."""
    wobble = 0.8 + RNG.random() * 0.4  # 0.8–1.2 daily variance
    impressions = int(impr * wobble)
    day_ctr = ctr
    day_cpc = cpc

    if scenario == "healthy":
        pass
    elif scenario == "budget_limited":
        # Consistently spends the entire daily budget.
        clicks = max(1, int(impressions * ctr))
        cost = budget  # 100% utilization
        return impressions, clicks, cost, clicks * conv_rate
    elif scenario == "ctr_drop":
        if d == LATEST:
            day_ctr = 0.014  # crashed today
        elif d == PRIOR:
            day_ctr = 0.032  # was fine yesterday
    elif scenario == "zero_impressions":
        if d == LATEST:
            return 0, 0, 0.0, 0.0  # outage today
    elif scenario == "cpc_spike":
        if d == LATEST:
            day_cpc = cpc * 1.6  # +60% CPC today

    clicks = max(0, int(impressions * day_ctr))
    cost = clicks * day_cpc
    return impressions, clicks, cost, clicks * conv_rate


def metrics(impressions: int, clicks: int, cost: float, conversions: float) -> dict:
    return {
        "impressions": impressions,
        "clicks": clicks,
        "interactions": clicks,
        "cost_micros": m(cost),
        "ctr": (clicks / impressions) if impressions else 0.0,
        "average_cpc_micros": m(cost / clicks) if clicks else None,
        "average_cpm_micros": m(cost / impressions * 1000) if impressions else None,
        "conversions": round(conversions, 2),
        "conversions_value": round(conversions * 4500, 2),
        "all_conversions": round(conversions, 2),
        "video_views": 0,
    }


def seed() -> None:
    dates = [LATEST - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]

    with session_scope() as db:
        # --- wipe prior demo accounts (cascades to all children) ---
        demo_ids = [cid for cid, _ in ACCOUNTS.values()]
        db.execute(delete(Account).where(Account.customer_id.in_(demo_ids)))
        db.flush()

        accounts: dict[str, Account] = {}
        for key, (cid, name) in ACCOUNTS.items():
            acc = Account(
                customer_id=cid,
                descriptive_name=name,
                currency_code="INR",
                time_zone="Asia/Kolkata",
                status="ENABLED",
                is_manager=False,
                is_syncable=True,
            )
            db.add(acc)
            db.flush()
            accounts[key] = acc

        gid = 500  # rolling google-id counter

        for (acc_key, name, impr, ctr, cpc, budget, conv_rate, scenario) in CAMPAIGNS:
            acc = accounts[acc_key]
            gid += 1
            status = "PAUSED" if scenario == "paused" else "ENABLED"

            budget_row = Budget(
                account_id=acc.id, budget_id=gid + 9000, name=f"{name} Budget",
                amount_micros=m(budget), delivery_method="STANDARD", period="DAILY",
                explicitly_shared=False,
            )
            db.add(budget_row)
            db.flush()

            campaign = Campaign(
                account_id=acc.id, campaign_id=gid, name=name, status=status,
                serving_status="SERVING", advertising_channel_type="SEARCH",
                bidding_strategy_type="MAXIMIZE_CONVERSIONS",
                networks="GOOGLE_SEARCH,SEARCH_PARTNERS",
                start_date=TODAY - timedelta(days=120),
                optimization_score=round(RNG.uniform(0.55, 0.95), 2),
                budget_id=budget_row.budget_id,
            )
            db.add(campaign)
            db.flush()

            ad_group = AdGroup(
                account_id=acc.id, campaign_id=campaign.id, ad_group_id=gid + 1000,
                name=f"{name} — Core", status=status, type="SEARCH_STANDARD",
                cpc_bid_micros=m(cpc),
            )
            db.add(ad_group)
            db.flush()

            # One ad; disapprove it for the cpc_spike scenario.
            db.add(
                Ad(
                    account_id=acc.id, ad_group_id=ad_group.id, ad_id=gid + 2000,
                    type="RESPONSIVE_SEARCH_AD", status=status,
                    approval_status="DISAPPROVED" if scenario == "cpc_spike" else "APPROVED",
                    final_urls="https://example.edu/apply",
                    headlines="Apply Now\nAdmissions Open 2026\nRanked Campus",
                    descriptions="Scholarships available. Enquire today.",
                )
            )

            kw_defs = KEYWORDS[name]
            keywords = []
            for i, (text, match, _qs) in enumerate(kw_defs):
                kw = Keyword(
                    account_id=acc.id, ad_group_id=ad_group.id, criterion_id=gid + 3000 + i,
                    text=text, match_type=match, status=status, cpc_bid_micros=m(cpc),
                )
                db.add(kw)
                keywords.append(kw)
            db.flush()

            st_defs = SEARCH_TERMS[name]
            search_terms = []
            for i, query in enumerate(st_defs):
                st = SearchTerm(
                    account_id=acc.id, campaign_id=campaign.id, ad_group_id=ad_group.id,
                    query=query, match_type="BROAD", search_term_targeting_status="NONE",
                )
                db.add(st)
                search_terms.append(st)
            db.flush()

            # --- daily snapshots ---
            camp_snaps, kw_snaps, st_snaps, budget_snaps = [], [], [], []
            for d in dates:
                impressions, clicks, cost, conversions = gen_day(
                    scenario, impr, ctr, cpc, budget, conv_rate, d
                )
                mx = metrics(impressions, clicks, cost, conversions)
                camp_snaps.append(
                    {
                        "account_id": acc.id, "campaign_id": campaign.id, "snapshot_date": d,
                        "status": status, "budget_micros": m(budget),
                        "bidding_strategy_type": campaign.bidding_strategy_type,
                        "optimization_score": campaign.optimization_score, **mx,
                    }
                )
                budget_snaps.append(
                    {
                        "account_id": acc.id, "budget_id": budget_row.id, "snapshot_date": d,
                        "amount_micros": m(budget), "spend_micros": mx["cost_micros"],
                        "utilization": round(cost / budget, 4) if budget else None,
                        "delivery_method": "STANDARD",
                    }
                )
                # split campaign metrics across keywords / search terms
                for i, kw in enumerate(keywords):
                    frac = [0.5, 0.3, 0.2][i]
                    ci, cc = int(impressions * frac), int(clicks * frac)
                    kmx = metrics(ci, cc, cost * frac, conversions * frac)
                    kw_snaps.append(
                        {
                            "account_id": acc.id, "keyword_id": kw.id, "ad_group_id": ad_group.id,
                            "campaign_id": campaign.id, "snapshot_date": d,
                            "match_type": kw.match_type, "status": status,
                            "quality_score": kw_defs[i][2],
                            "expected_ctr": "ABOVE_AVERAGE" if kw_defs[i][2] >= 7 else "BELOW_AVERAGE",
                            "landing_page_experience": "AVERAGE",
                            "ad_relevance": "AVERAGE" if kw_defs[i][2] >= 5 else "BELOW_AVERAGE",
                            **kmx,
                        }
                    )
                for i, st in enumerate(search_terms):
                    frac = [0.4, 0.35, 0.25][i]
                    si, sc = int(impressions * frac), int(clicks * frac)
                    st_snaps.append(
                        {
                            "account_id": acc.id, "search_term_id": st.id,
                            "campaign_id": campaign.id, "ad_group_id": ad_group.id,
                            "snapshot_date": d, **metrics(si, sc, cost * frac, conversions * frac),
                        }
                    )

            db.bulk_insert_mappings(CampaignSnapshot, camp_snaps)
            db.bulk_insert_mappings(KeywordSnapshot, kw_snaps)
            db.bulk_insert_mappings(SearchTermSnapshot, st_snaps)
            db.bulk_insert_mappings(BudgetSnapshot, budget_snaps)

        print(f"Seeded {len(CAMPAIGNS)} campaigns across {len(ACCOUNTS)} accounts, "
              f"{DAYS} days ({dates[0]} … {dates[-1]}).")


if __name__ == "__main__":
    seed()
