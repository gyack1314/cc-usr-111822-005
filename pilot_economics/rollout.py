from .evidence import at
from .accounts import recognized
def review(db, known_at):
    costs={(r['payload']['team'],r['payload']['period']):r for r in at(db,'cloud_cost',known_at)};out=[]
    for row in recognized(db,known_at):
        if 'team' not in row:out.append(row);continue
        cost=costs.get((row['team'],row['period']))
        if row['income'] is None or cost is None:out.append({'team':row['team'],'period':row['period'],'status':'账单未齐'});continue
        out.append({'team':row['team'],'period':row['period'],'observed_margin':row['income']-cost['payload']['amount'],'sources':[row['usage_source'],row['invoice_source'],cost['digest']]})
    return out
