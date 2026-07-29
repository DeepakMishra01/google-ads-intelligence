"""CPL target optimizer — the platform's core purpose.

Cost-per-lead is fixed by two dials, and this models BOTH:

    CPL = CPC  ÷  CVR
          ^ lower via Quality Score + brand/high-intent keyword focus
                  ^ raise via landing page + lead form + follow-up

Given a target CPL band (e.g. ₹750–850) and the account's REAL rates — blended
CPC, an optimized (brand/high-intent) CPC, and the team's true clicks→lead
conversion (avg ~0.13%, best ~0.58%) — it computes the conversion rate required
to hit the target at each CPC, the gap versus reality, honest CPL scenarios, and
a prioritized playbook of levers (each tagged whether it moves CPC or CVR).

It never pretends ads alone deliver the target: it shows exactly how far the
funnel must improve, because that is the dominant dial.
"""

from __future__ import annotations

from typing import Any

# The team's real, measured clicks→lead conversion (decimals, not %).
DEFAULT_CVR_AVG = 0.0013   # 0.13% — current average across campaigns
DEFAULT_CVR_BEST = 0.0058  # 0.58% — best observed
DEFAULT_TARGET_CPL_LOW = 750.0
DEFAULT_TARGET_CPL_HIGH = 850.0


def _leads(budget: float, cpc: float, cvr: float) -> int:
    return int((budget / cpc) * cvr) if cpc else 0


def _scenario(name: str, cpc: float, cvr: float, budget: float, note: str) -> dict[str, Any]:
    cpl = round(cpc / cvr) if cvr else None
    return {
        "name": name,
        "cpc": round(cpc, 2),
        "cvr_pct": round(cvr * 100, 2),
        "cpl": cpl,
        "leads": _leads(budget, cpc, cvr),
        "note": note,
    }


def build_cpl_plan(
    *,
    budget: float,
    blended_cpc: float,
    optimized_cpc: float | None,
    target_cpl_low: float = DEFAULT_TARGET_CPL_LOW,
    target_cpl_high: float = DEFAULT_TARGET_CPL_HIGH,
    cvr_avg: float = DEFAULT_CVR_AVG,
    cvr_best: float = DEFAULT_CVR_BEST,
) -> dict[str, Any] | None:
    """Reverse-engineer the target CPL into the CVR (and CPC) it demands."""
    if not budget or budget <= 0 or not blended_cpc:
        return None
    opt_cpc = optimized_cpc or blended_cpc
    target_mid = (target_cpl_low + target_cpl_high) / 2

    # Required CVR = CPC / CPL. Lower CPC (opt) → lower required CVR.
    req_at_blended = blended_cpc / target_mid
    req_at_optimized = opt_cpc / target_mid
    # Range across the CPL band at the optimized CPC (the achievable path).
    req_low = opt_cpc / target_cpl_high   # easiest end of the band
    req_high = opt_cpc / target_cpl_low   # hardest end

    gap_vs_avg = round(req_at_optimized / cvr_avg, 1) if cvr_avg else None
    gap_vs_best = round(req_at_optimized / cvr_best, 1) if cvr_best else None
    reachable_at_best = cvr_best >= req_low  # can the best funnel hit the cheap end?

    scenarios = [
        _scenario("Today (avg funnel)", blended_cpc, cvr_avg, budget,
                  "Your current average — CPL is unviable at this conversion rate."),
        _scenario("Your best funnel", blended_cpc, cvr_best, budget,
                  "Even your best observed conversion is far from the target CPL."),
        _scenario("Target — optimized CPC", opt_cpc, req_at_optimized, budget,
                  f"To hit ₹{round(target_mid)} CPL you need this conversion rate."),
    ]

    # Prioritized levers, each tagged with the dial it moves. Ordered by impact.
    levers = [
        {"dial": "measure", "lever": "Fix conversion tracking",
         "detail": "You can't optimise what you can't measure. Tag the lead form / "
                   "thank-you page and call conversions first — everything below depends on it."},
        {"dial": "CVR", "lever": "Dedicated, fast landing page",
         "detail": "One page per ad group, matching the keyword, form above the fold, mobile-"
                   "first (you're ~88% mobile), <3s load. This is the single biggest CVR lever."},
        {"dial": "CVR", "lever": "Short lead form + instant follow-up",
         "detail": "Ask only name/phone/course; call the lead within minutes. Speed-to-lead is "
                   "the difference between a 0.5% and a 5% funnel."},
        {"dial": "CPC", "lever": "Concentrate on brand + high-intent exact keywords",
         "detail": f"Brand/apply/admission clicks are the cheapest and best-converting — "
                   f"weighting to them pulls blended CPC toward ~₹{round(opt_cpc)} and lifts CVR."},
        {"dial": "CPC", "lever": "Raise Quality Score",
         "detail": "Tighter ad↔keyword↔landing-page relevance lowers CPC for the same position; "
                   "aim for QS 8–10 on core terms."},
        {"dial": "CVR", "lever": "Match ad promise to landing page",
         "detail": "The headline they clicked must be the first thing they see (fees→fees, "
                   "apply→application form). Mismatch is silent conversion loss."},
        {"dial": "CPC", "lever": "Negative keywords + tight match types",
         "detail": "Cut job/result/login/PDF traffic that never converts (see Negative Keywords) "
                   "and avoid Broad match until tracking is live."},
    ]

    if reachable_at_best:
        verdict = (
            f"Reachable: your best funnel ({round(cvr_best * 100, 2)}%) is close to the "
            f"~{round(req_low * 100, 1)}% needed at an optimised ₹{round(opt_cpc)} CPC. "
            "Standardise every campaign to your best-converting setup."
        )
    else:
        verdict = (
            f"Not reachable on ads alone. Hitting ₹{round(target_mid)} CPL needs a "
            f"~{round(req_at_optimized * 100, 1)}% conversion rate — about {gap_vs_best}× your "
            f"best ({round(cvr_best * 100, 2)}%) and {gap_vs_avg}× your average "
            f"({round(cvr_avg * 100, 2)}%). The ad plan gets you the cheapest quality clicks; "
            "the landing page + lead follow-up must close the rest."
        )

    return {
        "target_cpl_low": round(target_cpl_low),
        "target_cpl_high": round(target_cpl_high),
        "blended_cpc": round(blended_cpc, 2),
        "optimized_cpc": round(opt_cpc, 2),
        "required_cvr_pct": round(req_at_optimized * 100, 2),
        "required_cvr_pct_at_blended": round(req_at_blended * 100, 2),
        "required_cvr_band_pct": [round(req_low * 100, 2), round(req_high * 100, 2)],
        "current_cvr_avg_pct": round(cvr_avg * 100, 2),
        "current_cvr_best_pct": round(cvr_best * 100, 2),
        "gap_vs_avg": gap_vs_avg,
        "gap_vs_best": gap_vs_best,
        "reachable_at_best": reachable_at_best,
        "scenarios": scenarios,
        "levers": levers,
        "verdict": verdict,
    }
