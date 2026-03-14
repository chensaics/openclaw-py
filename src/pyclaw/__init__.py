"""pyclaw — Multi-channel AI gateway with extensible messaging integrations."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__: str = _pkg_version("openclaw-py")
except PackageNotFoundError:
    __version__ = "0.1.3"
