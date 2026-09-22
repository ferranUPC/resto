"""Knowledge-hygiene probes (E4.6; docs/_old/tfm-architecture-and-dod-v0.2.md §4.7): 20 constructed
cases checking that the Expert never cites an unverified, extrapolated `ExpertNote` as if it were
observed fact. See `docs/evaluating-resto.md` §4.8 for the full procedure and why this is
the only half of the hygiene bullet that needs a real model call — the other half ("status updates
in 100% of applicable cases") is deterministic and covered by
`tests/unit/application/use_cases/test_update_note_status.py` instead."""
