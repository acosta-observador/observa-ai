import datetime as dt

import pytest

from app import geo
from app.connectors.base import RawDocument, SourceConnector
from app.llm.base import BudgetExceeded, LLMProvider, extract_json
from app.models import Document, Feedback
from app.services import budget, classify, ingest, missions


class MockLLM(LLMProvider):
    name = "mock"

    def __init__(self, items=None, results=None):
        self.calls = []
        self.items, self.results = items, results

    def complete_json(self, system, user, max_tokens=2000):
        self.calls.append((system, user))
        if "<docs>" in user:
            return {"items": self.items(user) if callable(self.items) else self.items}
        return {"results": self.results or [], "answer": "resposta"}


class StubConnector(SourceConnector):
    name = "stub"
    label = "stub"

    def __init__(self, n=3, has_text=True):
        self.n = n
        self.has_text = has_text

    def fetch(self, since):
        return [RawDocument("stub", f"id{i}", f"https://x/{i}", f"Doc {i}", f"texto {i} habitação", published_at=dt.datetime.utcnow()) for i in range(self.n)]


def test_geo_has_308_concelhos_and_regions():
    p = geo.all_places()
    assert len(p["concelhos"]) == 308 and len(p["distritos"]) == 18 and len(p["regioes"]) == 2
    assert geo.locate("Lagoa", "Faro").lat != geo.locate("Lagoa", "Açores").lat
    assert geo.locate(None, "Açores").level == "regiao"


def test_extract_json_tolerates_fences():
    assert extract_json('Aqui:\n```json\n{"a": {"b": 1}}\n```') == {"a": {"b": 1}}


def test_classification_with_mocked_llm(db):
    ingest.app_settings.put(db, "enabled_sources", ["stub"])
    rep = ingest.ingest(db, {"stub": StubConnector(3)})
    assert rep["stub"]["new"] == 3
    llm = MockLLM(items=lambda user: [{"id": d.id, "score": 77, "category": "habitação", "summary": "S", "why": "W",
                                       "people": ["Ana"], "orgs": [], "concelho": "Loures", "distrito": "Lisboa"} for d in db.query(Document).all()])
    stats = classify.classify_pending(db, budget.BudgetedLLM(db, llm))
    assert stats["classified"] == 3
    d = db.query(Document).first()
    assert d.score == 77 and d.category == "habitação" and d.lat is not None and d.concelho == "Loures"
    assert len(llm.calls) == 1  # lote único (3 < tamanho do lote)
    # não reclassifica
    assert classify.classify_pending(db, budget.BudgetedLLM(db, llm))["classified"] == 0
    assert len(llm.calls) == 1


def test_ingest_dedup_and_no_text_status(db):
    ingest.app_settings.put(db, "enabled_sources", ["stub"])
    c = StubConnector(2, has_text=False)
    ingest.ingest(db, {"stub": c})
    assert ingest.ingest(db, {"stub": c})["stub"]["new"] == 0
    assert {d.status for d in db.query(Document)} == {"no_text"}


def test_invalid_llm_values_are_sanitised(db):
    d = Document(source="s", external_id="1", url="u", title="t", text="")
    classify.apply_result(d, {"score": 250, "category": "inventada"})
    assert d.score == 100 and d.category == "outros"


def test_budget_limit_stops_calls(db, monkeypatch):
    monkeypatch.setenv("MAX_LLM_CALLS_PER_DAY", "1")
    llm = budget.BudgetedLLM(db, MockLLM(items=[]))
    llm.complete_json("s", "<docs>[]</docs>")
    with pytest.raises(BudgetExceeded):
        llm.complete_json("s", "<docs>[]</docs>")
    assert budget.calls_today(db) == 1


def test_few_shot_uses_feedback(db):
    a = Document(source="s", external_id="a", url="u", title="Título útil", summary="resumo", status="classified")
    b = Document(source="s", external_id="b", url="u", title="Título ruído", summary="resumo", status="classified")
    db.add_all([a, b]); db.flush()
    db.add_all([Feedback(document_id=a.id, value="useful"), Feedback(document_id=b.id, value="noise")]); db.commit()
    block = classify.few_shot_block(db)
    assert "[ÚTIL]" in block and "Título útil" in block and "[RUÍDO]" in block and "Título ruído" in block


def test_mission_run_creates_alerts_once(db):
    from app.models import Mission
    d = Document(source="dre", external_id="1", url="https://x/1", title="Portaria sobre arrendamento", text="renda habitação",
                 summary="resumo", status="classified", score=80, category="habitação")
    db.add(d)
    m = Mission(name="Habitação", instruction="Avisa-me sobre habitação")
    db.add(m); db.commit()
    llm = MockLLM(results=[{"id": d.id, "match": True, "reason": "fala de habitação", "summary": "sumário"}])
    assert missions.run_mission(db, llm, m) == 1
    m.last_run_at = None
    assert missions.run_mission(db, llm, m) == 0  # deduplicado
    assert m.alerts[0].reason == "fala de habitação"
