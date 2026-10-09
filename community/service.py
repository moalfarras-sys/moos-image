"""Authenticated support API. No OS commands, automatic screenshots or raw log uploads.

A public suggestion shares its original proposal only. Its replies and images
remain private to the author and maintainers. SQLite transactions own retry
identity; a UI cannot grant access or announce an unverified release.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import threading
import time
from typing import Literal
import uuid
import warnings
from urllib.parse import urlsplit
import stat

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from community.proxy import forwarded_ip

MAX_UPLOAD = 2 * 1024 * 1024
MAX_BODY = MAX_UPLOAD + 64 * 1024
MAX_PIXELS = 4_000_000
MAX_ACCOUNT_IMAGES = 64 * 1024 * 1024
SESSION_SECONDS = 7 * 24 * 3600
EDITIONS = {'moos', 'moos-nvidia', 'moos-cloud', 'moos-arm'}


def fail(status, code):
    raise HTTPException(status, detail={'code': code})


class BoundedRequests:
    """Bound streamed bodies before any parser; never trust Content-Length alone."""
    def __init__(self, app, origin, proxy_uid=None):
        self.app, self.origin, self.proxy_uid = app, origin, proxy_uid

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        if self.proxy_uid is not None:
            ip = forwarded_ip(scope, scope.get('headers', []), self.proxy_uid)
            if ip is None:
                return await self.reject(send, 403, 'untrusted_proxy')
            scope = dict(scope, client=(ip, scope['client'][1]))
        headers = dict(scope.get('headers', []))
        origin = headers.get(b'origin')
        if origin and origin.decode('latin1') != self.origin:
            return await self.reject(send, 403, 'foreign_origin')
        body = bytearray()
        try:
            async with asyncio.timeout(30):
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    body.extend(message.get('body', b''))
                    if len(body) > MAX_BODY:
                        return await self.reject(send, 413, 'request_too_large')
                    if not message.get('more_body', False):
                        break
        except TimeoutError:
            return await self.reject(send, 408, 'request_timeout')
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        async def guarded_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [
                    (b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff'),
                    (b'content-security-policy', b"default-src 'none'; frame-ancestors 'none'"),
                    (b'referrer-policy', b'no-referrer')]
            await send(message)
        await self.app(scope, replay, guarded_send)

    @staticmethod
    async def reject(send, status, code):
        body = json.dumps({'detail': {'code': code}}).encode()
        await send({'type': 'http.response.start', 'status': status, 'headers': [
            (b'content-type', b'application/json'), (b'cache-control', b'no-store')]})
        await send({'type': 'http.response.body', 'body': body})


class RateLimit:
    def __init__(self):
        self.lock = threading.Lock()
        self.entries = OrderedDict()

    def take(self, key, maximum, period=60):
        now = time.monotonic()
        with self.lock:
            q = self.entries.setdefault(key, deque())
            self.entries.move_to_end(key)
            while q and q[0] <= now - period:
                q.popleft()
            if len(q) >= maximum:
                fail(429, 'rate_limited')
            q.append(now)
            while len(self.entries) > 4096:
                self.entries.popitem(last=False)


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        directory_stat = self.directory.lstat()
        if (self.directory.is_symlink() or directory_stat.st_uid != os.getuid()
                or directory_stat.st_mode & 0o077):
            raise ValueError('owned private data directory required')
        self.database = self.directory / 'participation.sqlite3'
        fd = os.open(self.database, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            metadata = os.fstat(fd)
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                    or metadata.st_mode & 0o077 or metadata.st_nlink != 1):
                raise ValueError('owned private regular database required')
        finally:
            os.close(fd)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL, password TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('member','maintainer')),
                    active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS sessions (
                    hash TEXT PRIMARY KEY, user TEXT NOT NULL REFERENCES users(id),
                    expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(id),
                    kind TEXT NOT NULL, public INTEGER NOT NULL DEFAULT 0,
                    title TEXT NOT NULL, proposal TEXT NOT NULL, state TEXT NOT NULL,
                    created INTEGER NOT NULL, updated INTEGER NOT NULL,
                    release TEXT, client_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    UNIQUE(owner, client_id));
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, thread TEXT NOT NULL REFERENCES threads(id),
                    author TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL,
                    created INTEGER NOT NULL, client_id TEXT NOT NULL,
                    UNIQUE(author, client_id));
                CREATE INDEX IF NOT EXISTS messages_thread ON messages(thread,id);
                CREATE TABLE IF NOT EXISTS images (
                    id TEXT PRIMARY KEY, thread TEXT NOT NULL REFERENCES threads(id),
                    owner TEXT NOT NULL REFERENCES users(id), data BLOB NOT NULL,
                    created INTEGER NOT NULL, client_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    UNIQUE(owner, client_id));
                CREATE TABLE IF NOT EXISTS releases (
                    id TEXT PRIMARY KEY, edition TEXT NOT NULL, version TEXT NOT NULL,
                    digest TEXT NOT NULL, verified INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(id),
                    thread TEXT NOT NULL REFERENCES threads(id), event TEXT NOT NULL,
                    created INTEGER NOT NULL, seen INTEGER NOT NULL DEFAULT 0);
            ''')
        self.database.chmod(0o600)

    @contextmanager
    def connect(self, write=False):
        # / is composefs on MoOS; measure the real data filesystem.
        if write and shutil.disk_usage(self.directory).free < 1024**3:
            fail(507, 'storage_unavailable')
        db = sqlite3.connect(self.database, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    @field_validator('display_name', 'title', 'body', mode='before', check_fields=False)
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class Credentials(Input):
    username: str = Field(min_length=3, max_length=32, pattern=r'^[a-z0-9_]+$')
    password: str = Field(min_length=12, max_length=128)


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=60)


class NewThread(Input):
    client_id: str
    kind: Literal['problem', 'suggestion']
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=5, max_length=8000)
    public: bool = False
    publish_consent: bool = False


class NewMessage(Input):
    client_id: str
    body: str = Field(min_length=1, max_length=8000)


class NewState(Input):
    state: Literal['received', 'triage', 'testing', 'released', 'closed']
    release_id: str | None = None


class ReleaseInput(Input):
    edition: str
    version: str
    digest: str


class AccountModeration(Input):
    active: bool


def client_key(key):
    try:
        if str(uuid.UUID(key)) != key:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        fail(422, 'invalid_retry_id')
    return key


def normalized_image(data):
    if not data or len(data) > MAX_UPLOAD:
        fail(413, 'image_too_large')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ('PNG', 'JPEG', 'WEBP') or getattr(image, 'n_frames', 1) != 1:
                    fail(422, 'invalid_image')
                if image.width * image.height > MAX_PIXELS:
                    fail(413, 'image_too_large')
                image.load()
                rgba = ImageOps.exif_transpose(image).convert('RGBA')
                # Flatten transparency deliberately: invisible RGB bytes must
                # not turn visible when an attachment loses its alpha channel.
                background = Image.new('RGBA',rgba.size,(255,255,255,255))
                clean = Image.alpha_composite(background,rgba).convert('RGB')
                clean.thumbnail((1920, 1920))
                # A fresh image drops EXIF, GPS, comments, ICC and PNG text chunks.
                clean = Image.frombytes('RGB', clean.size, clean.tobytes())
                output = io.BytesIO()
                clean.save(output, format='PNG')
                result = output.getvalue()
                if len(result) > MAX_UPLOAD:
                    fail(413, 'image_too_large')
                return result
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        fail(422, 'invalid_image')


def create_app(directory, *, public_origin, release_verifier=None, registration_open=False, proxy_uid=None):
    parsed = urlsplit(public_origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('one HTTPS public origin required')
    store, limiter = Store(directory), RateLimit()
    passwords = PasswordHasher()
    dummy_hash = passwords.hash(secrets.token_urlsafe(32))
    auth_slots = threading.BoundedSemaphore(4)
    image_slots = threading.BoundedSemaphore(2)
    app = FastAPI(title='MoOS Participation', docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BoundedRequests, origin=public_origin, proxy_uid=proxy_uid)
    app.state.store = store
    app.state.passwords = passwords

    def user(request: Request):
        header = request.headers.get('authorization', '')
        token = header.removeprefix('Bearer ')
        if not header.startswith('Bearer ') or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            fail(401, 'sign_in_required')
        with store.connect() as db:
            row = db.execute('''SELECT users.* FROM sessions JOIN users ON users.id=sessions.user
                WHERE sessions.hash=? AND sessions.expires>? AND users.active=1''',
                (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if row is None:
            fail(401, 'sign_in_required')
        return dict(row)

    def maintainer(current=Depends(user)):
        if current['role'] != 'maintainer':
            fail(403, 'maintainer_required')
        return current

    def thread(db, identity, current):
        row = db.execute('SELECT * FROM threads WHERE id=?', (identity,)).fetchone()
        if row is None or (row['owner'] != current['id'] and current['role'] != 'maintainer'):
            fail(404, 'thread_not_found')
        return row

    def notify(db, owner, identity, event):
        db.execute('INSERT INTO notifications(owner,thread,event,created) VALUES (?,?,?,?)',
                   (owner, identity, event, int(time.time())))

    @app.get('/v1/health')
    def health():
        return {'schema': 1, 'status': 'ready', 'registration_open': registration_open}

    @app.get('/v1/session')
    def identity(current=Depends(user)):
        return {'schema': 1, 'user': {k: current[k] for k in ('username','display_name','role')}}

    @app.post('/v1/accounts', status_code=201)
    def register(body: Registration, request: Request):
        if not registration_open:
            fail(403, 'registration_closed')
        limiter.take(('signup', request.client.host), 5, 3600)
        if not auth_slots.acquire(blocking=False):
            fail(429, 'rate_limited')
        try:
            hashed = passwords.hash(body.password)
            with store.connect(write=True) as db:
                if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] >= 10000:
                    fail(429, 'registration_closed')
                try:
                    db.execute('INSERT INTO users(id,username,display_name,password,role) VALUES (?,?,?,?,?)',
                        (str(uuid.uuid4()), body.username, body.display_name.strip(), hashed, 'member'))
                except sqlite3.IntegrityError:
                    fail(409, 'account_unavailable')
        finally:
            auth_slots.release()
        return {'schema': 1, 'created': True}

    @app.post('/v1/session')
    def login(body: Credentials, request: Request):
        limiter.take(('login-ip', request.client.host), 30)
        limiter.take(('login-user', body.username), 8)
        if not auth_slots.acquire(blocking=False):
            fail(429, 'rate_limited')
        try:
            with store.connect() as db:
                row = db.execute('SELECT * FROM users WHERE username=?', (body.username,)).fetchone()
            try:
                accepted = passwords.verify(row['password'] if row else dummy_hash, body.password)
            except (VerificationError, InvalidHashError):
                accepted = False
            if not accepted or row is None or not row['active']:
                fail(401, 'invalid_credentials')
            token = secrets.token_urlsafe(32)
            expires = int(time.time()) + SESSION_SECONDS
            with store.connect(write=True) as db:
                db.execute('DELETE FROM sessions WHERE expires<=?', (int(time.time()),))
                db.execute('INSERT INTO sessions VALUES (?,?,?)',
                    (hashlib.sha256(token.encode()).hexdigest(), row['id'], expires))
                db.execute('''DELETE FROM sessions WHERE user=? AND rowid NOT IN
                    (SELECT rowid FROM sessions WHERE user=? ORDER BY rowid DESC LIMIT 5)''',
                    (row['id'],row['id']))
            return {'schema': 1, 'token': token, 'expires': expires,
                    'user': {'username': row['username'], 'display_name': row['display_name'], 'role': row['role']}}
        finally:
            auth_slots.release()

    @app.delete('/v1/session', status_code=204)
    def logout(request: Request, current=Depends(user)):
        token = request.headers['authorization'][7:]
        with store.connect(write=True) as db:
            db.execute('DELETE FROM sessions WHERE hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
        return Response(status_code=204)

    @app.get('/v1/threads')
    def threads(current=Depends(user)):
        with store.connect() as db:
            rows = db.execute('''SELECT id,title,kind,state,public,created,updated,release FROM threads
                WHERE (?='maintainer' OR owner=?) ORDER BY updated DESC LIMIT 100''',
                (current['role'], current['id'])).fetchall()
        return {'schema': 1, 'threads': [dict(r) for r in rows]}

    @app.post('/v1/threads', status_code=201)
    def create_thread(body: NewThread, current=Depends(user)):
        client_key(body.client_id)
        if body.public and (body.kind != 'suggestion' or not body.publish_consent):
            fail(422, 'explicit_public_suggestion_required')
        fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with store.connect(write=True) as db:
            previous = db.execute('SELECT id,fingerprint FROM threads WHERE owner=? AND client_id=?',
                                   (current['id'], body.client_id)).fetchone()
            if previous:
                if previous['fingerprint'] != fingerprint:
                    fail(409, 'retry_content_changed')
                return {'schema': 1, 'id': previous['id'], 'received': True}
            limiter.take(('new-thread', current['id']), 10)
            identity, now = str(uuid.uuid4()), int(time.time())
            db.execute('''INSERT INTO threads
                (id,owner,kind,public,title,proposal,state,created,updated,client_id,fingerprint)
                VALUES (?,?,?,?,?,?,'received',?,?,?,?)''',
                (identity,current['id'],body.kind,int(body.public),body.title,body.body,
                 now,now,body.client_id,fingerprint))
            db.execute('INSERT INTO messages(thread,author,body,created,client_id) VALUES (?,?,?,?,?)',
                       (identity,current['id'],body.body,now,body.client_id))
        return {'schema': 1, 'id': identity, 'received': True}

    @app.get('/v1/threads/{identity}')
    def conversation(identity: str, after: int = 0, current=Depends(user)):
        if after < 0:
            fail(422, 'invalid_cursor')
        with store.connect() as db:
            row = thread(db,identity,current)
            messages = db.execute('''SELECT messages.id,body,created,display_name,role FROM messages
                JOIN users ON users.id=messages.author WHERE thread=? AND messages.id>?
                ORDER BY messages.id LIMIT 101''',(identity,after)).fetchall()
            images = db.execute('SELECT id,created FROM images WHERE thread=? ORDER BY created',
                                (identity,)).fetchall()
            release = db.execute('SELECT edition,version,digest FROM releases WHERE id=? AND verified=1',
                                 (row['release'],)).fetchone() if row['release'] else None
        return {'schema': 1, 'thread': {k:row[k] for k in ('id','title','kind','state','public','release')},
                'messages':[dict(r) for r in messages[:100]], 'has_more': len(messages)>100,
                'images':[dict(r) for r in images], 'release':dict(release) if release else None}

    @app.post('/v1/threads/{identity}/messages', status_code=201)
    def send(identity: str, body: NewMessage, current=Depends(user)):
        client_key(body.client_id)
        with store.connect(write=True) as db:
            row = thread(db,identity,current)
            previous = db.execute('SELECT id,thread,body FROM messages WHERE author=? AND client_id=?',
                                   (current['id'],body.client_id)).fetchone()
            if previous:
                if previous['thread'] != identity or previous['body'] != body.body:
                    fail(409, 'retry_content_changed')
                return {'schema':1,'id':previous['id'],'received':True}
            limiter.take(('message',current['id']),30)
            now = int(time.time())
            result = db.execute('INSERT INTO messages(thread,author,body,created,client_id) VALUES (?,?,?,?,?)',
                (identity,current['id'],body.body,now,body.client_id))
            db.execute('UPDATE threads SET updated=? WHERE id=?',(now,identity))
            if current['id'] != row['owner']:
                notify(db,row['owner'],identity,'reply')
        return {'schema':1,'id':result.lastrowid,'received':True}

    @app.post('/v1/threads/{identity}/images', status_code=201)
    async def upload(identity: str, request: Request, current=Depends(user)):
        # Permission precedes decoding: another user's image route is never an
        # image oracle. No multipart temporary files or client filenames.
        with store.connect() as db:
            row = thread(db,identity,current)
        key = client_key(request.headers.get('idempotency-key',''))
        data = await request.body()
        fingerprint = hashlib.sha256(data).hexdigest()
        with store.connect() as db:
            previous = db.execute('SELECT id,thread,fingerprint FROM images WHERE owner=? AND client_id=?',
                                   (current['id'],key)).fetchone()
        if previous:
            if previous['thread'] != identity or previous['fingerprint'] != fingerprint:
                fail(409,'retry_content_changed')
            return {'schema':1,'id':previous['id'],'received':True}
        limiter.take(('image',current['id']),10)
        if not image_slots.acquire(blocking=False):
            fail(429, 'rate_limited')
        try:
            clean = await run_in_threadpool(normalized_image, data)
        finally:
            image_slots.release()
        with store.connect(write=True) as db:
            thread(db,identity,current)
            total = db.execute('SELECT COALESCE(SUM(length(data)),0) FROM images WHERE owner=?',
                               (current['id'],)).fetchone()[0]
            if total + len(clean) > MAX_ACCOUNT_IMAGES:
                fail(413,'image_quota')
            # An identical concurrent retry must resolve the same receipt too.
            previous = db.execute('SELECT id,thread,fingerprint FROM images WHERE owner=? AND client_id=?',
                                   (current['id'],key)).fetchone()
            if previous:
                if previous['thread'] != identity or previous['fingerprint'] != fingerprint:
                    fail(409,'retry_content_changed')
                return {'schema':1,'id':previous['id'],'received':True}
            image_id = str(uuid.uuid4())
            db.execute('INSERT INTO images VALUES (?,?,?,?,?,?,?)',
                (image_id,identity,current['id'],clean,int(time.time()),key,fingerprint))
            db.execute('UPDATE threads SET updated=? WHERE id=?',(int(time.time()),identity))
            if current['id'] != row['owner']:
                notify(db,row['owner'],identity,'reply')
        return {'schema':1,'id':image_id,'received':True}

    @app.get('/v1/images/{image_id}')
    def image(image_id: str, current=Depends(user)):
        with store.connect() as db:
            row = db.execute('SELECT thread,data FROM images WHERE id=?',(image_id,)).fetchone()
            if row is None:
                fail(404,'image_not_found')
            thread(db,row['thread'],current)
        return Response(row['data'],media_type='image/png',headers={'Content-Disposition':'inline; filename="attachment.png"'})

    @app.get('/v1/suggestions')
    def suggestions():
        with store.connect() as db:
            rows = db.execute('''SELECT threads.id,title,proposal,state,release,users.display_name
                FROM threads JOIN users ON users.id=threads.owner WHERE public=1 AND kind='suggestion'
                ORDER BY updated DESC LIMIT 100''').fetchall()
        return {'schema':1,'suggestions':[dict(r) for r in rows]}

    @app.patch('/v1/threads/{identity}/state')
    def state(identity: str, body: NewState, current=Depends(maintainer)):
        with store.connect(write=True) as db:
            row = thread(db,identity,current)
            if body.state == 'released':
                verified = db.execute('SELECT id FROM releases WHERE id=? AND verified=1',
                                      (body.release_id,)).fetchone()
                if verified is None:
                    fail(422,'verified_release_required')
            elif body.release_id is not None:
                fail(422,'release_state_required')
            db.execute('UPDATE threads SET state=?,release=?,updated=? WHERE id=?',
                (body.state,body.release_id,int(time.time()),identity))
            if row['state'] != body.state or row['release'] != body.release_id:
                notify(db,row['owner'],identity,'released' if body.state=='released' else 'state')
        return {'schema':1,'state':body.state,'release_id':body.release_id}

    @app.post('/v1/releases', status_code=201)
    def release(body: ReleaseInput, current=Depends(maintainer)):
        if (body.edition not in EDITIONS or not re.fullmatch(r'sha256:[0-9a-f]{64}',body.digest)
                or not re.fullmatch(r'44\.\d{8}\.\d+',body.version)):
            fail(422,'invalid_release')
        limiter.take(('release',current['id']),3)
        if release_verifier is None or release_verifier(body.edition,body.version,body.digest) is not True:
            fail(422,'verified_release_required')
        identity = body.edition+':'+body.digest
        with store.connect(write=True) as db:
            db.execute('INSERT OR IGNORE INTO releases VALUES (?,?,?,?,1)',
                       (identity,body.edition,body.version,body.digest))
        return {'schema':1,'id':identity,'edition':body.edition,'version':body.version,'digest':body.digest}

    @app.get('/v1/notifications')
    def notifications(current=Depends(user)):
        with store.connect() as db:
            rows = db.execute('SELECT id,thread,event,created,seen FROM notifications WHERE owner=? ORDER BY id DESC LIMIT 100',
                              (current['id'],)).fetchall()
        return {'schema':1,'notifications':[dict(r) for r in rows]}

    @app.post('/v1/notifications/{notification_id}/seen')
    def seen(notification_id: int, current=Depends(user)):
        with store.connect(write=True) as db:
            db.execute('UPDATE notifications SET seen=1 WHERE id=? AND owner=?',(notification_id,current['id']))
        return {'schema':1,'seen':True}

    @app.post('/v1/moderation/{identity}/hide')
    def hide(identity: str, current=Depends(maintainer)):
        with store.connect(write=True) as db:
            thread(db,identity,current)
            db.execute('UPDATE threads SET public=0 WHERE id=?',(identity,))
        return {'schema':1,'public':False}

    @app.post('/v1/moderation/{identity}/account')
    def moderate_account(identity: str, body: AccountModeration, current=Depends(maintainer)):
        with store.connect(write=True) as db:
            row=thread(db,identity,current)
            target=db.execute('SELECT role FROM users WHERE id=?',(row['owner'],)).fetchone()
            if target['role']=='maintainer':
                fail(403,'operator_account_protected')
            db.execute('UPDATE users SET active=? WHERE id=?',(int(body.active),row['owner']))
            if not body.active:
                db.execute('DELETE FROM sessions WHERE user=?',(row['owner'],))
                db.execute('UPDATE threads SET public=0 WHERE owner=?',(row['owner'],))
        return {'schema':1,'active':body.active}

    @app.delete('/v1/threads/{identity}',status_code=204)
    def delete_thread(identity: str,current=Depends(user)):
        # Explicit deletion of one conversation, including its private images.
        # No broad disk cleanup, account-wide purge or unrelated data mutation.
        with store.connect(write=True) as db:
            thread(db,identity,current)
            for table in ('notifications','images','messages'):
                db.execute(f'DELETE FROM {table} WHERE thread=?',(identity,))
            db.execute('DELETE FROM threads WHERE id=?',(identity,))
        return Response(status_code=204)

    return app
