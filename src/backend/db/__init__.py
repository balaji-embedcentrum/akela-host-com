"""Two stores (docs/ARCHITECTURE.md §6): web-app DB (public) and the fleet registry
(`fleet` schema in mock mode = same Postgres; Supabase in real mode). The cross-store
link `agents.slot_name ↔ agent_slots.slot_name` is logical, never an FK."""

FLEET_SCHEMA = "fleet"
