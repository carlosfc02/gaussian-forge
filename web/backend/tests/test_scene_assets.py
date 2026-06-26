import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.services import scene_service


class SceneAssetTests(unittest.TestCase):
    def test_selects_highest_3dgs_iteration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            gs_root = Path(temporary_directory)
            for iteration in (1000, 30000, 7000):
                path = gs_root / 'scene' / 'gs' / 'model' / 'point_cloud' / f'iteration_{iteration}'
                path.mkdir(parents=True)
                (path / 'point_cloud.ply').write_text(str(iteration), encoding='utf-8')

            with patch.object(scene_service, 'GS_DIR', gs_root):
                result = scene_service.find_latest_3dgs_ply('scene')

            self.assertIsNotNone(result)
            path, iteration = result
            self.assertEqual(iteration, 30000)
            self.assertEqual(path.read_text(encoding='utf-8'), '30000')

    def test_obj_archive_contains_model_material_and_texture(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            sugar_root = Path(temporary_directory)
            mesh_root = sugar_root / 'scene' / 'refined_mesh' / 'source'
            mesh_root.mkdir(parents=True)
            for filename in ('model.obj', 'model.mtl', 'texture.png'):
                (mesh_root / filename).write_text(filename, encoding='utf-8')

            with patch.object(scene_service, 'SUGAR_OUTPUT_DIR', sugar_root):
                archive_path = scene_service.build_sugar_obj_archive('scene')

            try:
                with zipfile.ZipFile(archive_path) as archive:
                    self.assertEqual(set(archive.namelist()), {'model.obj', 'model.mtl', 'texture.png'})
            finally:
                archive_path.unlink(missing_ok=True)

    def test_clear_generated_data_preserves_video_gt_and_variants(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            videos = root / 'videos'
            frames = root / 'frames'
            masks = root / 'masks'
            gs = root / '3dgs'
            sugar = root / 'sugar'
            metrics = root / 'metrics'
            jobs = root / 'jobs'
            logs = root / 'logs'
            gt = root / 'GT'
            for directory in (videos, frames, masks, gs, sugar, metrics, jobs, logs, gt):
                directory.mkdir(parents=True)

            video = videos / 'scene.mp4'
            video.write_text('video', encoding='utf-8')
            (frames / 'scene.jpg').write_text('thumbnail', encoding='utf-8')
            for directory in (
                masks / 'scene',
                gs / 'scene',
                sugar / 'scene',
                metrics / 'segmentation' / 'scene',
                logs / 'scene',
                gt / 'scene',
                sugar / 'scene_variant',
            ):
                directory.mkdir(parents=True)
                (directory / 'content').write_text('content', encoding='utf-8')
            job = jobs / 'scene_job.json'
            job.write_text('{}', encoding='utf-8')

            patches = (
                patch.object(scene_service, 'VIDEOS_DIR', videos),
                patch.object(scene_service, 'FRAMES_VIDEOS_DIR', frames),
                patch.object(scene_service, 'MASKS_DIR', masks),
                patch.object(scene_service, 'GS_DIR', gs),
                patch.object(scene_service, 'SUGAR_OUTPUT_DIR', sugar),
                patch.object(scene_service, 'DATA_DIR', root),
                patch.object(scene_service, 'SEGMENTATION_JOBS_DIR', jobs),
                patch.object(scene_service, 'LOGS_DIR', logs),
                patch.object(scene_service, 'build_scene_read', return_value='scene-read'),
                patch('app.services.pipeline_service.ensure_no_active_pipeline'),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
                result = scene_service.clear_scene_generated_data('scene')

            self.assertEqual(result, 'scene-read')
            self.assertTrue(video.exists())
            self.assertTrue((gt / 'scene').exists())
            self.assertTrue((sugar / 'scene_variant').exists())
            self.assertFalse((masks / 'scene').exists())
            self.assertFalse((gs / 'scene').exists())
            self.assertFalse((sugar / 'scene').exists())
            self.assertFalse((metrics / 'segmentation' / 'scene').exists())
            self.assertFalse(job.exists())
            self.assertFalse((logs / 'scene').exists())

    def test_clear_reports_unwritable_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            videos = root / 'videos'
            masks = root / 'masks'
            videos.mkdir()
            masks.mkdir()
            (videos / 'scene.mp4').write_text('video', encoding='utf-8')
            blocked = masks / 'scene'
            blocked.mkdir()

            with patch.object(scene_service, 'VIDEOS_DIR', videos), patch.object(
                scene_service, 'MASKS_DIR', masks
            ), patch.object(
                scene_service, '_ensure_removable', side_effect=PermissionError(str(blocked))
            ), patch('app.services.pipeline_service.ensure_no_active_pipeline'):
                with self.assertRaises(HTTPException) as error:
                    scene_service.clear_scene_generated_data('scene')

            self.assertEqual(error.exception.status_code, 409)
            self.assertIn('not writable', error.exception.detail)
            self.assertTrue(blocked.exists())

    def test_clear_rejects_active_pipeline(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            videos = Path(temporary_directory)
            (videos / 'scene.mp4').write_text('video', encoding='utf-8')
            with patch.object(scene_service, 'VIDEOS_DIR', videos), patch(
                'app.services.pipeline_service.ensure_no_active_pipeline',
                side_effect=HTTPException(status_code=409, detail='active'),
            ):
                with self.assertRaises(HTTPException) as error:
                    scene_service.clear_scene_generated_data('scene')
            self.assertEqual(error.exception.status_code, 409)

    def test_launch_3dgs_viewer_uses_linux_script(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            gs = root / '3dgs'
            scripts = root / 'scripts'
            (gs / 'scene' / 'gs' / 'model').mkdir(parents=True)
            (gs / 'scene' / 'gs' / 'source').mkdir(parents=True)
            scripts.mkdir()
            script = scripts / 'open_3dgs_viewer.sh'
            script.write_text('#!/usr/bin/env bash\n', encoding='utf-8')

            with patch.object(scene_service, 'GS_DIR', gs), patch.object(
                scene_service, 'SCRIPTS_DIR', scripts
            ), patch.object(scene_service, '_run_viewer_script', return_value='launched') as run:
                result = scene_service.launch_3dgs_viewer('scene')

            self.assertEqual(result, 'launched')
            command = run.call_args.args[2]
            self.assertEqual(command[0], 'bash')
            self.assertEqual(Path(command[1]), script)
            self.assertIn('--scene-dir', command)
            self.assertIn('3dgs/scene', command)
            self.assertFalse(any('powershell' in part.lower() for part in command))

    def test_launch_sugar_viewer_uses_linux_script(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            gs = root / '3dgs'
            sugar = root / 'sugar_output'
            scripts = root / 'scripts'
            (gs / 'scene' / 'gs' / 'model').mkdir(parents=True)
            (gs / 'scene' / 'gs' / 'source').mkdir(parents=True)
            refined = sugar / 'scene' / 'refined_ply' / 'source'
            refined.mkdir(parents=True)
            (refined / 'model.ply').write_text('ply', encoding='utf-8')
            scripts.mkdir()
            script = scripts / 'open_sugar_viewer.sh'
            script.write_text('#!/usr/bin/env bash\n', encoding='utf-8')

            patches = (
                patch.object(scene_service, 'GS_DIR', gs),
                patch.object(scene_service, 'SUGAR_OUTPUT_DIR', sugar),
                patch.object(scene_service, 'SCRIPTS_DIR', scripts),
                patch.object(scene_service, '_run_viewer_script', return_value='launched'),
            )
            with patches[0], patches[1], patches[2], patches[3] as run:
                result = scene_service.launch_sugar_viewer('scene')

            self.assertEqual(result, 'launched')
            command = run.call_args.args[2]
            self.assertEqual(command[0], 'bash')
            self.assertEqual(Path(command[1]), script)
            self.assertIn('--ply-path', command)
            self.assertIn('--source-dir', command)
            self.assertIn('--base-model-dir', command)
            self.assertFalse(any('powershell' in part.lower() for part in command))

    def test_viewer_script_failure_is_reported_as_conflict(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            logs = Path(temporary_directory) / 'logs'
            completed = subprocess.CompletedProcess(
                args=['bash', 'scripts/open_3dgs_viewer.sh'],
                returncode=1,
                stdout='',
                stderr='DISPLAY is not set. Start WSLg/X11 before launching the viewer.',
            )
            with patch.object(scene_service, 'LOGS_DIR', logs), patch.object(
                scene_service.subprocess, 'run', return_value=completed
            ):
                with self.assertRaises(HTTPException) as error:
                    scene_service._run_viewer_script('scene', '3dgs', ['bash', 'scripts/open_3dgs_viewer.sh'])

            self.assertEqual(error.exception.status_code, 409)
            self.assertIn('DISPLAY is not set', error.exception.detail)
            self.assertTrue((logs / 'scene' / 'viewer_3dgs.log').exists())


if __name__ == '__main__':
    unittest.main()
