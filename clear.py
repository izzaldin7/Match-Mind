"""
Local dev utility — clears cached briefings/reports from matchmind.db.

This is a plain script, NOT an API endpoint, so it can only ever be run
by someone with direct access to this machine/codebase. Never expose
this as an HTTP route — see the conversation history for why.

Usage:
    python clear.py reports      # clear all cached post-match reports
    python clear.py briefings    # clear all cached pre-match briefings
    python clear.py box-scores   # clear cached Highlightly player box scores
    python clear.py all          # clear both
"""

import sys
from database import Session, GeneratedContent


def clear_content(content_type):
    session = Session()
    try:
        deleted = session.query(GeneratedContent).filter_by(
            content_type=content_type
        ).delete()
        session.commit()
        print(f"Cleared {deleted} cached {content_type}(s).")
    except Exception as e:
        session.rollback()
        print(f"Error clearing {content_type}: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target == "reports":
        clear_content("report")
    elif target == "briefings":
        clear_content("briefing")
    elif target == "box-scores":
        clear_content("box_score")
    elif target == "all":
        clear_content("report")
        clear_content("briefing")
        clear_content("box_score")
    else:
        print("Usage: python clear.py [reports|briefings|box-scores|all]")
        sys.exit(1)
