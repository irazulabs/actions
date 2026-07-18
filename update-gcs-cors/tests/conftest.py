from __future__ import annotations

import json
from pathlib import Path


def write_cors(path: Path, rules: object | None = None) -> Path:
    document = (
        rules
        if rules is not None
        else [
            {
                "origin": ["https://example.com"],
                "method": ["GET"],
                "responseHeader": ["Content-Type"],
                "maxAgeSeconds": 3600,
            }
        ]
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    return path
