"""AI Tools services — the AI Ad Copy Generator engine (Phase 3).

Each service has a single responsibility and follows the platform convention
``__init__(self, db: Session)`` returning plain dicts. ``AdCopyService`` is the
orchestrator that composes them into one generation run.
"""
