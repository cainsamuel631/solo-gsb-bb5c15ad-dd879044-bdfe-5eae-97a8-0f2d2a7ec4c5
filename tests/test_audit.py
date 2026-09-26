from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ok_tightens_intervals_and_orders():
    payload = {
        "strata": [
            {"id": "A", "min_age": 5, "max_age": 25},
            {"id": "B", "min_age": 8, "max_age": 20},
            {"id": "C", "min_age": 9, "max_age": 15},
        ],
        "relations": [
            {"older": "B", "younger": "A"},
            {"older": "A", "younger": "C"},
        ],
    }
    resp = client.post("/audit", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # 上界下压：A <= 20-1=19；下界上抬：A >= 9+1=10，B >= 10+1=11
    assert body["intervals"] == {
        "A": {"min_age": 10, "max_age": 19},
        "B": {"min_age": 11, "max_age": 20},
        "C": {"min_age": 9, "max_age": 15},
    }
    assert body["order"] == ["B", "A", "C"]


def test_lexicographically_smallest_order():
    payload = {
        "strata": [
            {"id": "C", "min_age": 1, "max_age": 100},
            {"id": "A", "min_age": 1, "max_age": 100},
            {"id": "B", "min_age": 1, "max_age": 100},
        ],
        "relations": [{"older": "B", "younger": "A"}],
    }
    body = client.post("/audit", json=payload).json()
    assert body["status"] == "ok"
    # 合法拓扑序有 BAC / BCA / CBA，字典序最小为 BAC
    assert body["order"] == ["B", "A", "C"]


def test_cycle_returns_path():
    payload = {
        "strata": [
            {"id": "A", "min_age": 1, "max_age": 100},
            {"id": "B", "min_age": 1, "max_age": 100},
            {"id": "C", "min_age": 1, "max_age": 100},
        ],
        "relations": [
            {"older": "A", "younger": "B"},
            {"older": "B", "younger": "C"},
            {"older": "C", "younger": "A"},
        ],
    }
    body = client.post("/audit", json=payload).json()
    assert body["status"] == "cycle"
    path = body["cycle"]
    assert path[0] == path[-1]
    assert len(path) == 4  # 三个地层 + 回到起点
    edges = {("A", "B"), ("B", "C"), ("C", "A")}
    assert all((a, b) in edges for a, b in zip(path, path[1:]))


def test_conflict_points_out_emptied_strata():
    payload = {
        "strata": [
            {"id": "A", "min_age": 5, "max_age": 8},
            {"id": "B", "min_age": 10, "max_age": 20},
        ],
        "relations": [{"older": "A", "younger": "B"}],
    }
    body = client.post("/audit", json=payload).json()
    assert body["status"] == "conflict"
    conflicts = {c["id"]: c for c in body["conflicts"]}
    # B 的上界被压到 8-1=7 < 10；A 的下界被抬到 10+1=11 > 8
    assert set(conflicts) == {"A", "B"}
    assert conflicts["B"] == {"id": "B", "min_age": 10, "max_age": 7}
    assert conflicts["A"] == {"id": "A", "min_age": 11, "max_age": 8}


def test_duplicate_ids_rejected():
    payload = {
        "strata": [
            {"id": "A", "min_age": 1, "max_age": 2},
            {"id": "A", "min_age": 3, "max_age": 4},
        ],
        "relations": [],
    }
    assert client.post("/audit", json=payload).status_code == 422


def test_self_relation_rejected():
    payload = {
        "strata": [{"id": "A", "min_age": 1, "max_age": 2}],
        "relations": [{"older": "A", "younger": "A"}],
    }
    assert client.post("/audit", json=payload).status_code == 422


def test_unknown_stratum_rejected():
    payload = {
        "strata": [{"id": "A", "min_age": 1, "max_age": 2}],
        "relations": [{"older": "A", "younger": "ZZZ"}],
    }
    assert client.post("/audit", json=payload).status_code == 422


def test_empty_interval_rejected():
    payload = {
        "strata": [{"id": "A", "min_age": 9, "max_age": 2}],
        "relations": [],
    }
    assert client.post("/audit", json=payload).status_code == 422


def test_no_relations_sorted_by_id():
    payload = {
        "strata": [
            {"id": "B", "min_age": 1, "max_age": 5},
            {"id": "A", "min_age": 10, "max_age": 20},
        ],
        "relations": [],
    }
    body = client.post("/audit", json=payload).json()
    assert body["status"] == "ok"
    assert body["order"] == ["A", "B"]
    assert body["intervals"]["A"] == {"min_age": 10, "max_age": 20}
