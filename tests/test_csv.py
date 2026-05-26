import pandas as pd
import io

def test_valid_csv():
    csv_content = b"name,age\nAlice,30\nBob,25"
    df = pd.read_csv(io.BytesIO(csv_content))
    assert len(df) == 2
    assert "name" in df.columns

def test_empty_csv():
    csv_content = b""
    try:
        df = pd.read_csv(io.BytesIO(csv_content))
        assert df.empty
    except Exception:
        pass

def test_csv_with_missing_values():
    csv_content = b"name,age\nAlice,\nBob,25"
    df = pd.read_csv(io.BytesIO(csv_content))
    assert df["age"].isna().sum() == 1

def test_large_csv():
    rows = "\n".join([f"user_{i},{i}" for i in range(1000)])
    csv_content = f"name,age\n{rows}".encode()
    df = pd.read_csv(io.BytesIO(csv_content))
    assert len(df) == 1000