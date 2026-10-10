"""Private per-account drafts and stable retry IDs, never sign-in credentials."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import uuid


class Outbox:
    def __init__(self, root, endpoint, username):
        self.root = Path(root)
        self.root.mkdir(parents=True,mode=0o700,exist_ok=True)
        info=self.root.lstat()
        if self.root.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('private draft directory required')
        scope=hashlib.sha256((endpoint+'\0'+username).encode()).hexdigest()
        self.path=self.root/(scope+'.sqlite3')
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_nlink!=1):
                raise ValueError('private regular draft database required')
        finally:os.close(fd)
        self.db=sqlite3.connect(self.path)
        self.db.row_factory=sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL,
            image BLOB,thread TEXT,state TEXT NOT NULL,receipt TEXT)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS composers (
            scope TEXT PRIMARY KEY, payload TEXT NOT NULL, image BLOB)''')
        self.db.commit()

    def add(self, kind, payload, image=None, thread=None):
        if kind not in ('thread','message','image'):
            raise ValueError('invalid outbox operation')
        if image is not None and len(image)>2*1024*1024:
            raise ValueError('image too large')
        # Only explicit support content, never credentials or service headers.
        if any(k in payload for k in ('password','token','authorization')):
            raise ValueError('credentials do not belong in drafts')
        identity=str(uuid.uuid4())
        body=dict(payload)|{'client_id':identity}
        with self.db:
            self.db.execute('INSERT INTO drafts VALUES (?,?,?,?,?,\'pending\',NULL)',
                (identity,kind,json.dumps(body,ensure_ascii=False),image,thread))
        return identity

    def get(self,identity):
        row=self.db.execute('SELECT * FROM drafts WHERE id=?',(identity,)).fetchone()
        if row is None:return None
        result=dict(row);result['payload']=json.loads(result['payload'])
        return result

    def pending(self):
        return [self.get(r[0]) for r in self.db.execute(
            "SELECT id FROM drafts WHERE state='pending' ORDER BY rowid")]

    def received(self,identity,receipt):
        if receipt.get('received') is not True or not isinstance(receipt.get('id'),(str,int)):
            raise ValueError('a real service receipt required')
        with self.db:
            self.db.execute("UPDATE drafts SET state='received',receipt=?,image=NULL WHERE id=?",
                            (json.dumps(receipt),identity))

    def accept_thread(self,identity,receipt):
        if receipt.get('received') is not True or not isinstance(receipt.get('id'),str):
            raise ValueError('a real thread receipt required')
        row=self.get(identity)
        if row is None:raise ValueError('draft missing')
        if row['state'] != 'pending':return None
        image_id=str(uuid.uuid4()) if row['image'] else None
        # A close/crash between accepting the report and uploading its image
        # cannot lose the selected image or duplicate the report on retry.
        with self.db:
            if image_id:
                self.db.execute('INSERT INTO drafts VALUES (?,?,?,?,?,\'pending\',NULL)',
                    (image_id,'image',json.dumps({'client_id':image_id}),row['image'],receipt['id']))
            self.db.execute("UPDATE drafts SET state='received',receipt=?,image=NULL WHERE id=?",
                            (json.dumps(receipt),identity))
        return image_id

    def accept_message(self,identity,receipt):
        row=self.get(identity)
        if row is None or row['kind']!='message':raise ValueError('message draft required')
        if receipt.get('received') is not True or type(receipt.get('id')) is not int:
            raise ValueError('a real message receipt required')
        if row['state']!='pending':return None
        image_id=str(uuid.uuid4()) if row['image'] else None
        with self.db:
            if image_id:
                self.db.execute('INSERT INTO drafts VALUES (?,?,?,?,?,\'pending\',NULL)',
                    (image_id,'image',json.dumps({'client_id':image_id}),row['image'],row['thread']))
            self.db.execute("UPDATE drafts SET state='received',receipt=?,image=NULL WHERE id=?",
                            (json.dumps(receipt),identity))
        return image_id

    def save_composer(self,scope,payload,image=None):
        if len(json.dumps(payload).encode())>40000 or (image and len(image)>2*1024*1024):
            raise ValueError('composer too large')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO composers VALUES (?,?,?)',
                            (scope,json.dumps(payload,ensure_ascii=False),image))

    def composer(self,scope):
        row=self.db.execute('SELECT payload,image FROM composers WHERE scope=?',(scope,)).fetchone()
        return (json.loads(row[0]),row[1]) if row else ({},None)

    def clear_composer(self,scope):
        with self.db:self.db.execute('DELETE FROM composers WHERE scope=?',(scope,))

    def discard(self,identity):
        # The user's explicit discard affects this account's local draft only.
        with self.db:self.db.execute('DELETE FROM drafts WHERE id=?',(identity,))

    def close(self):self.db.close()
