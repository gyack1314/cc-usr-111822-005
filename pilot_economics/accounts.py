from .evidence import at
from .adoption import groups
def recognized(db, known_at):
    invoices={(r['payload']['team'],r['payload']['period']):r for r in at(db,'invoice',known_at)};out=[]
    for row in groups(db,known_at):
        if 'team' not in row:out.append(row);continue
        bill=invoices.get((row['team'],row['period']))
        out.append({**row,'income':bill['payload']['recognized'] if bill else None,'invoice_source':bill['digest'] if bill else None})
    return out
