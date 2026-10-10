"""Explicit maintainer actions; no OS execution and no broadcast endpoint."""
import argparse
import ctypes
import json
from pathlib import Path

from community.transport import Api


def private_session(path):
    import os,re,stat,time
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'r') as stream:
        info=os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or info.st_mode & 0o077 or info.st_nlink!=1):
            raise ValueError('private operator session required')
        data=json.loads(stream.read(1024))
    if (data.get('role')!='maintainer' or data.get('expires',0)<=time.time()
            or not isinstance(data.get('token'),str) or not re.fullmatch('[A-Za-z0-9_-]{43}',data['token'])):
        raise ValueError('current operator session required')
    return data['token']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--service-url',required=True)
    parser.add_argument('--session',type=Path,required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('list')
    show=commands.add_parser('show');show.add_argument('thread')
    reply=commands.add_parser('reply');reply.add_argument('thread');reply.add_argument('--body-file',type=Path,required=True)
    reply.add_argument('--client-id',required=True,help='same UUID for every retry of this exact reply')
    state=commands.add_parser('state');state.add_argument('thread');state.add_argument('state',choices=('triage','testing','closed','released'));state.add_argument('--release-id')
    release=commands.add_parser('verify-release');release.add_argument('--edition',required=True);release.add_argument('--version',required=True);release.add_argument('--digest',required=True)
    hide=commands.add_parser('hide');hide.add_argument('thread')
    ban=commands.add_parser('ban');ban.add_argument('thread')
    args=parser.parse_args()
    if ctypes.CDLL(None).prctl(4,0,0,0,0)!=0:raise RuntimeError('private process required')
    api=Api(args.service_url,timeout=120 if args.command=='verify-release' else 15);token=private_session(args.session)
    if args.command=='list':result=api.request('GET','/v1/threads',token=token)
    elif args.command=='show':result=api.request('GET','/v1/threads/'+args.thread,token=token)
    elif args.command=='reply':
        result=api.request('POST','/v1/threads/'+args.thread+'/messages',token=token,
                           body={'client_id':args.client_id,'body':args.body_file.read_text()})
    elif args.command=='state':
        body={'state':args.state}
        if args.release_id:body['release_id']=args.release_id
        result=api.request('PATCH','/v1/threads/'+args.thread+'/state',token=token,body=body)
    elif args.command=='verify-release':
        result=api.request('POST','/v1/releases',token=token,
            body={'edition':args.edition,'version':args.version,'digest':args.digest})
    elif args.command=='hide':result=api.request('POST','/v1/moderation/'+args.thread+'/hide',token=token)
    else:result=api.request('POST','/v1/moderation/'+args.thread+'/account',token=token,body={'active':False})
    # Support content is printed only in the operator's explicitly requested
    # terminal. Sessions/credentials never appear in results.
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
