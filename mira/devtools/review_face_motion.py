"""Render the real GPU face with a WAV playback envelope; no assistant/device calls.

Run with the shipped Python dependencies and a GPU Qt session. Keep recordings
and visual proofs outside Git. The MP4 contains just the face, never the desktop.
"""
import argparse
import math
from pathlib import Path
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQuick import QQuickView
from faces import FaceProvider
from live_voice import ECHO_BLOCK, mouth_energy, pcm_peak


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--face', choices=('rose', 'holo'), default='rose')
    parser.add_argument('--legacy', action='store_true', help='peak-only envelope on the current renderer')
    args = parser.parse_args()
    with wave.open(str(args.audio)) as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            parser.error('audio must be 16 kHz S16 mono')
        pcm = audio.readframes(audio.getnframes())
    seconds = len(pcm) / 32000
    args.output.parent.mkdir(parents=True, exist_ok=True)
    qml = args.output.with_suffix('.qml')
    qml.write_text("""import QtQuick
import Mira
Rectangle { width: 600; height: 600; color: '#0b0913'
MiraCore { objectName: 'face'; anchors.fill: parent; phase: 'speaking'; motion: true; faceStyle: '""" + args.face + """' }
}""")
    app = QGuiApplication([])
    view = QQuickView()
    view.engine().addImportPath(str(ROOT / 'qml'))
    view.engine().addImageProvider('mira', FaceProvider())
    view.setSource(QUrl.fromLocalFile(str(qml)))
    if view.status() == QQuickView.Error:
        return 1
    face = view.rootObject().findChild(QObject, 'face')
    view.show()
    frames = {'index': 0, 'encoder': None, 'last_packet': -1}
    def capture():
        i = frames['index']; t = i / 30
        if t >= seconds:
            face.setProperty('phase', 'idle')
        if i % 2 == 0:
            offset = min(len(pcm), int(t * 32000) // ECHO_BLOCK * ECHO_BLOCK)
            block = pcm[offset:offset + ECHO_BLOCK]
            energy = min(1.0, pcm_peak(block) / 16000) if block else 0
            face.setProperty('level', energy)
            face.setProperty('mouthLevel', energy if args.legacy else (mouth_energy(block) if block else 0))
            face.setProperty('mouthPacket', i)
        face.setProperty('clock', t)
        image = view.grabWindow().scaled(600, 600).convertToFormat(QImage.Format_RGBA8888)
        if frames['encoder'] is None:
            frames['encoder'] = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo',
                '-pixel_format', 'rgba', '-video_size', f'{image.width()}x{image.height()}',
                '-framerate', '30', '-i', '-', '-i', str(args.audio), '-c:v', 'libx264',
                '-preset', 'fast', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                '-movflags', '+faststart', str(args.output)], stdin=subprocess.PIPE)
        frames['encoder'].stdin.write(image.constBits().tobytes())
        if i % 30 == 0:
            image.save(str(args.output.with_name(args.output.stem + f'-{i:04}.jpg')), 'JPG', 90)
        frames['index'] += 1
        if t > seconds + 1:
            timer.stop()
            frames['encoder'].stdin.close()
            result = frames['encoder'].wait()
            qml.unlink()
            print('face review', args.face, 'frames', frames['index'], 'encoder exit', result, flush=True)
            app.exit(result)
    timer = QTimer(interval=33)
    timer.timeout.connect(capture)
    QTimer.singleShot(600, timer.start)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
