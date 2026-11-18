"""按各自有效期间对齐试点证据，区分效率改善、收入增量与费用转移。

每个试点定义基线期间与试点期间；覆盖人群、实际采用、服务成本、
订单结果和财务归属按各自生效期间归入对应窗口后再比较。
缺少可比对照或成本账单未结清的试点只显示证据缺口，不下商业结论。
"""
from .evidence import at


def _money(value):
    return None if value is None else round(value, 2)


def _rate(value):
    return None if value is None else round(value, 4)


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def _by_period(rows, team):
    out = {}
    for row in rows:
        payload = row['payload']
        if payload.get('team') != team or 'period' not in payload:
            continue
        out.setdefault(payload['period'], []).append(row)
    return out


def _sum(rows, key):
    return sum(row['payload'][key] for row in rows)


def _price_index(changes, period):
    index = 1.0
    for change in changes:
        if change['payload']['effective'] <= period:
            index *= change['payload']['factor']
    return index


def _digests(*groups):
    return sorted({row['digest'] for group in groups for row in group})


def align(db, known_at, pilot):
    """把单个试点的全部证据对齐到基线/试点窗口，并给出证据缺口与商业闭环判断。"""
    payload = pilot['payload']
    team = payload['team']
    baseline = list(payload.get('baseline_periods', []))
    window = list(payload.get('pilot_periods', []))
    teams = {row['id']: row for row in at(db, 'team', known_at)}
    team_row = teams.get(team)
    team_info = team_row['payload'] if team_row else {}
    usage = _by_period(at(db, 'usage', known_at), team)
    coverage = _by_period(at(db, 'coverage', known_at), team)
    clouds = _by_period(at(db, 'cloud_cost', known_at), team)
    orders = _by_period(at(db, 'order', known_at), team)
    hours = _by_period(at(db, 'hour_report', known_at), team)
    invoices = _by_period(at(db, 'invoice', known_at), team)
    changes = [row for row in at(db, 'price_change', known_at)
               if row['payload'].get('team') == team or row['payload'].get('scope') == 'all']
    staff = [row for row in at(db, 'staff_change', known_at)
             if row['payload'].get('team') == team]
    transfers = [row for row in at(db, 'cost_transfer', known_at)
                 if team in (row['payload'].get('from_team'), row['payload'].get('to_team'))]
    reference = _price_index(changes, baseline[-1]) if baseline else 1.0
    last_baseline = baseline[-1] if baseline else ''
    hours_per_user = team_info.get('monthly_hours_per_user', 0)

    facts = []
    for period in baseline + window:
        usage_rows = usage.get(period, [])
        cover_rows = coverage.get(period, [])
        cloud_rows = clouds.get(period, [])
        order_rows = orders.get(period, [])
        hour_rows = hours.get(period, [])
        invoice_rows = invoices.get(period, [])
        staff_rows = [s for s in staff if last_baseline < s['payload']['effective'] <= period]
        transfer_rows = [t for t in transfers if t['payload'].get('period') == period]
        index = _price_index(changes, period)
        eligible = _sum(cover_rows, 'eligible_users') if cover_rows else None
        active = _sum(usage_rows, 'users')
        staff_delta = _sum(staff_rows, 'headcount_delta')
        booked = _sum(order_rows, 'amount') if order_rows else None
        facts.append({
            'period': period,
            'segment': 'baseline' if period in baseline else 'pilot',
            '_usage': usage_rows, '_cover': cover_rows, '_cloud': cloud_rows,
            '_orders': order_rows, '_hours': hour_rows, '_invoices': invoice_rows,
            '_staff': staff_rows, '_transfers': transfer_rows,
            '_changes': [c for c in changes if c['payload']['effective'] <= period],
            'eligible_users': eligible,
            'active_users': active,
            'sessions': _sum(usage_rows, 'sessions'),
            'adoption_rate': _rate(active / eligible) if eligible else None,
            'saved_hours': _sum(hour_rows, 'saved_hours'),
            'staff_explained_hours': max(0, -staff_delta) * hours_per_user,
            'orders': booked,
            'orders_at_baseline_price': booked / index * reference if booked is not None else None,
            'price_index': _rate(index),
            'reversals': [{'id': r['id'], 'reverses': r['payload'].get('reverses'),
                           'amount': r['payload']['amount']}
                          for r in order_rows if r['payload'].get('reverses')],
            'cloud_cost': _sum(cloud_rows, 'amount') if cloud_rows else None,
            'transfer_in': _sum([t for t in transfer_rows
                                 if t['payload'].get('to_team') == team], 'amount'),
            'transfer_out': _sum([t for t in transfer_rows
                                  if t['payload'].get('from_team') == team], 'amount'),
            'recognized': _sum(invoice_rows, 'recognized') if invoice_rows else None,
        })

    base_rows = [f for f in facts if f['segment'] == 'baseline']
    pilot_rows = [f for f in facts if f['segment'] == 'pilot']
    gaps, notes = [], []
    if not window:
        gaps.append('试点期间未定义')
    if not baseline or not any(f['orders'] is not None for f in base_rows):
        gaps.append('缺少可比对照')
    missing_cloud = [f['period'] for f in pilot_rows if f['cloud_cost'] is None]
    if missing_cloud:
        gaps.append('成本账单未结清: ' + ', '.join(missing_cloud))
    missing_cover = [f['period'] for f in pilot_rows if f['eligible_users'] is None]
    if missing_cover:
        gaps.append('覆盖人群缺失: ' + ', '.join(missing_cover))
    if window and not any(f['_usage'] for f in pilot_rows):
        gaps.append('采用数据缺失')
    if window and not any(f['orders'] is not None for f in pilot_rows):
        gaps.append('订单数据缺失')
    base_no_cloud = [f['period'] for f in base_rows if f['cloud_cost'] is None]
    if base_no_cloud:
        notes.append('基线期无云账单，服务成本按 0 计: ' + ', '.join(base_no_cloud))
    base_no_cover = [f['period'] for f in base_rows if f['eligible_users'] is None]
    if base_no_cover:
        notes.append('基线期覆盖人群缺失: ' + ', '.join(base_no_cover))
    win_no_orders = [f['period'] for f in pilot_rows if f['orders'] is None]
    if win_no_orders and not any('订单数据缺失' in g for g in gaps):
        notes.append('试点期订单未覆盖期间: ' + ', '.join(win_no_orders))

    # 效率改善：部门自报节省工时，剔除人员调整解释的部分，再按工时单价估值
    rate = team_info.get('loaded_hourly_cost')
    reported = sum(f['saved_hours'] for f in pilot_rows)
    explained = sum(f['staff_explained_hours'] for f in pilot_rows)
    net_hours = sum(max(0.0, f['saved_hours'] - f['staff_explained_hours']) for f in pilot_rows)
    if reported > 0 and rate is None:
        gaps.append('缺少工时单价')
    if reported == 0:
        notes.append('试点期无工时报告，效率改善按 0 计')
    value = net_hours / len(window) * rate if window and rate is not None else None

    # 收入增量：订单结果按基线价格重述后再比较，调价影响单列
    base_avg = _mean(f['orders_at_baseline_price'] for f in base_rows
                     if f['orders_at_baseline_price'] is not None)
    win_avg = _mean(f['orders_at_baseline_price'] for f in pilot_rows
                    if f['orders_at_baseline_price'] is not None)
    win_actual = _mean(f['orders'] for f in pilot_rows if f['orders'] is not None)
    increment = win_avg - base_avg if win_avg is not None and base_avg is not None else None
    price_effect = win_actual - win_avg if win_avg is not None and win_actual is not None else None

    # 服务成本：账面变化剔除费用转移，转移本身单列
    base_cloud = _mean(f['cloud_cost'] if f['cloud_cost'] is not None else 0 for f in base_rows)
    win_cloud = _mean(f['cloud_cost'] for f in pilot_rows if f['cloud_cost'] is not None)
    settled = len([f for f in pilot_rows if f['cloud_cost'] is not None]) == len(pilot_rows)
    booked_delta = win_cloud - (base_cloud or 0) if win_cloud is not None and settled else None
    transfer_in = sum(f['transfer_in'] for f in pilot_rows) / len(window) if window else 0
    transfer_out = sum(f['transfer_out'] for f in pilot_rows) / len(window) if window else 0
    ai_cost = booked_delta + transfer_out - transfer_in if booked_delta is not None else None

    eligible_total = sum(f['eligible_users'] for f in pilot_rows if f['eligible_users'])
    active_total = sum(f['active_users'] for f in pilot_rows)
    if gaps:
        closed, net = '证据不足', None
    else:
        net = (value or 0) + (increment or 0) - (ai_cost or 0)
        closed = '闭环成立' if net > 0 else '闭环不成立'

    periods = []
    for f in facts:
        row = {key: val for key, val in f.items() if not key.startswith('_')}
        row['orders'] = _money(row['orders'])
        row['orders_at_baseline_price'] = _money(row['orders_at_baseline_price'])
        row['cloud_cost'] = _money(row['cloud_cost'])
        row['transfer_in'] = _money(row['transfer_in'])
        row['transfer_out'] = _money(row['transfer_out'])
        row['recognized'] = _money(row['recognized'])
        row['sources'] = _digests(f['_usage'], f['_cover'], f['_cloud'], f['_orders'],
                                  f['_hours'], f['_invoices'], f['_staff'],
                                  f['_transfers'], f['_changes'])
        periods.append(row)
    sources = sorted({d for f in facts for d in _digests(f['_usage'], f['_cover'], f['_cloud'],
                                                         f['_orders'], f['_hours'], f['_invoices'],
                                                         f['_staff'], f['_transfers'], f['_changes'])}
                     | ({team_row['digest']} if team_row else set()) | {pilot['digest']})
    return {
        'pilot': pilot['id'],
        'assistant': payload.get('assistant'),
        'team': team,
        'team_name': team_info.get('name'),
        'cost_center': team_info.get('cost_center'),
        'windows': {'baseline': baseline, 'pilot': window},
        'adoption': {
            'eligible_users': eligible_total or None,
            'active_users': active_total,
            'adoption_rate': _rate(active_total / eligible_total) if eligible_total else None,
        },
        'efficiency': {
            'reported_saved_hours': reported,
            'staff_explained_hours': explained,
            'net_ai_hours': net_hours,
            'loaded_hourly_cost': rate,
            'value_per_period': _money(value),
        },
        'revenue': {
            'baseline_per_period': _money(base_avg),
            'pilot_actual_per_period': _money(win_actual),
            'pilot_constant_price_per_period': _money(win_avg),
            'increment_per_period': _money(increment),
            'price_effect_per_period': _money(price_effect),
        },
        'service_cost': {
            'baseline_per_period': _money(base_cloud),
            'pilot_per_period': _money(win_cloud),
            'booked_delta_per_period': _money(booked_delta),
            'ai_cost_per_period': _money(ai_cost),
        },
        'cost_transfer': {
            'transfer_in_per_period': _money(transfer_in),
            'transfer_out_per_period': _money(transfer_out),
            'net_out_per_period': _money(transfer_out - transfer_in),
            'details': [{'period': t['payload'].get('period'),
                         'from': t['payload'].get('from_team'),
                         'to': t['payload'].get('to_team'),
                         'amount': t['payload']['amount'],
                         'reason': t['payload'].get('reason')} for t in transfers],
        },
        'periods': periods,
        'gaps': gaps,
        'notes': notes,
        'closed_loop': closed,
        'net_benefit_per_period': _money(net),
        'sources': sources,
    }


def compare(db, known_at):
    """对已知时间可见的全部试点逐一对齐比较。"""
    return [align(db, known_at, pilot) for pilot in at(db, 'pilot', known_at)]
