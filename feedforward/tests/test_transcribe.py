from core.schemas import Transcript
from core import transcribe


def test_merge_batches(monkeypatch):
    class Page:
        def get_pixmap(self, dpi):
            assert dpi == 200
            return self
        def tobytes(self, fmt):
            return b"png"
    class Document:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def __len__(self): return 5
        def __getitem__(self, _): return Page()
    calls = []
    def mocked(images, resource=False, preceding_question=None):
        calls.append((len(images), preceding_question))
        return Transcript.model_validate({"answers": [{"question_id":"Q1", "text":"[illegible]" if len(calls) == 2 else "Typed or handwritten", "legibility":0.4}]})
    monkeypatch.setattr(transcribe, "read_pdf", lambda _: Document())
    monkeypatch.setattr(transcribe, "transcribe_images", mocked)
    result = transcribe.transcribe_pdf(b"pdf")
    assert calls == [(4, None), (1, "Q1")]
    assert result.answers[0].text == "Typed or handwritten\n[illegible]"
