import os
from pathlib import Path
from datetime import date
import pandas as pd
import re
import unicodedata
from sqlalchemy import create_engine

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"
LAKE = BASE / "lake"

# --- util ----------------------------------------------------------
def _snake(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

def _strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

def _parse_price(v):
    if pd.isna(v): return None
    s = str(v)
    s = _strip_accents(s).replace("€","").replace(" ", "")
    if s.lower() in ("", "nd", "none", "-", "nan"): return None
    s = s.replace(".", "")  # migliaia IT
    s = s.replace(",", ".") # decimali IT
    m = re.findall(r"\d+(?:\.\d+)?", s)
    return float(m[0]) if m else None

def _parse_number(v):
    if pd.isna(v): return None
    s = str(v).strip()
    if s.lower() in ("", "nd", "none", "-", "nan"): return None
    s = s.replace(".", "").replace(",", ".")
    m = re.findall(r"\d+(?:\.\d+)?", s)
    return float(m[0]) if m else None

def _parse_pair_slash(v):
    if pd.isna(v): return (None, None)
    s = str(v).strip().replace(",", ".")
    if s.lower() in ("", "nd", "none", "-", "nan"): return (None, None)
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if len(nums) >= 2: return (float(nums[0]), float(nums[1]))
    if len(nums) == 1: return (float(nums[0]), None)
    return (None, None)

def _find_first_col(cols, patterns):
    # cerca la prima colonna che matcha una lista di regex (case/accents insensitive)
    norm = {c: _strip_accents(c.lower()) for c in cols}
    for pat in patterns:
        r = re.compile(pat)
        for c, v in norm.items():
            if r.search(v):
                return c
    return None

# --- IO raw --------------------------------------------------------
def _pick_raw():
    for cand in [DATA/"raw"/"auto_dati.csv", DATA/"raw"/"auto_dati.xlsx"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("Metti auto_dati.csv o auto_dati.xlsx in data/raw/")

def ensure_dirs(ds: str):
    (LAKE/"bronze"/"auto"/f"dt={ds}").mkdir(parents=True, exist_ok=True)
    (LAKE/"silver"/"auto"/f"dt={ds}").mkdir(parents=True, exist_ok=True)
    (LAKE/"gold"/"brand_stats"/f"dt={ds}").mkdir(parents=True, exist_ok=True)

def ingest_bronze(ds: str, raw_path: Path):
    if raw_path.suffix.lower() == ".xlsx":
        try:
            import openpyxl  # noqa
        except ImportError:
            raise ImportError("Per .xlsx installa: pip install openpyxl")
        df = pd.read_excel(raw_path, engine="openpyxl")
    else:
        df = pd.read_csv(raw_path)
    out = LAKE/"bronze"/"auto"/f"dt={ds}"/"auto_raw.csv"
    df.to_csv(out, index=False)
    return out

# --- silver --------------------------------------------------------
def silver_transform(ds: str):
    raw = LAKE/"bronze"/"auto"/f"dt={ds}"/"auto_raw.csv"
    df = pd.read_csv(raw)

    # normalizza i nomi colonne
    original_cols = list(df.columns)
    df.columns = [_snake(c) for c in df.columns]
    cols = list(df.columns)

    # 1) Mappa sinonimi per chiavi principali
    mapping = {}
    if "marca" not in cols:
        c = _find_first_col(cols, [r"\bmarca\b", r"\bbrand\b", r"costruttor", r"\bcasa\b"])
        if c: mapping[c] = "marca"
    if "modello" not in cols:
        c = _find_first_col(cols, [r"\bmodello\b", r"\bmodel\b"])
        if c: mapping[c] = "modello"
    if "versione" not in cols:
        c = _find_first_col(cols, [r"\bversione\b", r"allestiment", r"\btrim\b", r"variante"])
        if c: mapping[c] = "versione"

    # prezzo (se non già presente sotto 'prezzo')
    price_col = "prezzo" if "prezzo" in cols else _find_first_col(
        cols, [r"prezz", r"listino", r"price"]
    )
    if price_col and price_col != "prezzo":
        mapping[price_col] = "prezzo"

    # capacità batteria kWh
    batt_col = "capacita_batteria_kwh" if "capacita_batteria_kwh" in cols else _find_first_col(
        cols, [r"batteria.*kwh", r"capacita.*kwh", r"kwh.*batter"]
    )
    if batt_col and batt_col != "capacita_batteria_kwh":
        mapping[batt_col] = "capacita_batteria_kwh"

    # applica rename se necessario
    if mapping:
        df = df.rename(columns=mapping)
        cols = list(df.columns)

    # 2) Parsing campi
    if "prezzo" in df:
        df["prezzo_eur"] = df["prezzo"].apply(_parse_price)

    # alcuni numerici frequenti (se presenti)
    for col in [
        "lunghezza","larghezza","altezza","cilindri","cilindrata_cm3","peso_kg",
        "autonomia_km","capacita_batteria_kwh","velocita_max_kmh"
    ]:
        if col in df:
            df[col] = df[col].apply(_parse_number)

    # posti/bagagliaio/potenza come coppie
    if "posti" in df:
        df["posti_min"] = df["posti"].apply(lambda x: _parse_pair_slash(x)[0])
        df["posti_max"] = df["posti"].apply(lambda x: _parse_pair_slash(x)[1])
    if "bagagliaio" in df:
        df["bagagliaio_min"] = df["bagagliaio"].apply(lambda x: _parse_pair_slash(x)[0])
        df["bagagliaio_max"] = df["bagagliaio"].apply(lambda x: _parse_pair_slash(x)[1])
    # potenze in forma "95/70"
    for src, pref in [
        ("potenza_cv_kw", ""),
        ("potenza_termico_cv_kw", "termico_"),
        ("potenza_omologata_cv_kw", "omologata_"),
    ]:
        if src in df:
            a = df[src].apply(lambda s: pd.Series(_parse_pair_slash(s), index=[f"{pref}cv", f"{pref}kw"]))
            a.columns = [f"{pref}potenza_cv", f"{pref}potenza_kw"]
            df = pd.concat([df, a], axis=1)

    out = LAKE/"silver"/"auto"/f"dt={ds}"/"auto_clean.parquet"
    df.to_parquet(out, index=False)
    return out

# --- gold ----------------------------------------------------------
def gold_brand_stats(ds: str):
    silver = LAKE/"silver"/"auto"/f"dt={ds}"/"auto_clean.parquet"
    df = pd.read_parquet(silver)

    # verifichiamo le tre chiavi base con fallback già fatto in silver
    for req in ["marca", "modello", "versione"]:
        if req not in df.columns:
            raise ValueError(f"Manca la colonna richiesta '{req}'. Colonne disponibili: {list(df.columns)}")

    agg_spec = dict(n_versioni=("versione", "count"))
    if "prezzo_eur" in df:
        agg_spec.update(
            prezzo_medio=("prezzo_eur", "mean"),
            prezzo_min=("prezzo_eur", "min"),
            prezzo_max=("prezzo_eur", "max"),
        )
    if "capacita_batteria_kwh" in df:
        agg_spec["batteria_media_kwh"] = ("capacita_batteria_kwh", "mean")

    g = df.groupby("marca", as_index=False).agg(**agg_spec).sort_values(
        list(agg_spec.keys())[1] if len(agg_spec) > 1 else "n_versioni",
        ascending=False
    )

    out = LAKE/"gold"/"brand_stats"/f"dt={ds}"/"brand_stats.parquet"
    g.to_parquet(out, index=False)
    return g

# --- publish -------------------------------------------------------
def publish_to_postgres(df: pd.DataFrame):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError("Setta DATABASE_URL, es: postgresql+psycopg://analytics:analytics@localhost:5432/analytics")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        df.to_sql("brand_stats", conn, schema="public", if_exists="replace", index=False)

# --- main ----------------------------------------------------------
def main():
    ds = os.environ.get("RUN_DATE") or date.today().isoformat()
    ensure_dirs(ds)
    raw = _pick_raw()
    ingest_bronze(ds, raw)
    silver_transform(ds)
    g = gold_brand_stats(ds)
    publish_to_postgres(g)
    print("DONE → gold brand_stats → Postgres (public.brand_stats)")

if __name__ == "__main__":
    main()