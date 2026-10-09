"""Private operator tooling and loopback server; public TLS belongs to the proxy."""
import argparse
import json
import os
from pathlib import Path
import secrets
import time
import uuid
import hashlib
import ctypes

from argon2 import PasswordHasher

from community.service import Store, create_app
from community.releases import verify_promoted


def operator_session(directory, output):
    store=Store(directory)
    output=Path(output)
    root=output.parent.lstat()
    if output.parent.is_symlink() or root.st_uid!=os.getuid() or root.st_mode & 0o077:
        raise ValueError('owned private output directory required')
    token=secrets.token_urlsafe(32);expires=int(time.time())+3600
    with store.connect(write=True) as db:
        current=db.execute("SELECT id,role FROM users WHERE username='moos_operator'").fetchone()
        if current and current['role']!='maintainer':
            raise ValueError('reserved operator identity is occupied; refusing promotion')
        if current:
            identity=current['id']
        else:
            identity=str(uuid.uuid4())
            db.execute('INSERT INTO users(id,username,display_name,password,role) VALUES (?,?,?,?,?)',
                (identity,'moos_operator','فريق تطوير MoOS',PasswordHasher().hash(secrets.token_urlsafe(48)),'maintainer'))
        db.execute('DELETE FROM sessions WHERE expires<=?',(int(time.time()),))
        db.execute('INSERT INTO sessions VALUES (?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(),identity,expires))
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump({'schema':1,'token':token,'expires':expires,'role':'maintainer'},stream)
            stream.flush();os.fsync(stream.fileno())
    # Never print the token or generate a password the operator must remember.
    return {'created':True,'file':str(output),'expires':expires}


def main():
    parser=argparse.ArgumentParser(description='MoOS participation service')
    parser.add_argument('--data',type=Path,required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    setup=commands.add_parser('operator-session')
    setup.add_argument('--output',type=Path,required=True)
    serve=commands.add_parser('serve')
    serve.add_argument('--public-origin',required=True)
    serve.add_argument('--port',type=int,default=8939)
    serve.add_argument('--registration-open',action='store_true')
    serve.add_argument('--proxy-uid',type=int,default=0,
                       help='UID of the reviewed local TLS proxy; every request must match')
    args=parser.parse_args()
    if ctypes.CDLL(None).prctl(4,0,0,0,0) != 0:
        raise RuntimeError('private process dump protection unavailable')
    if args.command=='operator-session':
        print(json.dumps(operator_session(args.data,args.output)))
        return
    if not 1024<=args.port<=65535:
        parser.error('an unprivileged loopback port is required')
    if args.registration_open:
        with Store(args.data).connect() as db:
            if db.execute("SELECT COUNT(*) FROM users WHERE role='maintainer' AND active=1").fetchone()[0]==0:
                parser.error('create the private operator identity before opening registration')
    import uvicorn
    app=create_app(args.data,public_origin=args.public_origin,
                   release_verifier=verify_promoted,registration_open=args.registration_open,
                   proxy_uid=args.proxy_uid)
    uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False,
                proxy_headers=False,server_header=False,limit_concurrency=64,
                timeout_keep_alive=5)


if __name__=='__main__':main()
