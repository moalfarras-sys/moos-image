"""Train Mira's wake word on the owner's recordings (local only) and describe the result honestly.

The recordings come from the Echo's own listening windows (see LiveVoice.arm_capture), so they
carry the same microphones, beamformer and room as the detector hears. Training runs the
`wake_training/train_owner.py` pipeline in its own environment; nothing is uploaded.
"""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRAINER = ROOT / 'wake_training' / 'train_owner.py'
TRAIN_ENV = Path(os.environ.get('MIRA_WAKE_TRAIN_ENV', Path.home() / '.local/share/mira/wake-train'))


def trainer_python():
    for candidate in (TRAIN_ENV / 'venv/bin/python', TRAIN_ENV / 'bin/python'):
        if candidate.exists():
            return candidate
    return None


def train(enrol_dir, models_dir, model_id, timeout=1800):
    """Returns {'status', 'holdout_hits', 'holdout_total', 'false_per_hour', 'cutoff', ...}."""
    enrol_dir, models_dir = Path(enrol_dir), Path(models_dir)
    python = trainer_python()
    if python is None or not TRAINER.exists():
        return {'status': 'error', 'error': 'trainer_not_installed'}
    owner = enrol_dir / 'mira'
    if len(list(owner.glob('*.wav'))) < 3:
        return {'status': 'error', 'error': 'too_few_recordings'}
    models_dir.mkdir(parents=True, exist_ok=True)
    work = TRAIN_ENV / 'runs' / model_id
    work.mkdir(parents=True, exist_ok=True)
    command = [str(python), str(TRAINER), '--owner', str(owner), '--out', str(work), '--id', model_id]
    if (enrol_dir / 'other').is_dir() and any((enrol_dir / 'other').glob('*.wav')):
        command += ['--negatives', str(enrol_dir / 'other')]
    env = dict(os.environ, MIRA_WAKE_TRAIN_ENV=str(TRAIN_ENV))
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env,
                                stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': 'timeout'}
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or '').strip().splitlines()[-1:] or ['failed']
        return {'status': 'error', 'error': tail[0][:160]}
    report_file = work / 'report.json'
    try:
        report = json.loads(report_file.read_text())
    except (OSError, ValueError):
        return {'status': 'error', 'error': 'no_report'}
    model = work / f'{model_id}.tflite'
    manifest = work / f'{model_id}.json'
    if not model.exists() or not manifest.exists():
        return {'status': 'error', 'error': 'no_model'}
    for source in (model, manifest):
        target = models_dir / source.name
        target.write_bytes(source.read_bytes())
        os.chmod(target, 0o644)
    return {'status': 'ok', **summarize(report)}


def summarize(report):
    """The few numbers the owner sees; the full report stays on disk."""
    cutoff = report.get('recommended_cutoff', 0.5)
    holdout = report.get('owner_holdout') or {}
    at = (holdout.get('by_cutoff') or {}).get(str(cutoff)) or {}
    return {'cutoff': cutoff,
            'holdout_hits': at.get('hits', holdout.get('hits')),
            'holdout_total': holdout.get('total'),
            'false_per_hour': report.get('false_accepts_per_hour_estimate'),
            'report': report.get('path', '')}
