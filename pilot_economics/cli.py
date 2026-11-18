"""读取业务样例并展示当前结果。"""
import argparse
import json
from pathlib import Path
from .evidence import connect, receive
from .rollout import review
from .compare import compare
from .recommend import recommend, diff
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('--compare',action='store_true',help='输出试点对齐比较')
    parser.add_argument('--recommend',action='store_true',help='输出已知时间的推广建议')
    parser.add_argument('--diff',nargs='*',metavar='KNOWN_AT',help='对比两个已知时间，列出判断被改写的试点')
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding='utf-8'))
    db=connect()
    for item in data['documents']:receive(db,item)
    if args.diff is not None:
        if len(args.diff)==2:points=args.diff
        elif not args.diff and data.get('previous_known_at'):points=[data['previous_known_at'],data['known_at']]
        else:parser.error('--diff 需要两个已知时间，或数据提供 previous_known_at')
        out=diff(db,points[0],points[1])
    elif args.compare:out=compare(db,data['known_at'])
    elif args.recommend:out=recommend(db,data['known_at'])
    else:out=review(db,data['known_at'])
    print(json.dumps(out,ensure_ascii=False,indent=2))
    db.close()
if __name__=='__main__':main()
