"""
持仓管理数据库模块

使用 SQLite 存储持仓、交易记录和账户信息。
"""

try:
    import sqlite3
except ImportError:
    import pysqlite3 as sqlite3

import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 数据库路径
DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "portfolio.db"

# A 股交易规则
MIN_SHARES = 100
SHARES_LOT = 100
COMMISSION_RATE = 0.00015
STAMP_TAX_RATE = 0.001
MIN_COMMISSION = 5.0
TRANSFER_FEE_RATE = 0.00001


class PortfolioDB:
    """持仓管理数据库"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._local = threading.local()
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def transaction(self):
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'SIM' CHECK(mode IN ('SIM', 'REAL')),
                    initial_capital REAL NOT NULL DEFAULT 1000000,
                    current_capital REAL NOT NULL DEFAULT 1000000,
                    strategy_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(name, mode)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    buy_threshold REAL NOT NULL DEFAULT 30.0,
                    take_profit REAL NOT NULL DEFAULT 0.20,
                    stop_loss REAL NOT NULL DEFAULT 0.08,
                    cooldown_days INTEGER NOT NULL DEFAULT 1,
                    max_position_pct REAL NOT NULL DEFAULT 0.20,
                    max_positions INTEGER NOT NULL DEFAULT 5,
                    description TEXT,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    shares INTEGER NOT NULL,
                    cost_price REAL NOT NULL,
                    current_price REAL,
                    buy_date TEXT NOT NULL,
                    buy_score REAL,
                    closed_at TEXT,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('BUY', 'SELL')),
                    price REAL NOT NULL,
                    shares INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL DEFAULT 0,
                    stamp_tax REAL NOT NULL DEFAULT 0,
                    trade_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    score REAL,
                    reason TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_nav (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    nav REAL NOT NULL,
                    total_assets REAL NOT NULL,
                    position_value REAL NOT NULL,
                    cash REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                    UNIQUE(account_id, date)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS trade_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    buy_date TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    buy_shares INTEGER NOT NULL,
                    sell_date TEXT,
                    sell_price REAL,
                    sell_shares INTEGER DEFAULT 0,
                    remaining_shares INTEGER NOT NULL,
                    buy_score REAL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS dividends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    ex_date TEXT NOT NULL,
                    dividend_per_share REAL NOT NULL,
                    shares INTEGER NOT NULL,
                    total_amount REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_account_date ON trades(account_id, trade_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_account_code ON trades(account_id, code)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_lots_account_code ON trade_lots(account_id, code, buy_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_positions_account_code ON positions(account_id, code)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_accounts_mode ON accounts(mode)")

    def create_account(self, name: str, mode: str = 'SIM', initial_capital: float = 1000000,
                      strategy_id: int = None) -> int:
        """创建账户（mode: SIM=模拟仓, REAL=实盘）"""
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO accounts (name, mode, initial_capital, current_capital, strategy_id) VALUES (?, ?, ?, ?, ?)",
                (name, mode, initial_capital, initial_capital, strategy_id)
            )
            return c.lastrowid

    # ========== 策略操作 ==========

    def create_strategy(self, name: str, buy_threshold: float = 30.0,
                        take_profit: float = 0.20, stop_loss: float = 0.08,
                        cooldown_days: int = 1, max_position_pct: float = 0.20,
                        max_positions: int = 5, description: str = None,
                        is_default: int = 0) -> int:
        """创建策略"""
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO strategies
                (name, buy_threshold, take_profit, stop_loss, cooldown_days,
                 max_position_pct, max_positions, description, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, buy_threshold, take_profit, stop_loss, cooldown_days,
                  max_position_pct, max_positions, description, is_default))
            return c.lastrowid

    def list_strategies(self) -> List[Dict]:
        """列出所有策略"""
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM strategies ORDER BY id")
        return [dict(r) for r in c.fetchall()]

    def get_strategy(self, strategy_id: int) -> Optional[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,))
        row = c.fetchone()
        return dict(row) if row else None

    def get_default_strategy(self) -> Optional[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM strategies WHERE is_default = 1 LIMIT 1")
        row = c.fetchone()
        if not row:
            c.execute("SELECT * FROM strategies ORDER BY id LIMIT 1")
            row = c.fetchone()
        return dict(row) if row else None

    def update_strategy(self, strategy_id: int, **kwargs) -> Dict:
        """更新策略"""
        allowed = ['name', 'buy_threshold', 'take_profit', 'stop_loss',
                   'cooldown_days', 'max_position_pct', 'max_positions',
                   'description', 'is_default']
        sets = []
        values = []
        for k in allowed:
            if k in kwargs:
                sets.append(f"{k} = ?")
                values.append(kwargs[k])
        if not sets:
            return {'success': False, 'error': '无更新字段'}
        values.append(strategy_id)
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute(f"UPDATE strategies SET {', '.join(sets)}, updated_at = datetime('now', 'localtime') WHERE id = ?",
                      values)
        return {'success': True}

    def delete_strategy(self, strategy_id: int) -> Dict:
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM accounts WHERE strategy_id = ?", (strategy_id,))
            if c.fetchone():
                return {'success': False, 'error': '该策略正被账户使用，无法删除'}
            c.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
        return {'success': True}

    def set_account_strategy(self, account_id: int, strategy_id: int) -> Dict:
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute("UPDATE accounts SET strategy_id = ? WHERE id = ?", (strategy_id, account_id))
        return {'success': True}

    def get_account(self, account_id: int) -> Optional[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = c.fetchone()
        return dict(row) if row else None

    def get_account_by_name(self, name: str, mode: str = None) -> Optional[Dict]:
        c = self._get_conn().cursor()
        if mode:
            c.execute("SELECT * FROM accounts WHERE name = ? AND mode = ?", (name, mode))
        else:
            c.execute("SELECT * FROM accounts WHERE name = ?", (name,))
        row = c.fetchone()
        return dict(row) if row else None

    def get_account_by_mode(self, mode: str) -> Optional[Dict]:
        """获取指定模式的默认账户（第一个）"""
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM accounts WHERE mode = ? ORDER BY id LIMIT 1", (mode,))
        row = c.fetchone()
        return dict(row) if row else None

    def get_default_account(self) -> Optional[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM accounts ORDER BY id LIMIT 1")
        row = c.fetchone()
        return dict(row) if row else None

    def update_capital(self, account_id: int, capital: float):
        c = self._get_conn().cursor()
        c.execute(
            "UPDATE accounts SET current_capital = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (capital, account_id)
        )

    def add_position(self, account_id: int, code: str, name: str,
                     shares: int, price: float, score: float = None) -> int:
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, shares, cost_price FROM positions WHERE account_id = ? AND code = ? AND closed_at IS NULL",
                (account_id, code)
            )
            existing = c.fetchone()
            if existing:
                old_shares = existing['shares']
                old_cost = existing['cost_price']
                new_shares = old_shares + shares
                new_cost = (old_cost * old_shares + price * shares) / new_shares
                c.execute(
                    "UPDATE positions SET shares = ?, cost_price = ?, current_price = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                    (new_shares, new_cost, price, existing['id'])
                )
            else:
                c.execute(
                    "INSERT INTO positions (account_id, code, name, shares, cost_price, current_price, buy_date, buy_score) VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), ?)",
                    (account_id, code, name, shares, price, price, score)
                )
            c.execute(
                "INSERT INTO trade_lots (account_id, code, name, buy_date, buy_price, buy_shares, remaining_shares, buy_score) VALUES (?, ?, ?, datetime('now', 'localtime'), ?, ?, ?, ?)",
                (account_id, code, name, price, shares, shares, score)
            )
            return c.lastrowid

    def reduce_position(self, account_id: int, code: str, shares: int, sell_price: float) -> List[Dict]:
        if not isinstance(shares, int) or shares <= 0:
            raise ValueError("卖出数量必须为正整数: " + str(shares))
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, name, shares FROM positions WHERE account_id = ? AND code = ? AND closed_at IS NULL",
                (account_id, code)
            )
            row = c.fetchone()
            if not row:
                raise ValueError("未找到持仓: " + code)
            if shares > row['shares']:
                raise ValueError("卖出数量" + str(shares) + "超过持仓" + str(row['shares']))

            c.execute(
                "SELECT id, buy_price, remaining_shares, buy_date FROM trade_lots WHERE account_id = ? AND code = ? AND remaining_shares > 0 ORDER BY buy_date ASC, id ASC",
                (account_id, code)
            )
            lots = c.fetchall()
            pairs = []
            remaining = shares
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(remaining, lot['remaining_shares'])
                pairs.append({
                    'lot_id': lot['id'],
                    'buy_date': lot['buy_date'],
                    'buy_price': lot['buy_price'],
                    'shares': take,
                    'sell_price': sell_price,
                    'return_rate': (sell_price - lot['buy_price']) / lot['buy_price'] * 100,
                })
                new_remaining = lot['remaining_shares'] - take
                if new_remaining == 0:
                    c.execute(
                        "UPDATE trade_lots SET remaining_shares = 0, sell_date = datetime('now', 'localtime'), sell_price = ?, sell_shares = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                        (sell_price, take, lot['id'])
                    )
                else:
                    c.execute(
                        "UPDATE trade_lots SET remaining_shares = ?, sell_date = datetime('now', 'localtime'), sell_price = ?, sell_shares = sell_shares + ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                        (new_remaining, sell_price, take, lot['id'])
                    )
                remaining -= take

            new_shares = row['shares'] - shares
            if new_shares == 0:
                c.execute(
                    "UPDATE positions SET closed_at = datetime('now', 'localtime'), updated_at = datetime('now', 'localtime') WHERE id = ?",
                    (row['id'],)
                )
            else:
                c.execute(
                    "UPDATE positions SET shares = ?, current_price = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                    (new_shares, sell_price, row['id'])
                )
            return pairs

    def get_positions(self, account_id: int, include_closed: bool = False) -> List[Dict]:
        c = self._get_conn().cursor()
        if include_closed:
            c.execute("SELECT * FROM positions WHERE account_id = ? ORDER BY buy_date DESC", (account_id,))
        else:
            c.execute("SELECT * FROM positions WHERE account_id = ? AND closed_at IS NULL ORDER BY buy_date DESC", (account_id,))
        return [dict(r) for r in c.fetchall()]

    def get_position(self, account_id: int, code: str) -> Optional[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM positions WHERE account_id = ? AND code = ? AND closed_at IS NULL", (account_id, code))
        row = c.fetchone()
        return dict(row) if row else None

    def update_prices(self, account_id: int, prices: Dict[str, float]):
        with self.transaction() as conn:
            c = conn.cursor()
            for code, price in prices.items():
                c.execute(
                    "UPDATE positions SET current_price = ?, updated_at = datetime('now', 'localtime') WHERE account_id = ? AND code = ? AND closed_at IS NULL",
                    (price, account_id, code)
                )

    def add_trade(self, account_id: int, code: str, name: str,
                  trade_type: str, price: float, shares: int,
                  fee: float = 0, stamp_tax: float = 0,
                  score: float = None, reason: str = None) -> int:
        if trade_type not in ('BUY', 'SELL'):
            raise ValueError("交易类型必须为 BUY 或 SELL: " + str(trade_type))
        if price <= 0 or shares <= 0:
            raise ValueError("价格和数量必须为正数: price=" + str(price) + ", shares=" + str(shares))
        amount = price * shares
        with self.transaction() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO trades (account_id, code, name, type, price, shares, amount, fee, stamp_tax, score, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, code, name, trade_type, price, shares, amount, fee, stamp_tax, score, reason)
            )
            return c.lastrowid

    def get_trades(self, account_id: int, limit: int = 100) -> List[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM trades WHERE account_id = ? ORDER BY trade_date DESC LIMIT ?", (account_id, limit))
        return [dict(r) for r in c.fetchall()]

    def save_daily_nav(self, account_id: int, date: str, nav: float,
                       total_assets: float, position_value: float, cash: float):
        c = self._get_conn().cursor()
        c.execute(
            "INSERT OR REPLACE INTO daily_nav (account_id, date, nav, total_assets, position_value, cash) VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, date, nav, total_assets, position_value, cash)
        )

    def get_daily_nav(self, account_id: int, start_date: str = None, end_date: str = None) -> List[Dict]:
        c = self._get_conn().cursor()
        query = "SELECT * FROM daily_nav WHERE account_id = ?"
        params = [account_id]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date"
        c.execute(query, params)
        return [dict(r) for r in c.fetchall()]

    def add_dividend(self, account_id: int, code: str, name: str,
                     ex_date: str, dividend_per_share: float, shares: int) -> int:
        total_amount = dividend_per_share * shares
        c = self._get_conn().cursor()
        c.execute(
            "INSERT INTO dividends (account_id, code, name, ex_date, dividend_per_share, shares, total_amount) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account_id, code, name, ex_date, dividend_per_share, shares, total_amount)
        )
        return c.lastrowid

    def get_dividends(self, account_id: int) -> List[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM dividends WHERE account_id = ? ORDER BY ex_date DESC", (account_id,))
        return [dict(r) for r in c.fetchall()]

    def get_trade_stats(self, account_id: int) -> Dict:
        c = self._get_conn().cursor()
        c.execute("SELECT COUNT(*) as total FROM trades WHERE account_id = ?", (account_id,))
        total_trades = c.fetchone()['total']
        c.execute("SELECT type, COUNT(*) as count FROM trades WHERE account_id = ? GROUP BY type", (account_id,))
        type_counts = {row['type']: row['count'] for row in c.fetchall()}

        c.execute(
            "SELECT buy_price, sell_price, sell_shares FROM trade_lots WHERE account_id = ? AND remaining_shares = 0 AND sell_shares > 0 AND sell_price IS NOT NULL",
            (account_id,)
        )
        closed_lots = c.fetchall()
        returns = []
        for lot in closed_lots:
            if lot['buy_price'] and lot['buy_price'] > 0:
                ret = (lot['sell_price'] - lot['buy_price']) / lot['buy_price'] * 100
                returns.append(ret)
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        c.execute(
            "SELECT buy_price, sell_price, sell_shares, remaining_shares FROM trade_lots WHERE account_id = ? AND remaining_shares > 0 AND sell_shares > 0 AND sell_price IS NOT NULL",
            (account_id,)
        )
        partial_lots = c.fetchall()
        max_win = max(wins) if wins else 0
        max_loss = min(losses) if losses else 0
        return {
            'total_trades': total_trades,
            'buy_count': type_counts.get('BUY', 0),
            'sell_count': type_counts.get('SELL', 0),
            'win_count': len(wins),
            'loss_count': len(losses),
            'win_rate': len(wins) / len(returns) * 100 if returns else 0,
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'max_win': max_win,
            'max_loss': max_loss,
            'partial_count': len(partial_lots),
        }


_db_instance = None
_db_lock = threading.Lock()


def get_db() -> PortfolioDB:
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = PortfolioDB()
    return _db_instance
