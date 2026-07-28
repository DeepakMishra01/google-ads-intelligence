"""Curated campus briefs — verifiable brand facts only (no marketing claims).

These seed known campuses with the structural facts an ad strategist needs:
canonical name, search aliases (for campus discovery + name matching), city,
programme types, entrance exam, and the official homepage (a low-confidence
Final-URL fallback used only when no historical landing page exists).

Facts here are limited to name / location / programme / exam / official domain —
never rankings, fees, or placement numbers (those are extracted live from the
landing page so nothing is fabricated). Any campus the user types that is not
listed still works: it falls back to a generic brief built from the typed name.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CampusBrief:
    key: str
    brand: str
    short: str
    aliases: list[str]
    location: str
    programs: list[str]
    exam: str | None = None
    homepage: str | None = None
    # extra name fragments that identify this campus in campaign names
    match_terms: list[str] = field(default_factory=list)
    # name fragments that would be FALSE matches (excluded)
    exclude_terms: list[str] = field(default_factory=list)

    def patterns(self) -> list[str]:
        """All name fragments used to match this campus in the warehouse."""
        base = {self.short.lower(), self.brand.lower(), *[a.lower() for a in self.aliases]}
        base.update(t.lower() for t in self.match_terms)
        return sorted(base)


CAMPUS_BRIEFS: list[CampusBrief] = [
    CampusBrief(
        key="gibs",
        brand="GIBS Business School",
        short="GIBS",
        aliases=["gibs", "gibs bangalore", "gibs business school"],
        location="Bangalore",
        programs=["PGDM", "MBA"],
        homepage="https://gibs.edu.in/",
        match_terms=["gibs"],
    ),
    CampusBrief(
        key="xime",
        brand="XIME",
        short="XIME",
        aliases=["xime", "xavier institute of management and entrepreneurship"],
        location="Bangalore",
        programs=["PGDM", "MBA"],
        homepage="https://xime.org/",
        match_terms=["xime"],
    ),
    CampusBrief(
        key="indus",
        brand="Indus University",
        short="Indus",
        aliases=["indus", "indus university", "indus university ahmedabad"],
        location="Ahmedabad",
        programs=["B.Tech", "Admissions"],
        homepage="https://www.indusuni.ac.in/",
        match_terms=["indus"],
        exclude_terms=["hindus", "hindustan"],
    ),
    CampusBrief(
        key="mica",
        brand="MICA",
        short="MICA",
        aliases=["mica", "mica ahmedabad", "mudra institute"],
        location="Ahmedabad",
        programs=["PGDM-C", "MBA"],
        exam="MICAT",
        homepage="https://www.mica.ac.in/",
        match_terms=["mica", "micat"],
    ),
    # Additional campuses with history (architecture supports every university).
    CampusBrief(
        key="nmims",
        brand="NMIMS",
        short="NMIMS",
        aliases=["nmims", "nmat", "npat"],
        location="Mumbai",
        programs=["MBA", "NPAT"],
        exam="NMAT",
        homepage="https://www.nmims.edu/",
        match_terms=["nmims", "nmat"],
    ),
    CampusBrief(
        key="gim",
        brand="Goa Institute of Management",
        short="GIM",
        aliases=["gim", "goa institute of management"],
        location="Goa",
        programs=["PGDM", "MBA"],
        homepage="https://www.gim.ac.in/",
        match_terms=["goa institute"],
    ),
]

_BY_KEY = {b.key: b for b in CAMPUS_BRIEFS}


def find_brief(query: str) -> CampusBrief | None:
    """Best-effort match of a free-text campus query to a known brief."""
    q = (query or "").strip().lower()
    if not q:
        return None
    if q in _BY_KEY:
        return _BY_KEY[q]
    # exact alias / short match first
    for b in CAMPUS_BRIEFS:
        if q == b.short.lower() or q == b.brand.lower() or q in [a.lower() for a in b.aliases]:
            return b
    # substring / contains match
    for b in CAMPUS_BRIEFS:
        if any(term in q or q in term for term in b.patterns()):
            return b
    return None


def generic_brief(query: str) -> CampusBrief:
    """Build a fallback brief for a campus not in the curated list."""
    name = (query or "").strip() or "University"
    return CampusBrief(
        key=name.lower().replace(" ", "_"),
        brand=name,
        short=name.split()[0],
        aliases=[name.lower()],
        location="",
        programs=["Admissions"],
        match_terms=[name.lower()],
    )
