"""Operations Command Center domain services (Phase 2).

Read-only analytics built on top of the Phase 1 data layer. Nothing here writes
to Google Ads. The scoring core (:mod:`app.services.ops.scoring`) is pure and
deterministic so health/priority/alert logic is unit-testable in isolation.
"""
