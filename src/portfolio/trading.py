"""
交易管理模块

提供买入、卖出、持仓查询等业务逻辑。
"""

from datetime import datetime
from typing import Dict, List, Optional

from .database import (
    PortfolioDB,
    get_db,
    MIN_SHARES,
    SHARES_LOT,
    COMMISSION_RATE,
    STAMP_TAX_RATE,
    MIN_COMMISSION,
    TRANSFER_FEE_RATE,
)


def calc_buy_fee(amount: float) -> float:
    """计算买入费用：佣金（最低 5 元）+ 过户费（仅沪市，简化忽略）"""
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    return round(commission, 2)


def calc_sell_fee(amount: float) -> tuple:
    """
    计算卖出费用：佣金（最低 5 元）+ 印花税（卖出单边千一）

    Returns:
        (total_fee, commission, stamp_tax)
    """
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    stamp_tax = amount * STAMP_TAX_RATE
    total = commission + stamp_tax
    return round(total, 2), round(commission, 2), round(stamp_tax, 2)


class TradingManager:
    """交易管理器（支持指定 account_id, mode, strategy_id）"""

    def __init__(self, db: PortfolioDB = None, account_id: int = None, mode: str = 'SIM'):
        self.db = db or get_db()
        self.mode = mode
        if account_id is None:
            self._account_id = None
        else:
            self._account_id = account_id
        self._ensure_account()

    def _ensure_account(self):
        """确保存在默认账户（按 mode 区分）"""
        if self._account_id is None:
            account = self.db.get_account_by_mode(self.mode)
            if not account:
                # 确保有默认策略
                default_strategy = self.db.get_default_strategy()
                if not default_strategy:
                    default_strategy_id = self.db.create_strategy(
                        name="默认策略", buy_threshold=30.0, take_profit=0.20,
                        stop_loss=0.08, cooldown_days=1, max_position_pct=0.20,
                        max_positions=5, is_default=1,
                        description="前7日均分≥30 买入，止盈20%，止损8%"
                    )
                else:
                    default_strategy_id = default_strategy['id']

                acc_id = self.db.create_account(
                    f"{'模拟仓' if self.mode == 'SIM' else '实盘'}",
                    mode=self.mode,
                    initial_capital=1000000,
                    strategy_id=default_strategy_id
                )
                self._account_id = acc_id
            else:
                self._account_id = account['id']

    def _get_account_id(self) -> int:
        if self._account_id is None:
            self._ensure_account()
        return self._account_id

    def get_account(self) -> Dict:
        return self.db.get_account(self._get_account_id())

    def get_strategy(self) -> Dict:
        """获取当前账户的策略"""
        account = self.get_account()
        if not account or not account.get('strategy_id'):
            return self.db.get_default_strategy()
        return self.db.get_strategy(account['strategy_id'])

    def _validate_shares(self, shares) -> int:
        """校验 A 股最小买入 100 股 + 整手"""
        if not isinstance(shares, int):
            try:
                shares = int(shares)
            except (TypeError, ValueError):
                raise ValueError(f"数量必须为整数，收到: {shares}")
        if shares <= 0:
            raise ValueError(f"数量必须为正数，收到: {shares}")
        if shares < MIN_SHARES:
            raise ValueError(f"A 股最小买入 {MIN_SHARES} 股，收到: {shares}")
        if shares % SHARES_LOT != 0:
            raise ValueError(f"A 股必须为 {SHARES_LOT} 整数倍，收到: {shares}")
        return shares

    def _validate_price(self, price) -> float:
        """校验价格"""
        try:
            price = float(price)
        except (TypeError, ValueError):
            raise ValueError(f"价格必须为数字，收到: {price}")
        if price <= 0:
            raise ValueError(f"价格必须为正数，收到: {price}")
        return price

    def buy(self, code: str, name: str, price, shares,
            score: float = None, reason: str = None,
            account_id: int = None) -> Dict:
        """
        买入股票

        Args:
            code: 股票代码
            name: 股票名称
            price: 买入价格
            shares: 买入数量（必须 100 整数倍）
            score: 当前评分
            reason: 买入原因
            account_id: 账户 ID（可选，默认使用默认账户）

        Returns:
            交易结果
        """
        shares = self._validate_shares(shares)
        price = self._validate_price(price)
        acc_id = account_id if account_id is not None else self._get_account_id()

        account = self.db.get_account(acc_id)
        if not account:
            return {
                'success': False,
                'error': f'账户 {acc_id} 不存在',
            }

        # 计算费用（A 股买入：佣金，最低 5 元）
        amount = price * shares
        fee = calc_buy_fee(amount)
        total_cost = amount + fee

        # 检查资金
        if total_cost > account['current_capital']:
            return {
                'success': False,
                'error': '资金不足',
                'required': round(total_cost, 2),
                'available': round(account['current_capital'], 2)
            }

        # 在单个事务内完成：扣资金、加仓、记交易
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            # 1. 扣减资金
            new_capital = account['current_capital'] - total_cost
            cursor.execute(
                'UPDATE accounts SET current_capital = ?, updated_at = datetime("now", "localtime") WHERE id = ?',
                (new_capital, acc_id)
            )
            # 2. 添加持仓
            cursor.execute(
                'SELECT id, shares, cost_price FROM positions WHERE account_id = ? AND code = ? AND closed_at IS NULL',
                (acc_id, code)
            )
            existing = cursor.fetchone()
            if existing:
                old_shares = existing['shares']
                old_cost = existing['cost_price']
                new_shares = old_shares + shares
                new_cost = (old_cost * old_shares + price * shares) / new_shares
                cursor.execute(
                    '''UPDATE positions
                       SET shares = ?, cost_price = ?, current_price = ?,
                           updated_at = datetime("now", "localtime")
                       WHERE id = ?''',
                    (new_shares, new_cost, price, existing['id'])
                )
            else:
                cursor.execute(
                    '''INSERT INTO positions
                       (account_id, code, name, shares, cost_price, current_price, buy_date, buy_score)
                       VALUES (?, ?, ?, ?, ?, ?, datetime("now", "localtime"), ?)''',
                    (acc_id, code, name, shares, price, price, score)
                )
            # 3. 记录 trade_lots（独立仓位行，便于 FIFO 配对）
            cursor.execute(
                '''INSERT INTO trade_lots
                   (account_id, code, name, buy_date, buy_price, buy_shares,
                    remaining_shares, buy_score)
                   VALUES (?, ?, ?, datetime("now", "localtime"), ?, ?, ?, ?)''',
                (acc_id, code, name, price, shares, shares, score)
            )
            # 4. 记录 trades
            cursor.execute(
                '''INSERT INTO trades
                   (account_id, code, name, type, price, shares, amount, fee, score, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (acc_id, code, name, 'BUY', price, shares, amount, fee, score, reason)
            )
            trade_id = cursor.lastrowid

        return {
            'success': True,
            'trade_id': trade_id,
            'code': code,
            'name': name,
            'price': price,
            'shares': shares,
            'amount': round(amount, 2),
            'fee': fee,
            'total_cost': round(total_cost, 2),
            'remaining_capital': round(new_capital, 2)
        }

    def sell(self, code: str, price, shares,
             reason: str = None, account_id: int = None) -> Dict:
        """
        卖出股票（FIFO 配对，A 股卖出：佣金 + 印花税）

        Args:
            code: 股票代码
            price: 卖出价格
            shares: 卖出数量（必须 100 整数倍）
            reason: 卖出原因
            account_id: 账户 ID

        Returns:
            交易结果
        """
        shares = self._validate_shares(shares)
        price = self._validate_price(price)
        acc_id = account_id if account_id is not None else self._get_account_id()

        account = self.db.get_account(acc_id)
        if not account:
            return {
                'success': False,
                'error': f'账户 {acc_id} 不存在',
            }

        # 事务内：FIFO 配对 + 减仓 + 加资金 + 记交易
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # 查询持仓
                cursor.execute(
                    '''SELECT id, name, shares, cost_price FROM positions
                       WHERE account_id = ? AND code = ? AND closed_at IS NULL''',
                    (acc_id, code)
                )
                row = cursor.fetchone()
                if not row:
                    return {
                        'success': False,
                        'error': '未持有该股票',
                        'code': code
                    }
                if shares > row['shares']:
                    return {
                        'success': False,
                        'error': f'卖出数量{shares}超过持仓{row["shares"]}',
                        'available': row['shares']
                    }

                # FIFO 配对 trade_lots
                cursor.execute(
                    '''SELECT id, buy_price, remaining_shares
                       FROM trade_lots
                       WHERE account_id = ? AND code = ? AND remaining_shares > 0
                       ORDER BY buy_date ASC, id ASC''',
                    (acc_id, code)
                )
                lots = cursor.fetchall()

                pairs = []
                remaining_to_sell = shares
                for lot in lots:
                    if remaining_to_sell <= 0:
                        break
                    take = min(remaining_to_sell, lot['remaining_shares'])
                    return_rate = (price - lot['buy_price']) / lot['buy_price'] * 100
                    pairs.append({
                        'lot_id': lot['id'],
                        'buy_price': lot['buy_price'],
                        'shares': take,
                        'sell_price': price,
                        'return_rate': return_rate,
                    })
                    new_remaining = lot['remaining_shares'] - take
                    if new_remaining == 0:
                        cursor.execute(
                            '''UPDATE trade_lots
                               SET remaining_shares = 0,
                                   sell_date = datetime("now", "localtime"),
                                   sell_price = ?,
                                   sell_shares = ?,
                                   updated_at = datetime("now", "localtime")
                               WHERE id = ?''',
                            (price, take, lot['id'])
                        )
                    else:
                        cursor.execute(
                            '''UPDATE trade_lots
                               SET remaining_shares = ?,
                                   sell_date = datetime("now", "localtime"),
                                   sell_price = ?,
                                   sell_shares = sell_shares + ?,
                                   updated_at = datetime("now", "localtime")
                               WHERE id = ?''',
                            (new_remaining, price, take, lot['id'])
                        )
                    remaining_to_sell -= take

                # 卖出费用（A 股：佣金 + 印花税）
                amount = price * shares
                total_fee, commission, stamp_tax = calc_sell_fee(amount)
                net_amount = amount - total_fee

                # 加资金
                new_capital = account['current_capital'] + net_amount
                cursor.execute(
                    'UPDATE accounts SET current_capital = ?, updated_at = datetime("now", "localtime") WHERE id = ?',
                    (new_capital, acc_id)
                )

                # 减仓
                new_shares = row['shares'] - shares
                if new_shares == 0:
                    cursor.execute(
                        '''UPDATE positions
                           SET closed_at = datetime("now", "localtime"),
                               updated_at = datetime("now", "localtime")
                           WHERE id = ?''',
                        (row['id'],)
                    )
                else:
                    cursor.execute(
                        '''UPDATE positions
                           SET shares = ?, current_price = ?,
                               updated_at = datetime("now", "localtime")
                           WHERE id = ?''',
                        (new_shares, price, row['id'])
                    )

                # 记录交易
                cursor.execute(
                    '''INSERT INTO trades
                       (account_id, code, name, type, price, shares, amount, fee, stamp_tax, reason)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (acc_id, code, row['name'], 'SELL', price, shares,
                     amount, commission, stamp_tax, reason)
                )
                trade_id = cursor.lastrowid

                # 计算总盈亏
                cost_amount = sum(p['buy_price'] * p['shares'] for p in pairs)
                profit = net_amount - cost_amount
                weighted_return = (profit / cost_amount * 100) if cost_amount > 0 else 0

        except ValueError as e:
            return {'success': False, 'error': str(e)}

        return {
            'success': True,
            'trade_id': trade_id,
            'code': code,
            'name': row['name'],
            'price': price,
            'shares': shares,
            'amount': round(amount, 2),
            'fee': commission,
            'stamp_tax': stamp_tax,
            'total_fee': total_fee,
            'net_amount': round(net_amount, 2),
            'profit': round(profit, 2),
            'profit_rate': round(weighted_return, 2),
            'pairs': pairs,
            'remaining_capital': round(new_capital, 2)
        }

    def get_positions(self, account_id: int = None) -> List[Dict]:
        """获取所有未平仓持仓"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        positions = self.db.get_positions(acc_id, include_closed=False)
        # 给每只持仓加上目标价（用于显示）
        strategy = self.get_strategy()
        if strategy:
            tp = strategy.get('take_profit', 0.20)
            sl = strategy.get('stop_loss', 0.08)
            for p in positions:
                p['target_take_profit'] = round(p['cost_price'] * (1 + tp), 2)
                p['target_stop_loss'] = round(p['cost_price'] * (1 - sl), 2)
        return positions

    def get_trades(self, limit: int = 100, account_id: int = None) -> List[Dict]:
        """获取交易记录"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        return self.db.get_trades(acc_id, limit)

    def get_stats(self, account_id: int = None) -> Dict:
        """获取交易统计"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        stats = self.db.get_trade_stats(acc_id)

        # 添加账户信息
        account = self.db.get_account(acc_id)
        positions = self.get_positions(acc_id)
        position_value = sum(
            (p['current_price'] or p['cost_price']) * p['shares']
            for p in positions
        )

        total_assets = account['current_capital'] + position_value
        total_return = (total_assets - account['initial_capital']) / account['initial_capital'] * 100

        def safe_round(v, decimals=2):
            try:
                if v is None:
                    return 0
                f = float(v)
                import math
                if math.isnan(f) or math.isinf(f):
                    return 0
                return round(f, decimals)
            except (TypeError, ValueError):
                return 0

        # 安全 round 所有数值字段
        safe_stats = {}
        for k, v in stats.items():
            if isinstance(v, (int, float)):
                safe_stats[k] = safe_round(v, 4) if k in ('avg_win', 'avg_loss', 'max_win', 'max_loss', 'win_rate', 'total_return') else safe_round(v)
            else:
                safe_stats[k] = v

        safe_stats.update({
            'initial_capital': account['initial_capital'],
            'current_capital': safe_round(account['current_capital']),
            'position_value': safe_round(position_value),
            'total_assets': safe_round(total_assets),
            'total_return': safe_round(total_return),
            'position_count': len(positions)
        })

        return safe_stats

    def update_prices(self, prices: Dict[str, float], account_id: int = None):
        """更新持仓价格"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        self.db.update_prices(acc_id, prices)

    def save_snapshot(self, date: str = None, account_id: int = None):
        """保存每日快照"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        if date is None:
            date = datetime.now().strftime('%Y%m%d')

        account = self.db.get_account(acc_id)
        positions = self.get_positions(acc_id)

        position_value = sum(
            (p['current_price'] or p['cost_price']) * p['shares']
            for p in positions
        )
        cash = account['current_capital']
        total_assets = cash + position_value
        nav = total_assets / account['initial_capital']

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT OR REPLACE INTO daily_nav
                   (account_id, date, nav, total_assets, position_value, cash)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (acc_id, date, nav, total_assets, position_value, cash)
            )

        return {
            'date': date,
            'nav': round(nav, 4),
            'total_assets': round(total_assets, 2),
            'position_value': round(position_value, 2),
            'cash': round(cash, 2)
        }

    def get_nav_history(self, start_date: str = None,
                        end_date: str = None, account_id: int = None) -> List[Dict]:
        """获取净值历史"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        return self.db.get_daily_nav(acc_id, start_date, end_date)

    def update_initial_capital(self, new_capital: float, account_id: int = None) -> Dict:
        """修改账户初始资金（重置模拟仓规模）"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        if new_capital <= 0:
            return {'success': False, 'error': '初始资金必须为正数'}
        with self.db.transaction() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE accounts SET initial_capital = ?, current_capital = ? WHERE id = ?",
                (new_capital, new_capital, acc_id)
            )
            # 同时删除所有持仓和交易（重置）
            c.execute("UPDATE positions SET closed_at = datetime('now', 'localtime') WHERE account_id = ? AND closed_at IS NULL", (acc_id,))
            c.execute("DELETE FROM trade_lots WHERE account_id = ?", (acc_id,))
            c.execute("DELETE FROM trades WHERE account_id = ?", (acc_id,))
            c.execute("DELETE FROM daily_nav WHERE account_id = ?", (acc_id,))
        return {'success': True, 'initial_capital': new_capital, 'message': '已重置账户'}

    def add_capital(self, delta: float, account_id: int = None, reason: str = None) -> Dict:
        """增减资金（不影响初始资金基准，只调整当前可用资金）"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        account = self.db.get_account(acc_id)
        new_capital = account['current_capital'] + delta
        if new_capital < 0:
            return {'success': False, 'error': '资金不足'}
        with self.db.transaction() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE accounts SET current_capital = ? WHERE id = ?",
                (new_capital, acc_id)
            )
        return {'success': True, 'current_capital': new_capital, 'delta': delta, 'reason': reason}

    def delete_trade(self, trade_id: int, account_id: int = None) -> Dict:
        """删除交易记录（同时反转交易对账户和持仓的影响）"""
        acc_id = account_id if account_id is not None else self._get_account_id()
        with self.db.transaction() as conn:
            c = conn.cursor()
            # 查找交易
            c.execute("SELECT * FROM trades WHERE id = ? AND account_id = ?", (trade_id, acc_id))
            trade = c.fetchone()
            if not trade:
                return {'success': False, 'error': '交易不存在'}

            trade = dict(trade)
            code = trade['code']

            if trade['type'] == 'BUY':
                # 反转：先看现在还有多少持仓可释放
                c.execute(
                    "SELECT id, shares FROM positions WHERE account_id = ? AND code = ? AND closed_at IS NULL",
                    (acc_id, code)
                )
                pos = c.fetchone()
                if pos:
                    new_shares = pos['shares'] - trade['shares']
                    refund = trade['amount'] + trade['fee']  # 退还买入扣的资金
                    if new_shares <= 0:
                        c.execute(
                            "UPDATE positions SET closed_at = datetime('now', 'localtime') WHERE id = ?",
                            (pos['id'],)
                        )
                    else:
                        c.execute(
                            "UPDATE positions SET shares = ? WHERE id = ?",
                            (new_shares, pos['id'])
                        )
                    c.execute(
                        "UPDATE accounts SET current_capital = current_capital + ? WHERE id = ?",
                        (refund, acc_id)
                    )
                # 同步 trade_lots
                c.execute(
                    "SELECT id, buy_shares, sell_shares FROM trade_lots WHERE account_id = ? AND code = ? AND buy_date = ? ORDER BY id DESC",
                    (acc_id, code, trade['trade_date'])
                )
                for lot in c.fetchall():
                    if trade['shares'] <= 0:
                        break
                    lot = dict(lot)
                    take = min(trade['shares'], lot['buy_shares'] - lot['sell_shares'])
                    c.execute("DELETE FROM trade_lots WHERE id = ?", (lot['id'],))
            else:  # SELL
                # 反转卖出：扣回资金，撤销持仓变化
                c.execute(
                    "UPDATE accounts SET current_capital = current_capital - ? WHERE id = ?",
                    (trade['amount'] - trade['fee'] - trade['stamp_tax'], acc_id)
                )
                # 撤销 trade_lots 卖出记录
                c.execute(
                    "SELECT id, buy_shares, remaining_shares, sell_shares, sell_price FROM trade_lots WHERE account_id = ? AND code = ? AND sell_date = ? ORDER BY id ASC",
                    (acc_id, code, trade['trade_date'])
                )
                remaining_to_restore = trade['shares']
                restored_shares = 0
                for lot in c.fetchall():
                    if remaining_to_restore <= 0:
                        break
                    lot = dict(lot)
                    take = min(remaining_to_restore, lot['sell_shares'])
                    new_remaining = lot['remaining_shares'] + take
                    new_sell_shares = lot['sell_shares'] - take
                    if new_sell_shares <= 0:
                        c.execute(
                            "UPDATE trade_lots SET remaining_shares = ?, sell_shares = 0, sell_date = NULL, sell_price = NULL, updated_at = datetime('now', 'localtime') WHERE id = ?",
                            (new_remaining, lot['id'])
                        )
                    else:
                        c.execute(
                            "UPDATE trade_lots SET remaining_shares = ?, sell_shares = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                            (new_remaining, new_sell_shares, lot['id'])
                        )
                    restored_shares += take
                    remaining_to_restore -= take

                if restored_shares > 0:
                    c.execute(
                        "UPDATE positions SET shares = shares + ?, closed_at = NULL, updated_at = datetime('now', 'localtime') WHERE account_id = ? AND code = ? AND closed_at IS NULL",
                        (restored_shares, acc_id, code)
                    )
                    if c.rowcount == 0:
                        c.execute(
                            "SELECT id, shares FROM positions WHERE account_id = ? AND code = ? AND closed_at IS NOT NULL ORDER BY closed_at DESC, id DESC LIMIT 1",
                            (acc_id, code)
                        )
                        pos = c.fetchone()
                        if pos:
                            c.execute(
                                "UPDATE positions SET shares = ?, closed_at = NULL, updated_at = datetime('now', 'localtime') WHERE id = ?",
                                (max(pos['shares'], restored_shares), pos['id'])
                            )

            # 删除交易记录
            c.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        return {'success': True, 'deleted_trade_id': trade_id}

    def record_dividend(self, code: str, name: str, ex_date: str,
                        dividend_per_share: float, account_id: int = None) -> Dict:
        """
        记录现金分红（除权日 + 持仓股数 = 派息金额）

        Returns:
            派息结果
        """
        acc_id = account_id if account_id is not None else self._get_account_id()

        position = self.db.get_position(acc_id, code)
        if not position:
            return {
                'success': False,
                'error': f'未持有 {code}，无法记录分红',
            }

        shares = position['shares']
        total_amount = dividend_per_share * shares

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            # 1. 写入分红记录
            cursor.execute(
                '''INSERT INTO dividends
                   (account_id, code, name, ex_date, dividend_per_share, shares, total_amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (acc_id, code, name, ex_date, dividend_per_share, shares, total_amount)
            )
            # 2. 加资金（A 股现金分红直接到账）
            cursor.execute(
                'UPDATE accounts SET current_capital = current_capital + ?, updated_at = datetime("now", "localtime") WHERE id = ?',
                (total_amount, acc_id)
            )

        return {
            'success': True,
            'code': code,
            'name': name,
            'ex_date': ex_date,
            'dividend_per_share': dividend_per_share,
            'shares': shares,
            'total_amount': round(total_amount, 2),
        }
