from contextvars import ContextVar
from typing import Optional

# Context variable to store the output directory for the current session/request
output_dir_var: ContextVar[Optional[str]] = ContextVar("output_dir", default=None)
