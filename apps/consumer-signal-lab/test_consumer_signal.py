"""Synthetic ordinary shopping-review tests. No real accounts, media or SNS data."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from consumer_signal import analyze


def review(i, text="텀블러 세척하기 편리해요", *, account=None, product="텀블러", kind="original", repost_of=None, platform="sample", posted_at="2026-11-02T09:00:00Z"):
    return {
        "product": product, "platform": platform, "post_id": str(i),
        "account": account or "synthetic-" + str(i),
        "posted_at": posted_at, "text": text, "kind": kind,
        "repost_of": repost_of,
    }


def only(rows, **kwargs):
    return analyze(rows, **kwargs)["products"][0]


class ConsumerSignalTests(unittest.TestCase):
    def test_ten_accounts_repeating_one_review_is_one_content_pattern(self):
        p = only([review(i) for i in range(10)])
        self.assertEqual((p["raw_rows"], p["unique_text_patterns"], p["exact_repeat_posts"]), (10, 1, 9))
        self.assertEqual((p["observed_accounts"], p["account_capped_patterns"]), (10, 1))
        self.assertEqual(p["top_account_share"], 0.1)

    def test_ten_distinct_reviews_remain_distinct(self):
        p = only([review(i, "좋은 텀블러 사용 후기 " + str(i)) for i in range(10)])
        self.assertEqual((p["unique_text_patterns"], p["exact_repeat_posts"]), (10, 0))

    def test_opposite_sentiment_is_not_merged(self):
        p = only([review(1, "이어폰 음질이 좋아요", product="이어폰"),
                  review(2, "이어폰 음질이 안 좋아요", product="이어폰")])
        self.assertEqual(p["unique_text_patterns"], 2)

    def test_reposts_are_amplification_not_reviews(self):
        p = only([review(1), review(2, "", kind="repost", repost_of="sample:1")])
        self.assertEqual((p["unique_text_patterns"], p["reposts"], p["unknown"]), (1, 1, 0))

    def test_unverified_repost_is_unknown(self):
        p = only([review(1), review(2, "", kind="repost"), review(3, "")])
        self.assertEqual((p["unique_text_patterns"], p["unknown"]), (1, 2))

    def test_quote_with_own_text_can_be_independent(self):
        p = only([review(1), review(2, "저는 세척이 불편했어요", kind="quote")])
        self.assertEqual((p["unique_text_patterns"], p["reposts"]), (2, 0))

    def test_duplicate_ingestion_does_not_double_count(self):
        rows = [review(1), review(1)]
        p = only(rows)
        self.assertEqual((p["raw_rows"], p["unique_source_posts"],
                          p["duplicate_feed_rows"], p["unique_text_patterns"]), (2, 1, 1, 1))

    def test_nfkc_and_whitespace_match_but_polarity_stays(self):
        p = only([review(1, "ＡＢＣ  최고"), review(2, "abc\n 최고")])
        self.assertEqual((p["unique_text_patterns"], p["exact_repeat_posts"]), (1, 1))

    def test_products_are_separate_denominators(self):
        result = analyze([review(1, "좋아요", product="키보드"),
                          review(2, "좋아요", product="마우스")])
        self.assertEqual([p["unique_text_patterns"] for p in result["products"]], [1, 1])

    def test_daily_cap_is_sensitivity_not_person_count(self):
        p = only([review(i, "후기 " + str(i), account="shopper") for i in range(4)],
                 daily_account_cap=2)
        self.assertEqual((p["unique_text_patterns"], p["account_capped_patterns"], p["account_cap_excess"]), (4, 2, 2))
        self.assertEqual(p["observed_accounts"], 1)

    def test_cap_resets_next_day(self):
        rows = [review(i, "후기 " + str(i), account="shopper", posted_at="2026-11-02") for i in range(3)]
        rows.append(review(4, "새날 후기", account="shopper", posted_at="2026-11-03"))
        p = only(rows)
        self.assertEqual((p["account_capped_patterns"], p["account_cap_excess"]), (3, 1))

    def test_unknown_account_is_not_assumed_one_person(self):
        r = review(1)
        r["account"] = None
        p = only([r])
        self.assertEqual((p["observed_accounts"], p["unknown_account_rows"],
                          p["uncapped_unknown_account_patterns"]), (0, 1, 1))
        self.assertIsNone(p["top_account_share"])

    def test_empty_batch(self):
        self.assertEqual(analyze([])["products"], [])
        self.assertEqual(analyze([])["input_rows"], 0)

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze([review(1)], daily_account_cap=0)
        with self.assertRaises(TypeError):
            analyze("not a dataset")
        r = review(1)
        r["kind"] = "unknown"
        with self.assertRaises(ValueError):
            analyze([r])
        r = review(1, "x" * 5001)
        with self.assertRaises(ValueError):
            analyze([r])

    def test_large_synthetic_batch(self):
        rows = (review(i, "안전한 일반 상품 후기 " + str(i % 100),
                       account="test-" + str(i % 200)) for i in range(20_000))
        result = analyze(rows)
        p = result["products"][0]
        self.assertEqual(result["input_rows"], 20_000)
        self.assertEqual(p["unique_source_posts"], 20_000)
        self.assertEqual(p["unique_text_patterns"], 100)
        self.assertEqual(p["exact_repeat_posts"], 19_900)
        self.assertEqual(p["observed_accounts"], 200)


if __name__ == "__main__":
    unittest.main()
