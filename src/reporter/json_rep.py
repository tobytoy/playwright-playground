"""
JSON Reporter: exports audit report to structured JSON.
"""

import json
from pathlib import Path
from ..models import AuditReport


class JSONReporter:
    @staticmethod
    def export(report: AuditReport, output_path: str | Path):
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
