from datetime import date


def add_tx(client, when, amount, category=None, description="thing", tx_type="expense"):
    r = client.post("/transactions", json={
        "date": f"{when}T00:00:00", "description": description, "amount": amount,
        "category_path": category, "transaction_type": tx_type,
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_default_categories_seeded(client):
    nodes = client.get("/categories").json()["nodes"]
    assert nodes["groceries"]["parent_id"] == "food_&_dining"


def test_filters_tolerate_missing_fields(client):
    add_tx(client, "2025-01-05", 10)  # no category, no merchant
    add_tx(client, "2025-01-06", 20, category="Food & Dining/Groceries")

    r = client.get("/transactions", params={"category_path": "Groceries", "merchant": "x"})
    assert r.status_code == 200 and r.json()["total"] == 0

    r = client.get("/transactions", params={"category_path": "Food & Dining"})
    assert r.json()["total"] == 1

    r = client.get("/transactions", params={"from_date": "2025-01-06", "to_date": "2025-01-06"})
    assert [t["amount"] for t in r.json()["transactions"]] == [20]


def test_update_transaction_learns_merchant(client):
    tx = add_tx(client, "2025-01-05", 10, description="Woolworths Sandton")
    r = client.patch(f"/transactions/{tx['id']}", json={"category_path": "Food & Dining/Groceries"})
    assert r.status_code == 200
    merchants = client.get("/merchants").json()["merchants"]
    assert merchants[0]["preferred_category"] == "Food & Dining/Groceries"


def test_update_transaction_allows_zero_and_clearing(client):
    tx = add_tx(client, "2025-01-05", 10, category="Food & Dining")
    r = client.patch(f"/transactions/{tx['id']}", json={"category_path": None, "tags": []})
    assert r.json()["category_path"] is None and r.json()["tags"] == []


def test_budget_status_only_counts_current_period(client):
    today = date.today()
    this_month = today.replace(day=1)
    add_tx(client, this_month.isoformat(), 300, category="Food & Dining/Groceries")
    add_tx(client, "2001-01-01", 5000, category="Food & Dining/Groceries")  # long ago
    add_tx(client, this_month.isoformat(), 999, category="Food & Dining/Groceries", tx_type="income")

    client.post("/budgets", json={
        "category_path": "Groceries", "amount": 1000, "period": "monthly", "start_date": "2000-01-01T00:00:00",
    })
    status = client.get("/budgets/status").json()["statuses"][0]
    assert status["spent_amount"] == 300
    assert status["status"] == "ok"


def test_budget_status_prorates_custom_range(client):
    add_tx(client, "2025-03-10", 100, category="Food & Dining")
    client.post("/budgets", json={
        "category_path": "Food & Dining", "amount": 3652.5, "period": "yearly", "start_date": "2025-01-01T00:00:00",
    })
    s = client.get("/budgets/status", params={"from_date": "2025-03-01", "to_date": "2025-03-10"}).json()["statuses"][0]
    assert s["budget_amount"] == 100.0  # 10 days of a 3652.50/year budget
    assert s["spent_amount"] == 100 and s["status"] == "exceeded"


def test_update_budget(client):
    b = client.post("/budgets", json={"amount": 500, "period": "monthly", "start_date": "2025-01-01T00:00:00"}).json()
    r = client.put(f"/budgets/{b['id']}", json={"amount": 750})
    assert r.status_code == 200 and r.json()["amount"] == 750
    assert client.put("/budgets/nope", json={"amount": 1}).status_code == 404


def test_child_budget_cannot_exceed_parent(client):
    client.post("/budgets", json={"category_path": "Food & Dining", "amount": 100, "period": "monthly",
                                  "start_date": "2025-01-01T00:00:00"})
    r = client.post("/budgets", json={"category_path": "Food & Dining/Groceries", "amount": 200,
                                      "period": "monthly", "start_date": "2025-01-01T00:00:00"})
    assert r.status_code == 400


def test_move_category_and_reject_cycles(client):
    r = client.patch("/categories/groceries", json={"parent_id": None})
    tree = r.json()
    assert "groceries" in tree["root_ids"]
    assert "groceries" not in tree["nodes"]["food_&_dining"]["children"]

    r = client.patch("/categories/food_&_dining", json={"parent_id": "restaurants"})
    assert r.status_code == 400


def test_delete_category_uncategorizes_subcategory_transactions(client):
    tx = add_tx(client, "2025-01-05", 10, category="Food & Dining/Groceries")
    other = add_tx(client, "2025-01-05", 10, category="Transportation")
    r = client.delete("/categories/food_&_dining")
    assert r.json()["uncategorized_transactions"] == 1
    assert client.get(f"/transactions/{tx['id']}").json()["category_path"] is None
    assert client.get(f"/transactions/{other['id']}").json()["category_path"] == "Transportation"


CSV = """Account: 12345
Statement period: Jan 2025
Date,Description,Amount,Balance
2025/01/02,Coffee Shop,-35.00,1000
2025/01/02,Coffee Shop,-35.00,965
2025/01/03,Salary,"20,000.00",20965
2025/01/04,Broken row,abc,0
"""


def test_csv_import_keeps_repeated_rows_and_detects_reimport(client, storage):
    r = client.post("/imports/bank-csv", json={"file_content": CSV}).json()
    assert r["imported"] == 3 and r["duplicates"] == 0 and r["skipped"] == 1
    assert r["ai_error"]  # AI disabled in tests, import still succeeds

    txs = storage.get_transactions()
    assert sorted(t["transaction_type"] for t in txs) == ["expense", "expense", "income"]

    r = client.post("/imports/bank-csv", json={"file_content": CSV}).json()
    assert r["imported"] == 0 and r["duplicates"] == 3


def test_csv_import_debit_credit_columns_and_learned_category(client, storage):
    storage.create_merchant({"name": "spar", "aliases": ["spar"], "preferred_category": "Food & Dining/Groceries"})
    csv_text = "Posting Date,Details,Debit,Credit\n05/01/2025,SPAR,120.50,\n06/01/2025,Refund,,40\n"
    r = client.post("/imports/bank-csv", json={"file_content": csv_text}).json()
    assert r["imported"] == 2 and r["learned_categorised"] == 1
    by_desc = {t["description"]: t for t in storage.get_transactions()}
    assert by_desc["SPAR"]["category_path"] == "Food & Dining/Groceries"
    assert by_desc["SPAR"]["transaction_type"] == "expense"
    assert by_desc["Refund"]["transaction_type"] == "income"


def test_csv_import_uses_ai_for_unknowns(client, storage, fake_ai):
    fake_ai("Transportation/Petrol")
    r = client.post("/imports/bank-csv", json={"file_content": "Date,Description,Amount\n2025-01-01,ENGEN,-500\n"}).json()
    assert r["ai_categorised"] == 1
    assert storage.get_transactions()[0]["category_path"] == "Transportation/Petrol"


def test_csv_without_required_columns_is_rejected(client):
    r = client.post("/imports/bank-csv", json={"file_content": "foo,bar\n1,2\n"})
    assert r.status_code == 400


def test_smart_transaction_without_ai_still_creates(client):
    r = client.post("/transactions/smart", json={"description": "chow", "amount": "150"})
    assert r.status_code == 200
    assert r.json()["transaction"]["amount"] == 150 and r.json()["transaction"]["category_path"] is None


def test_smart_transaction_uses_ai_suggestion(client, fake_ai):
    fake_ai('Sure! {"description": "Chow", "suggested_category": "Food & Dining/Takeout"}')
    r = client.post("/transactions/smart", json={"description": "chow", "amount": "150"}).json()
    assert r["transaction"]["category_path"] == "Food & Dining/Takeout"
    assert r["category_created"] is False


def test_smart_transaction_prefers_learned_category(client, storage, fake_ai):
    ai = fake_ai('{"suggested_category": "Shopping"}')
    storage.create_merchant({"name": "chow", "aliases": ["chow"], "preferred_category": "Food & Dining"})
    r = client.post("/transactions/smart", json={"description": "Chow", "amount": "10"}).json()
    assert r["transaction"]["category_path"] == "Food & Dining"
    assert ai.prompts == []


def test_duplicates_and_ignore(client):
    a = add_tx(client, "2025-01-05", 10, description="a")
    b = add_tx(client, "2025-01-05", 10, description="b")
    add_tx(client, "2025-01-06", 10, description="c")

    groups = client.get("/duplicates").json()["groups"]
    assert len(groups) == 1 and {t["id"] for t in groups[0]["transactions"]} == {a["id"], b["id"]}

    client.post("/duplicates/ignore", json={"pairs": [[b["id"], a["id"]]]})
    assert client.get("/duplicates").json()["groups"] == []


def test_not_found_responses(client):
    assert client.delete("/transactions/nope").status_code == 404
    assert client.delete("/budgets/nope").status_code == 404
    assert client.delete("/merchants/nope").status_code == 404
    assert client.delete("/categories/nope").status_code == 404


def test_category_filter_matches_whole_segments(client):
    add_tx(client, "2025-01-05", 10, category="Transportation/Petrol/Diesel")  # a category named "Petrol/Diesel"
    add_tx(client, "2025-01-05", 20, category="Food & Dining")
    assert client.get("/transactions", params={"category_path": "Petrol/Diesel"}).json()["total"] == 1
    assert client.get("/transactions", params={"category_path": "Food"}).json()["total"] == 0
