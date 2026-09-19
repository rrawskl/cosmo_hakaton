"""Import only already downloaded real responses, retaining acquisition timestamps."""

import json
from pathlib import Path
from backend.app import adapters

adapters.init_sources()
for item in json.loads(Path("data/audit/access.json").read_text(encoding="utf8")):
    source = item["source"]
    if (
        source not in adapters.CATALOG
        or item.get("status") != 200
        or source in ["ncei", "spacetrack"]
    ):
        continue
    path = Path("data/audit") / (source + ".txt")
    if path.exists():
        record = adapters.store_response(
            source,
            item["url"],
            path.read_bytes().decode("utf8"),
            retrieved=item["retrieved_at"],
        )
        print(source, record["sha256"])
