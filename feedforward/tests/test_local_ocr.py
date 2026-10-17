from core.local_ocr import _lines


def test_extracts_paddle_v3_recognized_text():
    assert _lines([{"rec_texts": ["Force", "equals mass times acceleration"]}]) == [
        "Force", "equals mass times acceleration"
    ]


def test_extracts_legacy_paddle_ocr_text():
    result = [[[[0, 0], [1, 0]], ("Recognized line", 0.99)]]
    assert _lines(result) == ["Recognized line"]
