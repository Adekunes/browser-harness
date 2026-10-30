"""Keep unit tests off live daemons.

browser_harness reads these at import, and daemon.PID binds to them there. Without
this, a test reaching daemon.serve() rewrites the real pid record for BU_NAME, and
the live daemon that owns it exits as superseded within seconds."""
import atexit
import os
import shutil
import tempfile

# Short and under /tmp: AF_UNIX sun_path is 104 bytes on macOS.
_scratch = tempfile.mkdtemp(prefix="bh-", dir="/tmp")
atexit.register(shutil.rmtree, _scratch, ignore_errors=True)
os.environ.update(
    BU_NAME="unit-test",
    BH_RUNTIME_DIR=_scratch,
    BH_RUNTIME_DIR_SHARED="1",
    BH_TMP_DIR=_scratch,
    BH_TMP_DIR_SHARED="1",
)
for var in ("BU_CDP_URL", "BU_CDP_WS", "BU_BROWSER_ID"):
    os.environ.pop(var, None)
