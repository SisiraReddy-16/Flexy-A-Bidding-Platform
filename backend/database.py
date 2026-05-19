import httpx

_url: str = None   # e.g. https://xxx.supabase.co
_key: str = None   # service_role JWT


def init_db(app):
    global _url, _key
    _url = (app.config.get('SUPABASE_URL') or '').rstrip('/')
    _key = app.config.get('SUPABASE_KEY') or ''

    if not _url or not _key:
        print('[DB] Warning: SUPABASE_URL or SUPABASE_KEY not set.')
        return

    try:
        resp = httpx.get(
            f'{_url}/rest/v1/',
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code < 500:
            print('[DB] Connected to Supabase successfully.')
        else:
            print(f'[DB] Warning: Supabase returned {resp.status_code}')
    except Exception as e:
        # Don't crash on startup — just warn. Real errors surface on first query.
        print(f'[DB] Warning: Could not reach Supabase at startup: {e}')
        print('[DB] Check your SUPABASE_URL in .env — make sure it is your real project URL.')


def _headers() -> dict:
    return {
        'apikey':        _key,
        'Authorization': f'Bearer {_key}',
        'Content-Type':  'application/json',
        'Prefer':        'return=representation',
    }


def get_db() -> 'SupabaseClient':
    if not _url or not _key:
        raise RuntimeError('Database not initialised. Check SUPABASE_URL and SUPABASE_KEY in .env')
    return SupabaseClient(_url, _headers())


# ── Lightweight PostgREST client ──────────────────────────────

class SupabaseClient:
    def __init__(self, base_url: str, headers: dict):
        self._base = base_url
        self._h    = headers

    def table(self, name: str) -> 'QueryBuilder':
        return QueryBuilder(f"{self._base}/rest/v1/{name}", self._h)


class QueryBuilder:
    def __init__(self, url: str, headers: dict):
        self._url        = url
        self._headers    = dict(headers)
        self._filters    = []
        self._select     = '*'
        self._order      = None
        self._limit      = None
        self._range      = None
        self._count      = None
        self._pending_op = 'select'
        self._pending_data = None

    def select(self, cols: str = '*', count: str = None):
        self._select = cols
        if count:
            self._count = count
            self._headers['Prefer'] = f'count={count}'
        return self

    def eq(self, col, val):
        self._filters.append(f'{col}=eq.{val}')
        return self

    def neq(self, col, val):
        self._filters.append(f'{col}=neq.{val}')
        return self

    def lt(self, col, val):
        self._filters.append(f'{col}=lt.{val}')
        return self

    def lte(self, col, val):
        self._filters.append(f'{col}=lte.{val}')
        return self

    def gt(self, col, val):
        self._filters.append(f'{col}=gt.{val}')
        return self

    def gte(self, col, val):
        self._filters.append(f'{col}=gte.{val}')
        return self

    def ilike(self, col, pattern):
        self._filters.append(f'{col}=ilike.{pattern}')
        return self

    def is_(self, col, val):
        v = 'null' if val is None else str(val).lower()
        self._filters.append(f'{col}=is.{v}')
        return self

    def in_(self, col, vals):
        self._filters.append(f'{col}=in.({",".join(str(v) for v in vals)})')
        return self

    def order(self, col, desc: bool = False):
        self._order = f'{col}.{"desc" if desc else "asc"}'
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def range(self, start: int, end: int):
        self._range = (start, end)
        return self

    def insert(self, data: dict):
        self._pending_op   = 'insert'
        self._pending_data = data
        return self

    def update(self, data: dict):
        self._pending_op   = 'update'
        self._pending_data = data
        return self

    def delete(self):
        self._pending_op = 'delete'
        return self

    def _build_url(self) -> str:
        params = [f'select={self._select}']
        params.extend(self._filters)
        if self._order:
            params.append(f'order={self._order}')
        if self._limit is not None:
            params.append(f'limit={self._limit}')
        return self._url + ('?' + '&'.join(params) if params else '')

    def _req_headers(self) -> dict:
        h = dict(self._headers)
        if self._range:
            h['Range'] = f'{self._range[0]}-{self._range[1]}'
        return h

    def execute(self) -> 'Result':
        op = self._pending_op
        if op == 'insert':
            url  = f'{self._url}?select={self._select}'
            resp = httpx.post(url, headers=self._headers, json=self._pending_data, timeout=15)
        elif op == 'update':
            url  = self._build_url()
            resp = httpx.patch(url, headers=self._headers, json=self._pending_data, timeout=15)
        elif op == 'delete':
            url  = self._build_url()
            resp = httpx.delete(url, headers=self._headers, timeout=15)
        else:
            url  = self._build_url()
            resp = httpx.get(url, headers=self._req_headers(), timeout=15)

        if resp.status_code >= 400:
            raise RuntimeError(f'Supabase {resp.status_code}: {resp.text[:300]}')

        try:
            data = resp.json()
        except Exception:
            data = []
        if not isinstance(data, list):
            data = [data] if data else []

        count = None
        if self._count:
            cr = resp.headers.get('Content-Range', '')
            if '/' in cr:
                try:
                    count = int(cr.split('/')[1])
                except Exception:
                    count = len(data)
        return Result(data, count)


class Result:
    def __init__(self, data: list, count=None):
        self.data  = data
        self.count = count