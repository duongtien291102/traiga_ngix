"""Run with python -m unittest discover -s tests (requires FFmpeg and sh)."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'normalize-recording.sh'
SHELL = (r'C:\Program Files\Git\bin\bash.exe' if os.name == 'nt'
         else shutil.which('sh'))


def run(*args):
    return subprocess.run(args, check=True, capture_output=True)


@unittest.skipUnless(SHELL and shutil.which('ffmpeg') and shutil.which('ffprobe'),
                     'FFmpeg, ffprobe and sh are required')
class RecordingSyncTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='dvr sync ')
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / 'recording.mp4'

    def fixture(self, audio=True):
        args = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                'testsrc2=size=160x90:rate=25:duration=4']
        if audio:
            args += ['-f', 'lavfi', '-i', 'sine=sample_rate=48000:duration=4',
                     '-af', r'aselect=not(between(t\,1\,1.5))', '-c:a', 'aac']
        run(*args, '-c:v', 'libx264', str(self.file))

    def normalize(self):
        run(SHELL, str(SCRIPT), str(self.file))

    def packets(self):
        result = run('ffprobe', '-v', 'error', '-select_streams', 'a:0',
                     '-show_packets', '-show_entries', 'packet=pts_time',
                     '-of', 'json', str(self.file))
        return [float(p['pts_time']) for p in json.loads(result.stdout)['packets']]

    def video_hash(self):
        return run('ffmpeg', '-v', 'error', '-i', str(self.file), '-map', '0:v:0',
                   '-c', 'copy', '-f', 'hash', '-').stdout

    def test_audio_gaps_become_samples_and_video_is_unchanged(self):
        self.fixture()
        original_pts = self.packets()
        self.assertGreater(max(b - a for a, b in zip(original_pts, original_pts[1:])), .4)
        video_hash = self.video_hash()
        mtime = self.file.stat().st_mtime_ns
        self.normalize()
        pts = self.packets()
        for a, b in zip(pts, pts[1:]):
            self.assertAlmostEqual(b - a, 1024 / 48000, places=5)
        self.assertAlmostEqual(pts[-1], original_pts[-1], delta=.05)
        self.assertEqual(self.video_hash(), video_hash)
        self.assertEqual(self.file.stat().st_mtime_ns, mtime)
        self.assertTrue(Path(str(self.file) + '.avsync-v1').is_file())
        digest = hashlib.sha256(self.file.read_bytes()).digest()
        self.normalize()
        self.assertEqual(hashlib.sha256(self.file.read_bytes()).digest(), digest)

    def test_old_faststart_marker_does_not_skip_audio_repair(self):
        self.fixture()
        Path(str(self.file) + '.fixed').touch()
        self.normalize()
        self.assertTrue(Path(str(self.file) + '.avsync-v1').is_file())

    def test_unfinished_mp4_is_not_replaced_or_marked(self):
        self.file.write_bytes(b'not a finalized MP4')
        self.normalize()
        self.assertEqual(self.file.read_bytes(), b'not a finalized MP4')
        self.assertFalse(Path(str(self.file) + '.avsync-v1').exists())
        self.assertFalse(Path(str(self.file) + '.sync.tmp.mp4').exists())

    def test_video_without_audio(self):
        self.fixture(audio=False)
        video_hash = self.video_hash()
        self.normalize()
        self.assertEqual(self.video_hash(), video_hash)
        self.assertTrue(Path(str(self.file) + '.avsync-v1').is_file())


if __name__ == '__main__':
    unittest.main()
