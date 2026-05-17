"""Provider abstraction layer — the spine of local-first (docs/ARCHITECTURE.md §3).

Every external system (fleet registry, billing, provisioning, auth, email) is reached
ONLY through an interface here. Routers/services never import stripe/paramiko/supabase/
resend/docker directly — enforced by tests/test_architecture.py.
"""
