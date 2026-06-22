"""APIRouter modules for web.py route groups.

New route groups live here as APIRouter factories (build_*_router) rather
than inline inside run_web(), so they can be reasoned about and tested
independently of the rest of the 1800+-line run_web() body. Existing
routes are not retrofitted into this pattern -- only new route groups
(agentic, p2p) use it, to avoid bundling a large structural refactor
with new feature code.
"""
