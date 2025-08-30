from pathlib import Path
import csv
import datetime

CSV_PATH = Path("data/powerball_history_full.csv")

def test_csv_integrity():
    assert CSV_PATH.exists(), f"{CSV_PATH} does not exist"

    seen_dates = set()
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        header = next(r)
        expected_header = ["date","w1","w2","w3","w4","w5","powerball","power_play","source_url"]
        assert header == expected_header, f"Header mismatch: {header}"

        for row in r:
            assert len(row) == len(expected_header), f"Row length wrong: {row}"
            d, w1,w2,w3,w4,w5,pb,pp,url = row

            # Date valid + unique
            try:
                datetime.date.fromisoformat(d)
            except ValueError:
                raise AssertionError(f"Invalid date: {d}")
            assert d not in seen_dates, f"Duplicate date found: {d}"
            seen_dates.add(d)

            # Parse numbers
            whites = [int(x) for x in (w1,w2,w3,w4,w5)]
            red = int(pb)

            # 5 distinct whites, range 1..69
            assert len(set(whites)) == 5, f"Whites not distinct for {d}: {whites}"
            assert all(1 <= n <= 69 for n in whites), f"White out of range for {d}: {whites}"

            # Red ball range 1..26
            assert 1 <= red <= 26, f"Powerball out of range for {d}: {red}"