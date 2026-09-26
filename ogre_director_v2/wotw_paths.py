from pathlib import Path
import os
def user_data_path(*parts, create_parent=False):
    base = Path(os.environ.get("LOCKKEY_USER_DATA", Path(__file__).resolve().parent/"user_data"))
    p = base.joinpath(*parts)
    if create_parent:
        p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)
