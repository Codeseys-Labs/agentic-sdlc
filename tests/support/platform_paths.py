"""One absolute path a fixture can name on any host, because `Path("/x")` is not one.

WHY THIS FILE EXISTS
--------------------
`WindowsPath("/payload").is_absolute()` is FALSE. A Windows path is absolute only with a drive (or a
UNC share); a leading separator alone gives it a root and no anchor, so `os.path.abspath` completes it
against the process's current drive and `/payload` becomes `C:\\payload`.

Three fixtures named such a literal and compared it against what a product function returned, which is
an identity on POSIX and a mismatch on native Windows. All three failed that way on the Windows CI leg
of main@818bf09 (seed context `ci-red-818bf09`):

  * `tests/test_git_project_ladder.py`        -- `WindowsPath('/payload') != WindowsPath('C:/payload')`
  * `tests/test_ccodex_sdlc_two_agent_plane.py` -- `'C:/fixture/home/.claude' != '/fixture/home/.claude'`
  * `tests/test_operator_tools_import_freedom.py` -- `WindowsPath('C:/b') != WindowsPath('/b')`

None of the three was a product defect: each product function anchored an incomplete path exactly as
documented, and the fixture was what claimed to be absolute without being so.

WHAT THIS DOES AND DOES NOT PROMISE. `ABSOLUTE_ANCHOR` is absolute under the flavour of the host that
is running, which is the only property those comparisons need -- it is NOT a path absolute under both
flavours at once, because no path is except a UNC share. So use it to build a fixture the running
platform will agree is absolute; do not read it as a portable literal.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The root of the volume this process is on: `/` on POSIX, `C:\` (or whatever drive) on Windows.
#: Derived rather than written down, because a hard-coded `C:\` would be the same class of assumption
#: in the other direction.
ABSOLUTE_ANCHOR = Path(os.path.abspath(os.sep))


def absolute_fixture(*parts: str) -> Path:
    """One absolute, NONEXISTENT fixture path built from the running host's own anchor.

    `absolute_fixture("payload")` is `/payload` on POSIX and `C:\\payload` on Windows. Nothing is
    created: these are values for comparisons and for configuration objects, not directories.
    """
    return ABSOLUTE_ANCHOR.joinpath(*parts)
