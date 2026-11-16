from app.models import Document, utcnow


def _doc(db, **kw):
    d = Document(source="dre", external_id=kw.pop("eid", "1"), url="https://x", title=kw.pop("title", "T"), status="classified",
                 score=kw.pop("score", 80), category=kw.pop("category", "política"), published_at=utcnow(), **kw)
    db.add(d); db.commit()
    return d


def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_requires_login(client):
    assert client.get("/api/alerts").status_code == 401
    assert client.post("/api/login", json={"password": "errada"}).status_code == 401
    assert client.post("/api/login", json={"password": "segredo"}).status_code == 200
    assert client.get("/api/alerts").status_code == 200


def test_threshold_hides_low_scores_and_feedback_roundtrip(client, db):
    hi = _doc(db, eid="a", score=90)
    _doc(db, eid="b", score=10)
    client.post("/api/login", json={"password": "segredo"})
    assert [a["id"] for a in client.get("/api/alerts").json()] == [hi.id]
    assert len(client.get("/api/alerts?include_hidden=true").json()) == 2
    assert client.post(f"/api/alerts/{hi.id}/feedback", json={"value": "useful"}).status_code == 200
    assert client.get("/api/alerts").json()[0]["feedback"] == "useful"
    assert client.post(f"/api/alerts/{hi.id}/feedback", json={"value": "xx"}).status_code == 422
    stats = client.get("/api/feedback/stats").json()
    assert stats["total"] == 1 and stats["rate"] == 100


def test_missions_crud_and_search(client, db):
    _doc(db, eid="c", title="Portaria de habitação", summary="renda habitação", text="habitação")
    client.post("/api/login", json={"password": "segredo"})
    m = client.post("/api/missions", json={"name": "H", "instruction": "habitação em portarias"}).json()
    assert client.patch(f"/api/missions/{m['id']}", json={"active": False}).json()["active"] is False
    r = client.post("/api/search", json={"question": "habitação"}).json()  # provider fake
    assert r["results"] and r["results"][0]["url"] == "https://x"
    assert client.delete(f"/api/missions/{m['id']}").status_code == 200
