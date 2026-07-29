"""Campaign setup guide — the "build this from scratch" checklist.

Consolidates everything the engine already computed (budget, bidding, ad groups,
match types, negatives, devices, copy) into an ordered, plain-English checklist a
person new to Google Ads can follow step by step. Each step says what to set and
whether it's ready or still needs the user's attention (e.g. conversion tracking).

Pure function over already-built dicts — no DB/LLM.
"""

from __future__ import annotations

from typing import Any


def build_setup_guide(
    *,
    campaign_name: str,
    plan: dict[str, Any] | None,
    keyword_groups: list[dict[str, Any]],
    negatives: list[str],
    geo: str | None,
    has_conversions: bool,
    total_keywords: int,
) -> dict[str, Any]:
    """Ordered setup steps with a ready/action flag for each."""
    plan = plan or {}
    bidding = plan.get("bidding") or {}
    device = plan.get("device") or {}
    forecast = plan.get("forecast") or {}

    daily = bidding.get("daily_budget")
    cap = bidding.get("max_cpc_cap")
    budget = forecast.get("budget")

    n_groups = len(keyword_groups)
    group_names = ", ".join(g.get("name", "") for g in keyword_groups) or "—"
    geo_txt = geo or "India (refine to the campus city + a radius, and key metros)"

    steps: list[dict[str, Any]] = [
        {
            "step": "Campaign type",
            "detail": "Search Network only. Uncheck 'Display Network' and 'Search partners' "
            "to start — they spend budget with lower intent.",
            "status": "ready",
        },
        {
            "step": "Budget (daily)",
            "detail": (
                f"Set ₹{daily:,}/day"
                + (f" (≈ ₹{round(budget):,} over the period)." if budget else ".")
                + " Google can spend up to 2× on a busy day but averages to your monthly. "
                "Shift more into peak months — see the Monthly ad spend table."
            )
            if daily
            else "Enter a budget above to get a recommended daily amount.",
            "status": "ready" if daily else "action",
        },
        {
            "step": "Bidding strategy",
            "detail": (
                f"{bidding.get('recommended', 'Maximize Clicks with a CPC cap')}. "
                + (bidding.get("why") or "")
            ),
            "status": "ready",
        },
        {
            "step": "Max-CPC cap (anti-overspend)",
            "detail": f"Set a max cost-per-click cap of ~₹{cap} so automated bidding can't "
            "run away. Per-keyword starting bids are in the Keywords list."
            if cap
            else "Use the per-keyword bids as manual max-CPCs.",
            "status": "ready",
        },
        {
            "step": "Locations",
            "detail": f"Target {geo_txt}. Set location option to 'Presence' (people IN the "
            "area), not 'interest', to avoid paying for out-of-area clicks.",
            "status": "review",
        },
        {
            "step": "Devices",
            "detail": device.get("recommendation")
            or "Start at parity across devices; adjust once data comes in.",
            "status": "ready" if device else "review",
        },
        {
            "step": "Ad groups & keywords",
            "detail": f"{n_groups} ad groups by intent ({group_names}). "
            f"{total_keywords} keywords, each with its own match type and bid "
            "(Exact for brand/proven, Phrase elsewhere — see the Keywords list).",
            "status": "ready",
        },
        {
            "step": "Match types (anti-overspend)",
            "detail": "Use Exact and Phrase only. Do NOT use Broad match until conversion "
            "tracking + smart bidding are live — Broad without them is the top way to waste "
            "budget.",
            "status": "ready",
        },
        {
            "step": "Negative keywords",
            "detail": f"Add the {len(negatives)} negative keywords so you don't pay for "
            "irrelevant searches (jobs, results, free, PDFs, etc.).",
            "status": "ready" if negatives else "review",
        },
        {
            "step": "Ads (Responsive Search Ads)",
            "detail": "Paste the generated headlines & descriptions (see Ad copy). "
            "Aim for 8–15 headlines and 3–4 descriptions per ad group for a strong Ad Strength.",
            "status": "ready",
        },
        {
            "step": "Extensions / assets",
            "detail": "Add the generated sitelinks, callouts and structured snippets — they "
            "lift CTR for free and are required for a competitive ad.",
            "status": "ready",
        },
        {
            "step": "Conversion tracking",
            "detail": (
                "NOT set up for this campus. Until it's fixed, leads and cost-per-lead are "
                "estimates and you can't use lead-based bidding. Fixing it unlocks Maximize "
                "Conversions → Target CPA and real ROI — do this first if you can."
            )
            if not has_conversions
            else "Conversion tracking is active — you can move to conversion-based bidding.",
            "status": "action" if not has_conversions else "ready",
        },
    ]
    return {
        "campaign_name": campaign_name,
        "steps": steps,
        "ready_count": sum(1 for s in steps if s["status"] == "ready"),
        "action_count": sum(1 for s in steps if s["status"] == "action"),
    }
