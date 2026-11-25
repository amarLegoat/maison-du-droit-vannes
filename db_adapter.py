import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import pandas as pd


def resolve_db_url(explicit_url=None):
    """Résout la cible BDD : argument > variable d'env DATABASE_URL / SUPABASE_URL > SQLite local."""
    if explicit_url and str(explicit_url).strip():
        return str(explicit_url).strip()
    env_url = os.environ.get("DATABASE_URL", "").strip()
    if env_url:
        return env_url
    supa_url = os.environ.get("SUPABASE_URL", "").strip()
    if supa_url:
        return supa_url
    return "sqlite:///maison_droit.db"


def resolve_supabase_key(explicit_key=None):
    if explicit_key and str(explicit_key).strip():
        return str(explicit_key).strip()
    for var_name in ("SUPABASE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY"):
        val = os.environ.get(var_name, "").strip()
        if val:
            return val
    return ""


class SupabaseHttpsBackend:
    """
    Client léger passant 100 % par l'API REST HTTPS Supabase (port 443) :
    contourne le blocage des ports PostgreSQL (5432 / 6543) sur le réseau de l'IUT.
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        if not self.api_key:
            raise ValueError(
                "La clé API publique Supabase (anon / publishable) est requise pour utiliser le mode HTTPS (port 443)."
            )

    def _headers(self, prefer=None):
        h = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def _request(self, method: str, path: str, params: dict = None, payload=None, prefer: str = None):
        url = f"{self.base_url}/rest/v1/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params, safe="(),.*:")
        data_bytes = json.dumps(payload, default=str).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data_bytes, headers=self._headers(prefer=prefer), method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
                if not body.strip():
                    return []
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Erreur API HTTPS Supabase ({exc.code}) sur '{path}': {err_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Erreur réseau HTTPS vers Supabase : {exc.reason}") from exc

    def select_all(self, table: str, order_by: str = None, page_size: int = 1000) -> list[dict]:
        all_rows = []
        offset = 0
        while True:
            params = {"select": "*", "limit": str(page_size), "offset": str(offset)}
            if order_by:
                params["order"] = order_by
            batch = self._request("GET", table, params=params)
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return all_rows

    def insert_ignore_conflict(self, table: str, rows: list[dict], on_conflict: str = None):
        if not rows:
            return
        params = {"on_conflict": on_conflict} if on_conflict else None
        self._request("POST", table, params=params, payload=rows, prefer="resolution=ignore-duplicates,return=minimal")

    def insert_one_returning(self, table: str, row: dict, id_col: str):
        res = self._request("POST", table, payload=row, prefer="return=representation")
        if isinstance(res, list) and res and id_col in res[0]:
            return res[0][id_col]
        if isinstance(res, dict) and id_col in res:
            return res[id_col]
        return None

    def insert_many(self, table: str, rows: list[dict], chunk_size: int = 500):
        for i in range(0, len(rows), chunk_size):
            self._request("POST", table, payload=rows[i:i + chunk_size], prefer="return=minimal")

    def delete_where(self, table: str, col: str, op: str, val):
        self._request("DELETE", table, params={col: f"{op}.{val}"}, prefer="return=minimal")


class UniversalDB:
    """
    Adaptateur universel :
    1) Supabase HTTPS REST API (https://...supabase.co + clé anon/publishable) -> Port 443, non bloqué à l'IUT
    2) PostgreSQL direct (postgresql://...) -> Ports 5432/6543 (Streamlit Cloud / réseau ouvert)
    3) SQLite local (sqlite:///maison_droit.db) -> Fichier local hors-ligne
    """

    def __init__(self, db_url=None, supabase_key=None):
        self.db_url = resolve_db_url(db_url)
        if self.db_url.startswith("postgres://"):
            self.db_url = "postgresql://" + self.db_url[len("postgres://"):]

        self.is_https_supabase = self.db_url.startswith("https://")
        self.is_postgres = self.db_url.startswith("postgresql://")

        if self.is_https_supabase:
            key = resolve_supabase_key(supabase_key)
            self.https = SupabaseHttpsBackend(self.db_url, key)
            self.conn = None
        elif self.is_postgres:
            try:
                import psycopg2
            except ImportError as exc:
                raise ImportError(
                    "Le pilote 'psycopg2-binary' est requis pour postgresql://. "
                    "Installez-le avec : pip install psycopg2-binary"
                ) from exc
            self.conn = psycopg2.connect(self.db_url)
            self.conn.autocommit = False
            self.https = None
        else:
            path = self.db_url.replace("sqlite:///", "") if self.db_url.startswith("sqlite:///") else self.db_url
            self.sqlite_path = path
            self.conn = sqlite3.connect(path, check_same_thread=False)
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.https = None

    def _adapt_sql(self, sql):
        if self.is_postgres:
            return sql.replace("?", "%s")
        return sql

    def execute(self, sql, params=None):
        cur = self.conn.cursor()
        q = self._adapt_sql(sql)
        if params is not None:
            cur.execute(q, params)
        else:
            cur.execute(q)
        return cur

    def executemany(self, sql, seq_params):
        if not seq_params:
            return
        cur = self.conn.cursor()
        q = self._adapt_sql(sql)
        cur.executemany(q, seq_params)
        return cur

    def executescript(self, script_sql):
        cur = self.conn.cursor()
        if self.is_postgres:
            for stmt in script_sql.split(";"):
                s = stmt.strip()
                if s:
                    cur.execute(s)
        else:
            cur.executescript(script_sql)

    def fetchone(self, sql, params=None):
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql, params=None):
        cur = self.execute(sql, params)
        return cur.fetchall()

    def insert_returning_id(self, sql_with_returning, params):
        cur = self.execute(sql_with_returning, params)
        row = cur.fetchone()
        return row[0] if row else None

    def read_df(self, sql, params=None):
        q = self._adapt_sql(sql)
        if self.is_postgres:
            cur = self.conn.cursor()
            cur.execute(q, params or ())
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        return pd.read_sql_query(q, self.conn, params=params)

    def commit(self):
        if self.conn is not None:
            self.conn.commit()

    def close(self):
        if self.conn is not None:
            self.conn.close()
