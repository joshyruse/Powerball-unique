from pathlib import Path
from lotto.rules import PowerballRules
from lotto.history import load_history_csv
from lotto.generate import generate_unique

def test_end_to_end_smoke(tmp_path: Path):
    # minimal fake sample that matches scraper format
    p = tmp_path / "mini.csv"
    p.write_text(
        "date,w1,w2,w3,w4,w5,powerball,power_play,source_url\n"
        "1992-04-22,4,8,15,16,23,42,,https://example\n"
        "1992-04-25,5,7,19,22,44,12,,https://example\n",
        encoding="utf-8"
    )

    rules = PowerballRules()
    hist = load_history_csv(p, rules)
    picks = generate_unique(hist, rules, count=2, seed=1)
    assert len(picks) == 2
    for whites, red in picks:
        assert len(whites) == 5
        assert all(1 <= w <= 69 for w in whites)
        assert 1 <= red <= 26