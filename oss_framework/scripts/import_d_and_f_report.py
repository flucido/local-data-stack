"""Import D&F report from Excel.

Stage 1 canonical landing is Parquet under STAGE1_PATH.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import logging

import pandas as pd

from config import STAGE1_PATH

logger = logging.getLogger(__name__)


class DAndFImporter:
    """Import D&F (Ds, Fs, 504, SPED) report from Excel"""

    def __init__(self):
        self.records_imported = 0

    def import_from_excel(self, file_path: str) -> int:
        """Import D&F report from Excel file"""
        try:
            if not file_path:
                logger.warning("No D&F report path provided")
                return 0

            # Read Excel file
            df = pd.read_excel(file_path)
            self.records_imported = len(df)
            logger.info(
                f"Loaded D&F report with {self.records_imported} rows from {file_path}"
            )

            load_date = date.today().isoformat()
            out_dir = (
                Path(STAGE1_PATH)
                / "reference"
                / "excel"
                / "raw_d_and_f"
                / f"load_date={load_date}"
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "part-000.parquet"
            df.to_parquet(out_file, index=False)
            logger.info(f"Wrote Stage1 Parquet: {out_file}")

            return self.records_imported

        except Exception as e:
            logger.error(f"Error importing D&F report: {str(e)}")
            raise

    def close(self):
        """No-op for compatibility."""
        return


if __name__ == "__main__":
    importer = DAndFImporter()
    # Note: Requires valid file path
    print("✅ D&F importer ready")
    importer.close()
