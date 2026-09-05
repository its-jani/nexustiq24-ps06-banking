import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ROUTINE = (
    "date,description,payee,amount,channel\n"
    "2024-01-05,Grocery,Store,-45.00,card\n"
    "2024-01-12,Grocery,Store,-52.00,card\n"
    "2024-01-19,Salary,Acme,2000.00,direct_deposit\n"
    "2024-01-26,Grocery,Store,-48.00,card\n"
)

SUSPICIOUS = ROUTINE + "2024-02-10,Wire,Shell Escrow,-12000.00,wire\n"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ui_page_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>PS06" in r.text


def test_routine_csv_returns_clean():
    r = client.post("/investigate", files={"file": ("customer.csv", io.BytesIO(ROUTINE.encode()), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "CLEAN"
    assert body["findings"] == []
    assert body["cited_transactions"] == []
    assert body["case_id"]


def test_suspicious_csv_returns_needs_review_with_cited_rows():
    r = client.post("/investigate", files={"file": ("customer.csv", io.BytesIO(SUSPICIOUS.encode()), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "NEEDS REVIEW"
    rows = {t["row"] for t in body["cited_transactions"]}
    assert rows <= {2, 3, 4, 5, 6}  # all present in the input CSV
    assert 6 in rows  # the -12000 wire
    assert "fraud" not in body["narrative"].lower()


def test_ingest_error_returns_400():
    bad = "date,payee,amount\n2024-01-05,X,10\n"  # missing description/channel
    r = client.post("/investigate", files={"file": ("c.csv", io.BytesIO(bad.encode()), "text/csv")})
    assert r.status_code == 400


def test_case_retrievable_by_id():
    r = client.post("/investigate", files={"file": ("c.csv", io.BytesIO(ROUTINE.encode()), "text/csv")})
    case_id = r.json()["case_id"]
    r2 = client.get(f"/investigate/{case_id}")
    assert r2.status_code == 200
    assert r2.json()["verdict"] == "CLEAN"


def test_missing_case_404():
    assert client.get("/investigate/doesnotexist").status_code == 404


def test_same_input_gets_distinct_case_ids():
    ids = set()
    for _ in range(3):
        r = client.post("/investigate", files={"file": ("c.csv", io.BytesIO(ROUTINE.encode()), "text/csv")})
        ids.add(r.json()["case_id"])
    assert len(ids) == 3