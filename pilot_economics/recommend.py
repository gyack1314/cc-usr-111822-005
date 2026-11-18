"""推广建议：按已知时间可复现，并说明哪些试点的商业闭环判断被改写。

建议只依赖 known_at 之前收到的资料，之后补到的云账单或订单冲销
不会改变历史建议；diff 用来对比两个已知时间，列出判断被改写的试点。
"""
import hashlib
import json
from .compare import compare


def _digest(obj):
    body = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(body.encode()).hexdigest()


def recommend(db, known_at):
    """输出各试点在已知时间的推广建议，附可核对的来源与摘要。"""
    items = []
    for row in compare(db, known_at):
        if row['closed_loop'] == '证据不足':
            action = '补充证据后再定'
        elif row['closed_loop'] == '闭环成立':
            action = '建议推广'
        else:
            action = '建议暂缓推广'
        item = {
            'pilot': row['pilot'],
            'team': row['team'],
            'closed_loop': row['closed_loop'],
            'net_benefit_per_period': row['net_benefit_per_period'],
            'gaps': row['gaps'],
            'recommendation': action,
            'sources': row['sources'],
        }
        item['digest'] = _digest(item)
        items.append(item)
    return {'known_at': known_at, 'items': items, 'digest': _digest(items)}


def _reversals(row):
    return {rev['id']: rev for period in row['periods'] for rev in period['reversals']}


def _changes(before, after):
    """对比同一试点在两个已知时间的对齐事实，说明判断变化的原因。"""
    changes = []
    before_periods = {p['period']: p for p in before['periods']}
    after_periods = {p['period']: p for p in after['periods']}
    arrived = sorted(p for p, row in after_periods.items()
                     if row['cloud_cost'] is not None
                     and before_periods.get(p, {}).get('cloud_cost') is None)
    if arrived:
        changes.append('云账单到账: ' + ', '.join(arrived))
    adopted = sorted(p for p, row in after_periods.items()
                     if row['active_users'] and not before_periods.get(p, {}).get('active_users'))
    if adopted:
        changes.append('采用数据更新: ' + ', '.join(adopted))
    covered = sorted(p for p, row in after_periods.items()
                     if row['eligible_users'] is not None
                     and before_periods.get(p, {}).get('eligible_users') is None)
    if covered:
        changes.append('覆盖人群更新: ' + ', '.join(covered))
    old_reversals = _reversals(before)
    for rid, rev in sorted(_reversals(after).items()):
        if rid not in old_reversals:
            changes.append('订单冲销: {} (冲销 {}, {})'.format(rid, rev['reverses'], rev['amount']))
    moved = sorted(p for p, row in after_periods.items()
                   if p in before_periods
                   and row['orders'] is not None
                   and before_periods[p]['orders'] is not None
                   and row['orders'] != before_periods[p]['orders'])
    for period in moved:
        changes.append('订单结果变化: {} {} -> {}'.format(
            period, before_periods[period]['orders'], after_periods[period]['orders']))
    if before['closed_loop'] != after['closed_loop']:
        changes.append('商业闭环判断: {} -> {}'.format(before['closed_loop'], after['closed_loop']))
    return changes


def diff(db, earlier, later):
    """对比两个已知时间的推广建议，列出商业闭环判断被改写的试点。"""
    before_rows = {row['pilot']: row for row in compare(db, earlier)}
    after_rows = {row['pilot']: row for row in compare(db, later)}
    before_rec = {item['pilot']: item for item in recommend(db, earlier)['items']}
    after_rec = {item['pilot']: item for item in recommend(db, later)['items']}
    items = []
    for pid in sorted(set(before_rows) | set(after_rows)):
        before, after = before_rows.get(pid), after_rows.get(pid)
        if before is None or after is None:
            items.append({'pilot': pid, 'rewritten': False,
                          'changes': ['新试点纳入' if before is None else '试点已撤销'],
                          'before': before_rec.get(pid), 'after': after_rec.get(pid)})
            continue
        changes = _changes(before, after)
        b_rec, a_rec = before_rec[pid], after_rec[pid]
        if b_rec['recommendation'] != a_rec['recommendation']:
            changes.append('推广建议: {} -> {}'.format(b_rec['recommendation'],
                                                     a_rec['recommendation']))
        items.append({'pilot': pid,
                      'rewritten': before['closed_loop'] != after['closed_loop'],
                      'changes': changes,
                      'before': b_rec, 'after': a_rec})
    return {'from': earlier, 'to': later,
            'rewritten': [item['pilot'] for item in items if item['rewritten']],
            'items': items}
