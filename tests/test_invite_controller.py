"""Run production controller/channel code at a synthetic engine boundary."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('DYNAMITE_SOURCE_DIR', str(ROOT.parent / 'dynamite')))


class InviteControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ww-invite-controller-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = cls.build(Path(cls.temp.name))

    @classmethod
    def build(cls, destination, mutate=None):
        for name in ('SteamInviteProtocol.h', 'SteamInviteBindings.h', 'SteamInviteController.h', 'SteamInviteController.cpp'):
            content = (SOURCE / 'hook/src' / name).read_text()
            if mutate:
                content = mutate(name, content)
            (destination / name).write_text(content)
        binary = destination / 'controller'
        result = subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++23', '-Wall', '-Wextra', '-Werror', '-pedantic', '-pthread',
            '-I', str(destination), '-I', str(ROOT / 'tests'), str(ROOT / 'tests/dynamite_invite_controller.cpp'),
            str(destination / 'SteamInviteController.cpp'), '-o', str(binary)], text=True, capture_output=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)
        return binary

    def run_case(self, name, binary=None):
        return subprocess.run([str(binary or self.binary), name], text=True, capture_output=True, timeout=15)

    def test_default_and_foreign_thread_guards(self):
        for name in ('defaults', 'threads'):
            with self.subTest(name=name):
                result = self.run_case(name)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_loading_and_target_generation(self):
        result = self.run_case('loading')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cleanup_reentrancy_stale_receipts_and_restart(self):
        result = self.run_case('cleanup')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_host_invites_renewal_and_host_to_guest(self):
        result = self.run_case('hosting')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_friend_expiry_proof_and_foreign_session_guards(self):
        result = self.run_case('safety')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_epoch_duplicate_frame_and_clock_guards(self):
        result = self.run_case('boundaries')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_active_world_generation_fences(self):
        result = self.run_case('generation')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_registration_context_loss_and_unregistration_retry(self):
        result = self.run_case('context_loss')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_owned_epoch_and_renewal_survive_history_pruning(self):
        result = self.run_case('high_water')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sdk_reentrancy_is_rejected_without_corrupting_selection(self):
        result = self.run_case('reentrancy')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_negative_active_world_flags_block_invites(self):
        result = self.run_case('active_world')
        self.assertEqual(result.returncode, 0, result.stderr)

    def mutation(self, needle, replacement, scenario, message):
        def mutate(name, content):
            if name == 'SteamInviteController.cpp':
                self.assertEqual(content.count(needle), 1)
                return content.replace(needle, replacement)
            return content
        with tempfile.TemporaryDirectory(prefix='ww-controller-mutant-') as directory:
            binary = self.build(Path(directory), mutate)
            result = self.run_case(scenario, binary)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)

    def test_stale_ready_generation_mutation_is_caught(self):
        self.mutation('frame.generation > preparedAfter', 'frame.generation >= preparedAfter',
            'loading', 'previous engine generation cannot connect')

    def test_stale_acknowledgement_mutation_is_caught(self):
        self.mutation('|| *outstanding != action', '|| outstanding->kind != action.kind',
            'cleanup', 'stale action acknowledgement rejected')

    def test_cleanup_failure_mutation_is_caught(self):
        self.mutation('if (!success) { cleanupBlocked = true;', 'if (success && false) { cleanupBlocked = true;',
            'cleanup', 'failed cleanup cannot clear ownership')

    def test_active_generation_mutation_is_caught(self):
        self.mutation('if (owned && ownedGeneration && frame.generation != ownedGeneration)',
            'if (owned && ownedGeneration && frame.generation == 0)',
            'generation', 'old connection generation cannot become current world')


if __name__ == '__main__':
    unittest.main()
