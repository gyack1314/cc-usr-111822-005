from .evidence import at
def groups(db, known_at):
    teams={r['id']:r for r in at(db,'team',known_at)};out=[]
    for row in at(db,'usage',known_at):
        p=row['payload'];team=teams.get(p['team'])
        if not team:out.append({'usage':row['id'],'status':'部门待核'});continue
        out.append({'team':p['team'],'period':p['period'],'users':p['users'],'sessions':p['sessions'],'usage_source':row['digest'],'team_source':team['digest']})
    return out
