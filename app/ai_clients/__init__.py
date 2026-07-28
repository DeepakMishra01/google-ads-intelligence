"""External AI/LLM clients.

Kept separate from ``app/google_ads`` so the platform can grow a suite of AI
agents (ad copy, campaign creator, keyword generator, ...) that all share one
cached, retry-wrapped LLM client with a typed error taxonomy.
"""
