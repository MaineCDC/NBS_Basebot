"""Single source of truth for which NBS site each bot targets.

Rules (so we never have to mix-and-match per bot):
  * Default: every bot runs against PRODUCTION.
  * A bot named in TEST_LOCKED_BOTS ALWAYS runs against the InductiveHealth
    TEST site, regardless of ENVIRONMENT -- because it isn't promoted to prod
    yet. This is clearly indicated at runtime (see target_site_label / the
    "[bot] target site: ..." print each bot emits).
  * Setting ENVIRONMENT=development in .env forces ALL bots onto the test site
    (useful for a full dry run). In that mode nothing conflicts.

Because production and test are different websites sharing ONE Chrome session,
start_bots.py uses these helpers to drop any bot whose site doesn't match the
session, instead of letting a prod bot and a test bot fight over the browser.
"""
import os

# Bots not yet in production -> always the test site. Remove a name here the day
# that bot graduates to production.
#TEST_LOCKED_BOTS = {"babesia", "ILIOutbreak"}
TEST_LOCKED_BOTS = {"giardiasis"}
# ("4. giardiasis")
#     print("5. strep")
#     print("6. babesia")
#     print("7. CovidEcr")
#     print("8. HepBnotificationreview")
#     print("9. Gonorrhea")
#     print("10. ILIOutbreak")

def session_is_production():
    """Global switch: production unless ENVIRONMENT=development."""
    return os.getenv("ENVIRONMENT", "production").strip().lower() != "development"


def is_production(bot_name):
    """Resolve the prod/test flag for a single bot by name."""
    if bot_name in TEST_LOCKED_BOTS:
        return False
    return session_is_production()


def target_site_label(bot_name):
    """Human-readable site for logging."""
    return "PRODUCTION" if is_production(bot_name) else "TEST (InductiveHealth)"
