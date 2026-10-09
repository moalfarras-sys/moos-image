"""Native MoOS participation client: asynchronous network, private durable drafts."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

# OSTree's frozen source mtimes cannot validate a previous compiled QML cache.
# This app follows the other first-party launchers and always reads its source.
os.environ['QML_DISABLE_DISK_CACHE'] = '1'

sys.path.insert(0, '/usr/lib/mira/site')
from PySide6.QtCore import (QObject, Property, QRunnable, QThreadPool, QTimer, QUrl,
                           Signal, Slot, QLocale, QBuffer, QByteArray, QIODevice)
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QImageReader, QPainter
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from community.transport import Api, ApiError
from community.outbox import Outbox

ERRORS = {
    'offline': ('الخدمة غير متصلة الآن. أعد المحاولة عند عودة الاتصال.', 'Service offline. Retry when connected.'),
    'invalid_credentials': ('اسم الدخول أو كلمة المرور غير صحيحة.', 'Sign-in details are incorrect.'),
    'registration_closed': ('التسجيل غير متاح حاليًا.', 'Registration is currently closed.'),
    'account_unavailable': ('اسم الدخول مستخدم؛ اختر اسمًا آخر.', 'This sign-in name is unavailable.'),
    'sign_in_required': ('انتهت جلسة الدخول. سجّل الدخول من جديد؛ مسوداتك محفوظة.', 'Session expired. Sign in again; your drafts are saved.'),
    'rate_limited': ('طلبات كثيرة خلال وقت قصير. انتظر قليلًا ثم أعد المحاولة.', 'Too many requests. Wait a little, then retry.'),
    'invalid_image': ('اختر صورة PNG أو JPEG أو WebP ثابتة ومكتملة.', 'Choose a complete, still PNG, JPEG or WebP image.'),
    'image_too_large': ('حد الصورة: 2 ميغابايت و4 ملايين بكسل.', 'Image limit: 2 MB and 4 million pixels.'),
    'verified_release_required': ('الإصدار غير معتمد؛ لا يمكن إعلان صدور الإصلاح.', 'Release verification failed; this fix cannot be announced.'),
    'storage_unavailable': ('مساحة الخدمة منخفضة؛ أعد المحاولة لاحقًا. مسودتك محفوظة.', 'Service storage unavailable. Your draft is saved.'),
}


def private_directory(path):
    path = Path(path)
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = path.lstat()
    if path.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('owned private profile required')
    return path


def normalized_picture(data):
    """Decode a bounded raster, flatten alpha, discard metadata, never hand a URL to Qt."""
    if len(data) > 2*1024*1024:
        raise ApiError('image_too_large')
    buffer = QBuffer()
    buffer.setData(QByteArray(data)); buffer.open(QIODevice.ReadOnly)
    reader = QImageReader(buffer)
    if bytes(reader.format()).lower() not in (b'png', b'jpeg', b'webp'):
        raise ApiError('invalid_image')
    size = reader.size()
    if not size.isValid() or size.width()*size.height() > 4_000_000:
        raise ApiError('image_too_large')
    if reader.supportsAnimation() and reader.imageCount() != 1:
        raise ApiError('invalid_image')
    reader.setAutoTransform(True)
    source = reader.read()
    if source.isNull():
        raise ApiError('invalid_image')
    from PySide6.QtCore import Qt
    if max(source.width(), source.height()) > 1920:
        source = source.scaled(1920, 1920, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    clean = QImage(source.size(), QImage.Format_RGB32)
    clean.fill(0xffffffff)
    painter = QPainter(clean); painter.drawImage(0, 0, source); painter.end()
    output = QBuffer(); output.open(QIODevice.WriteOnly)
    if not clean.save(output, 'PNG'):
        raise ApiError('invalid_image')
    result = bytes(output.data())
    if len(result) > 2*1024*1024:
        raise ApiError('image_too_large')
    return result


class WorkerSignals(QObject):
    finished = Signal(int, object, str, object)


class Worker(QRunnable):
    def __init__(self, generation, work, done):
        super().__init__()
        self.generation, self.work, self.done = generation, work, done
        self.signals = WorkerSignals()

    def run(self):
        try:
            result, error = self.work(), ''
        except ApiError as exc:
            result, error = None, exc.code
        except Exception:
            result, error = None, 'service_unavailable'
        self.signals.finished.emit(self.generation, result, error, self.done)


class Controller(QObject):
    changed = Signal()
    def __init__(self, api, state_root, language=None, parent=None):
        super().__init__(parent)
        self.api, self.root = api, private_directory(state_root)
        self.language = language or ('ar' if QLocale().textDirection().name == 'RightToLeft' else 'en')
        self.pool = QThreadPool(self); self.pool.setMaxThreadCount(2)
        self.jobs = []; self.generation = 0; self.selection = 0
        self.token = None; self.outbox = None; self.cache = None; self.pictures = {}
        self.sending = set()
        self.data = {'signedIn': False, 'displayName': '', 'role': 'member', 'busy': False,
                     'status': '', 'error': False, 'registrationOpen': False,
                     'threads': [], 'suggestions': [], 'messages': [], 'images': [],
                     'selectedThread': '', 'selectedTitle': '', 'selectedState': '',
                     'release': {}, 'hasMore': False, 'pending': 0, 'drafts': [],
                     'picture': '', 'replyPicture': '', 'composer': {}, 'replyDraft': '',
                     'notifications': []}
        self.timer = QTimer(self); self.timer.setInterval(60000)
        self.timer.timeout.connect(self.refresh)

    @Property('QVariantMap', notify=changed)
    def snapshot(self):
        return dict(self.data)

    def tr(self, ar, en):
        return ar if self.language == 'ar' else en

    def publish(self, **changes):
        self.data.update(changes); self.changed.emit()

    def update_pending(self):
        rows = self.outbox.pending() if self.outbox else []
        self.publish(pending=len(rows), drafts=[{'id': r['id'], 'kind': r['kind'],
                     'title': r['payload'].get('title', r['payload'].get('body', ''))[:160]} for r in rows])

    def submit(self, work, done):
        job = Worker(self.generation, work, done); self.jobs.append(job)
        job.signals.finished.connect(self.complete)
        self.publish(busy=True); self.pool.start(job)

    @Slot(int, object, str, object)
    def complete(self, generation, result, error, done):
        self.jobs = [j for j in self.jobs if not (j.generation == generation and j.done is done)]
        if generation != self.generation:
            return
        self.publish(busy=any(j.generation == generation for j in self.jobs))
        if error:
            self.sending.clear()
            ar, en = ERRORS.get(error, ('تعذّرت العملية. أعد المحاولة.', 'Request failed. Retry.'))
            self.publish(status=self.tr(ar, en), error=True)
            if error == 'sign_in_required':
                self.reset_account()
                self.publish(status=self.tr(ar, en), error=True)
            return
        try:
            done(result)
        except (ValueError, KeyError, TypeError, ApiError):
            self.publish(status=self.tr('استجابة غير مكتملة. أعد الفحص.', 'Incomplete response. Check again.'), error=True)

    @Slot()
    def start(self):
        self.submit(lambda: self.api.request('GET', '/v1/health'),
                    lambda r: self.publish(registrationOpen=r.get('registration_open') is True))
        self.loadSuggestions()

    @Slot(str, str, str)
    def register(self, username, password, display_name):
        body = {'username': username.strip().lower(), 'password': password, 'display_name': display_name.strip()}
        def done(result):
            if result.get('created') is not True:
                raise ValueError()
            self.publish(status=self.tr('أُنشئ حسابك. سجّل الدخول.', 'Account created. Sign in.'), error=False)
        self.submit(lambda: self.api.request('POST', '/v1/accounts', body=body), done)

    def reset_account(self):
        self.generation += 1; self.selection += 1; self.timer.stop(); self.pool.clear()
        if self.outbox:
            self.outbox.close(); self.outbox = None
        if self.cache:
            self.cache.cleanup(); self.cache = None
        self.token = None; self.pictures.clear(); self.sending.clear()
        self.publish(signedIn=False, displayName='', role='member', threads=[], messages=[], images=[],
                     selectedThread='', selectedTitle='', selectedState='', release={}, hasMore=False,
                     pending=0, drafts=[], picture='', replyPicture='', composer={}, replyDraft='',
                     notifications=[], status='', busy=False, error=False)

    def signed_in(self, token, user):
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token) or user.get('role') not in ('member', 'maintainer'):
            raise ValueError()
        self.outbox = Outbox(self.root/'drafts', self.api.endpoint, user['username'])
        self.token = token; self.cache = tempfile.TemporaryDirectory(prefix='pictures-', dir=self.root)
        composer, image = self.outbox.composer('report')
        if image:
            self.pictures['report'] = image
        self.publish(signedIn=True, displayName=user['display_name'], role=user['role'],
                     status='', error=False, composer=composer,
                     picture=self.cache_picture(image) if image else '')
        self.update_pending(); self.refresh(); self.timer.start()

    @Slot(str, str)
    def login(self, username, password):
        self.reset_account()
        def done(result):
            self.signed_in(result['token'], result['user'])
        self.submit(lambda: self.api.request('POST', '/v1/session',
                    body={'username': username.strip().lower(), 'password': password}), done)

    def operator_login(self, token):
        self.reset_account()
        self.submit(lambda: self.api.request('GET', '/v1/session', token=token),
                    lambda r: self.signed_in(token, r['user']))

    @Slot()
    def logout(self):
        token = self.token; self.reset_account()
        if token:
            self.submit(lambda: self.api.request('DELETE', '/v1/session', token=token), lambda _: None)

    @Slot()
    def loadSuggestions(self):
        self.submit(lambda: self.api.request('GET', '/v1/suggestions'),
                    lambda r: self.publish(suggestions=r['suggestions']))

    @Slot()
    def refresh(self):
        if self.data['busy']:
            return
        if not self.token:
            self.start()
            return
        token = self.token
        self.submit(lambda: self.api.request('GET', '/v1/threads', token=token),
                    lambda r: self.publish(threads=r['threads']))
        self.submit(lambda: self.api.request('GET', '/v1/notifications', token=token),
                    lambda r: self.publish(notifications=r['notifications']))
        self.loadSuggestions()
        if self.data['selectedThread']:
            self.selectThread(self.data['selectedThread'], preserve=True)

    @Slot(str)
    def selectThread(self, identity, preserve=False):
        if not self.token:
            return
        self.selection += 1; selection = self.selection; token = self.token
        if not preserve:
            payload, image = self.outbox.composer('reply:'+identity)
            self.pictures.pop('reply', None)
            if image:
                self.pictures['reply'] = image
            self.publish(selectedThread=identity, selectedTitle='', selectedState='', messages=[], images=[],
                         hasMore=False, release={}, replyDraft=payload.get('body', ''),
                         replyPicture=self.cache_picture(image) if image else '')
        def done(result):
            if selection != self.selection:
                return
            previous = {i['id']: i.get('source', '') for i in self.data['images']}
            thread = result['thread']
            self.publish(selectedThread=thread['id'], selectedTitle=thread['title'], selectedState=thread['state'],
                         messages=result['messages'], hasMore=result.get('has_more', False),
                         images=[dict(i, source=previous.get(i['id'], '')) for i in result['images']],
                         release=result.get('release') or {})
        self.submit(lambda: self.api.request('GET', '/v1/threads/'+identity, token=token), done)

    @Slot()
    def moreMessages(self):
        if not self.data['messages'] or not self.data['hasMore'] or not self.token:
            return
        identity = self.data['selectedThread']; selection = self.selection; token = self.token
        after = self.data['messages'][-1]['id']
        def done(result):
            if selection != self.selection:
                return
            self.publish(messages=self.data['messages']+result['messages'], hasMore=result.get('has_more', False))
        self.submit(lambda: self.api.request('GET', '/v1/threads/'+identity+'?after='+str(after), token=token), done)

    def cache_picture(self, data):
        if not self.cache:
            raise ValueError('signed-in image cache required')
        path = Path(self.cache.name)/(hashlib.sha256(data).hexdigest()+'.png')
        if not path.exists():
            if sum(p.stat().st_size for p in Path(self.cache.name).glob('*.png'))+len(data) > 32*1024*1024:
                raise ApiError('image_too_large')
            fd = os.open(path, os.O_CREAT|os.O_WRONLY|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
        return QUrl.fromLocalFile(str(path)).toString()

    @Slot(str)
    def loadImage(self, identity):
        if not self.token or not any(i['id'] == identity for i in self.data['images']):
            return
        token, selection = self.token, self.selection
        def done(data):
            if selection != self.selection:
                return
            url = self.cache_picture(data)
            self.publish(images=[dict(i, source=url) if i['id'] == identity else i for i in self.data['images']])
        self.submit(lambda: normalized_picture(self.api.request('GET', '/v1/images/'+identity, token=token)), done)

    @Slot(str, str)
    def choosePicture(self, url, target='report'):
        if not self.outbox or target not in ('report', 'reply'):
            return
        path = Path(QUrl(url).toLocalFile()); selection = self.selection
        def work():
            fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 2*1024*1024:
                    raise ApiError('image_too_large')
                return normalized_picture(stream.read(2*1024*1024+1))
        def done(data):
            if target == 'reply' and selection != self.selection:
                return
            self.pictures[target] = data
            self.publish(**{('picture' if target == 'report' else 'replyPicture'): self.cache_picture(data)}, status='', error=False)
            self.persist_composer(target)
        self.submit(work, done)

    @Slot(str)
    def clearPicture(self, target='report'):
        self.pictures.pop(target, None)
        self.publish(**{('picture' if target == 'report' else 'replyPicture'): ''})
        self.persist_composer(target)

    def persist_composer(self, target):
        if not self.outbox:
            return
        if target == 'report':
            scope, payload = 'report', self.data['composer']
        else:
            if not self.data['selectedThread']:
                return
            scope, payload = 'reply:'+self.data['selectedThread'], {'body': self.data['replyDraft']}
        self.outbox.save_composer(scope, payload, self.pictures.get(target))

    @Slot(str, str, int, bool)
    def saveReportDraft(self, title, body, kind, public):
        self.data['composer'] = {'title': title[:160], 'body': body[:8000], 'kind': kind, 'public': public}
        self.persist_composer('report')

    @Slot(str)
    def saveReplyDraft(self, body):
        self.data['replyDraft'] = body[:8000]; self.persist_composer('reply')

    @Slot(str, str, str, bool)
    def createThread(self, title, body, kind, public):
        if not self.outbox:
            return
        payload = {'title': title.strip(), 'body': body.strip(), 'kind': kind, 'public': public, 'publish_consent': public}
        identity = self.outbox.add('thread', payload, image=self.pictures.get('report'))
        self.outbox.clear_composer('report'); self.pictures.pop('report', None)
        self.publish(composer={}, picture=''); self.update_pending(); self.retry(identity)

    @Slot(str)
    def sendMessage(self, body):
        if not self.outbox or not self.data['selectedThread']:
            return
        identity = self.outbox.add('message', {'body': body.strip()}, image=self.pictures.get('reply'), thread=self.data['selectedThread'])
        self.outbox.clear_composer('reply:'+self.data['selectedThread']); self.pictures.pop('reply', None)
        self.publish(replyDraft='', replyPicture=''); self.update_pending(); self.retry(identity)

    @Slot(str)
    def retry(self, identity):
        if not self.outbox or not self.token or identity in self.sending:
            return
        row = self.outbox.get(identity)
        if not row or row['state'] != 'pending':
            return
        token = self.token; self.sending.add(identity)
        def work():
            if row['kind'] == 'thread':
                return self.api.request('POST', '/v1/threads', body=row['payload'], token=token)
            if row['kind'] == 'message':
                return self.api.request('POST', '/v1/threads/'+row['thread']+'/messages', body=row['payload'], token=token)
            return self.api.request('POST', '/v1/threads/'+row['thread']+'/images', binary=row['image'], retry_id=identity, token=token)
        def done(result):
            self.sending.discard(identity); image_job = None
            if row['kind'] == 'thread':
                image_job = self.outbox.accept_thread(identity, result)
                self.selectThread(result['id'])
            elif row['kind'] == 'message':
                image_job = self.outbox.accept_message(identity, result)
            else:
                self.outbox.received(identity, result)
            self.update_pending()
            self.publish(status=self.tr('تم استلام الرسالة. الصورة تنتظر الإرسال.' if image_job else 'تم الاستلام في خدمة MoOS.',
                         'Message received. Picture pending.' if image_job else 'Received by the MoOS service.'), error=False)
            if image_job:
                self.retry(image_job)
            elif self.outbox.pending():
                self.retryPending()
            else:
                self.refresh()
        self.publish(status=self.tr('جارٍ الإرسال… مسودتك محفوظة.', 'Sending… Your draft is saved.'), error=False)
        self.submit(work, done)

    @Slot()
    def retryPending(self):
        if self.outbox:
            rows = self.outbox.pending()
            if rows:
                self.retry(rows[0]['id'])

    @Slot(str)
    def discardDraft(self, identity):
        if self.outbox and identity not in self.sending:
            self.outbox.discard(identity); self.update_pending()

    @Slot(str)
    def markState(self, state):
        if not self.token or not self.data['selectedThread']:
            return
        identity, token = self.data['selectedThread'], self.token
        self.submit(lambda: self.api.request('PATCH', '/v1/threads/'+identity+'/state', token=token, body={'state': state}),
                    lambda _: self.refresh())

    @Slot(str)
    def hideSuggestion(self, identity):
        token = self.token
        self.submit(lambda: self.api.request('POST', '/v1/moderation/'+identity+'/hide', token=token), lambda _: self.loadSuggestions())

    @Slot(int)
    def markSeen(self, identity):
        token = self.token
        self.submit(lambda: self.api.request('POST', '/v1/notifications/'+str(identity)+'/seen', token=token), lambda _: self.refresh())

    @Slot()
    def deleteConversation(self):
        if not self.token or not self.data['selectedThread']:
            return
        identity, token = self.data['selectedThread'], self.token
        def done(_):
            self.selection += 1
            self.outbox.clear_composer('reply:'+identity)
            self.publish(selectedThread='', selectedTitle='', selectedState='', messages=[], images=[], release={})
            self.refresh()
        self.submit(lambda: self.api.request('DELETE', '/v1/threads/'+identity, token=token), done)

    def close(self):
        self.reset_account()


def read_operator(path):
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError('private operator file required')
        data = json.loads(stream.read(1024))
    if data.get('role') != 'maintainer' or not re.fullmatch(r'[A-Za-z0-9_-]{43}', data.get('token', '')):
        raise ValueError('invalid operator session')
    return data['token']


def main():
    parser = argparse.ArgumentParser(description='MoOS participation')
    parser.add_argument('--service-url')
    parser.add_argument('--service-config', type=Path, default=Path('/usr/share/moos/community-service.json'))
    parser.add_argument('--profile', type=Path, default=Path.home()/'.local/state/moos-community')
    parser.add_argument('--review', action='store_true')
    parser.add_argument('--language', choices=('ar', 'en'))
    parser.add_argument('--operator-session', type=Path)
    parser.add_argument('--capture', type=Path, help='explicit source/image review of this app only')
    args = parser.parse_args()
    if not args.service_url:
        config = json.loads(args.service_config.read_text())
        if type(config.get('schema')) is not int or config['schema'] != 1:
            raise ValueError('valid MoOS service configuration required')
        args.service_url = config['service_url']
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) != 0:
        raise RuntimeError('private process dump protection unavailable')
    if args.language:
        QLocale.setDefault(QLocale('ar_SA' if args.language == 'ar' else 'en_US'))
    app = QGuiApplication([sys.argv[0]])
    app.setLayoutDirection(QLocale().textDirection())
    app.setApplicationName('MoOS Community'); app.setDesktopFileName('org.moos.community')
    app.setWindowIcon(QIcon.fromTheme('moos-logo'))
    controller = Controller(Api(args.service_url, review=args.review), args.profile, args.language)
    engine = QQmlApplicationEngine()
    engine.addImportPath('/usr/lib64/qt6/qml'); engine.addImportPath('/usr/lib/qt6/qml')
    engine.rootContext().setContextProperty('community', controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name('main.qml'))))
    if not engine.rootObjects():
        raise SystemExit('MoOS participation UI failed to load')
    app.aboutToQuit.connect(controller.close)
    if args.capture:
        # Build review has no account or network activity. This is the actual
        # launcher/engine, never a fake backend success or owner screenshot.
        def capture():
            try:
                frame = engine.rootObjects()[0].grabWindow()
                saved = not frame.isNull() and frame.save(str(args.capture))
            except Exception:
                saved = False
            if not saved:
                print('MOOS_COMMUNITY_CAPTURE_FAILED', flush=True)
                app.exit(2)
            else:
                print('MOOS_COMMUNITY_UI_READY', flush=True); app.quit()
        QTimer.singleShot(500, capture)
    else:
        QTimer.singleShot(0, controller.start)
    if args.operator_session:
        token = read_operator(args.operator_session)
        QTimer.singleShot(0, lambda: controller.operator_login(token))
    raise SystemExit(app.exec())


if __name__ == '__main__':
    main()
