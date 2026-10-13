import json
import shutil
import subprocess
from pathlib import Path
import pytest
from media_automation.bulletin.numbering import number_for_date

@pytest.mark.parametrize('day,expected',[('2026-10-11','13-41'),('2026-10-18','13-42'),('2026-01-04','13-1'),('2026-12-27','13-52'),('2027-01-03','14-1'),('2028-12-31','15-53')])
def test_date_numbering_matches_browser_across_year_boundaries(day,expected):
    assert number_for_date(day)==expected
    node=shutil.which('node')
    if node:
        p=Path(__file__).parents[1]/'src/media_automation/web/original/ui/bulletin-number.js'
        actual=subprocess.check_output([node,'-e',"console.log(require(process.argv[1]).numberForDate(process.argv[2]))",str(p),day],text=True).strip()
        assert actual==expected

def test_non_sunday_rejected():
    with pytest.raises(ValueError):number_for_date('2026-10-10')
