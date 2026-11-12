"""Repository-native tests for the checksum-verify public requirements."""

import hashlib
import os
import stat
import subprocess
import tempfile
import unittest

TOOL = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "checksum-verify")

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def run_tool(*args, cwd=None):
    return subprocess.run(
        [TOOL] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )


def write_fixture(directory, name, data):
    path = os.path.join(directory, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


class ChecksumVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def digest_of(self, data):
        return hashlib.sha256(data).hexdigest()

    def test_match_exit_zero_exact_stdout_empty_stderr(self):
        path = write_fixture(self.tmp.name, "small.bin", b"hello world")
        proc = run_tool(path, self.digest_of(b"hello world"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, ("OK %s\n" % path).encode())
        self.assertEqual(proc.stderr, b"")

    def test_mismatch_exit_one_exact_stdout_empty_stderr(self):
        path = write_fixture(self.tmp.name, "small.bin", b"hello world")
        proc = run_tool(path, "0" * 64)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, ("FAIL %s\n" % path).encode())
        self.assertEqual(proc.stderr, b"")

    def test_empty_file_matches_known_digest(self):
        path = write_fixture(self.tmp.name, "empty.bin", b"")
        self.assertEqual(EMPTY_SHA256,
                         "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        proc = run_tool(path, EMPTY_SHA256)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, ("OK %s\n" % path).encode())
        self.assertEqual(proc.stderr, b"")

    def test_empty_file_mismatch(self):
        path = write_fixture(self.tmp.name, "empty.bin", b"")
        proc = run_tool(path, "0" * 64)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, ("FAIL %s\n" % path).encode())

    def test_one_byte_difference_is_mismatch(self):
        data = b"hello world"
        path = write_fixture(self.tmp.name, "data.bin", b"hello worle")
        proc = run_tool(path, self.digest_of(data))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, ("FAIL %s\n" % path).encode())
        self.assertEqual(proc.stderr, b"")

    def test_hex_case_insensitive(self):
        data = b"case-bytes"
        digest = self.digest_of(data)
        path = write_fixture(self.tmp.name, "case.bin", data)
        lower = run_tool(path, digest.lower())
        upper = run_tool(path, digest.upper())
        self.assertEqual(lower.returncode, 0)
        self.assertEqual(upper.returncode, 0)
        self.assertEqual(lower.stdout, upper.stdout)
        self.assertEqual(lower.stderr, b"")
        self.assertEqual(upper.stderr, b"")

    def test_help_long_flag(self):
        proc = run_tool("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        text = proc.stdout.decode()
        self.assertIn("checksum-verify <file> <expected-sha256>", text)
        self.assertIn("SHA-256", text)
        self.assertIn("64", text)
        self.assertIn("OK", text)
        self.assertIn("FAIL", text)
        self.assertIn("0", text)
        self.assertIn("1", text)
        self.assertIn("2", text)

    def test_help_short_flag(self):
        proc = run_tool("-h")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        self.assertTrue(proc.stdout)

    def test_help_takes_precedence_over_bad_args(self):
        proc = run_tool("--help", "whatever", "zzz")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        self.assertTrue(proc.stdout)
        proc = run_tool("/nonexistent", "zzz", "-h")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        self.assertTrue(proc.stdout)

    def test_help_needs_no_valid_args(self):
        proc = run_tool("--help", "/nonexistent", "not-hex")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")

    def test_argument_counts_are_usage_errors(self):
        for args in ([], ["only-one"], ["a", "b", "c"]):
            proc = run_tool(*args)
            self.assertEqual(proc.returncode, 2, args)
            self.assertEqual(proc.stdout, b"", args)
            self.assertIn(b"usage", proc.stderr.lower(), args)
            self.assertIn(b"checksum-verify <file> <expected-sha256>",
                          proc.stderr, args)
            self.assertEqual(proc.stderr.count(b"\n"), 1, args)

    def test_invalid_checksum_shapes(self):
        path = write_fixture(self.tmp.name, "ok.bin", b"data")
        bad_values = [
            "0" * 63,
            "0" * 65,
            "",
            "z" * 64,
            "0" * 63 + "g",
            " " + self.digest_of(b"data"),
            self.digest_of(b"data") + " ",
            "  ",
        ]
        for bad in bad_values:
            proc = run_tool(path, bad)
            self.assertEqual(proc.returncode, 2, repr(bad))
            self.assertEqual(proc.stdout, b"", repr(bad))
            self.assertIn(b"invalid checksum", proc.stderr.lower(),
                          repr(bad))

    def test_invalid_checksum_wins_over_missing_file(self):
        proc = run_tool(os.path.join(self.tmp.name, "missing.bin"), "zzz")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"invalid checksum", proc.stderr.lower())

    def test_invalid_checksum_wins_over_directory(self):
        proc = run_tool(self.tmp.name, "zzz")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"invalid checksum", proc.stderr.lower())

    def test_invalid_checksum_wins_over_unreadable(self):
        path = write_fixture(self.tmp.name, "locked.bin", b"data")
        os.chmod(path, 0)
        try:
            proc = run_tool(path, "zzz")
        finally:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"invalid checksum", proc.stderr.lower())

    def test_missing_file(self):
        missing = os.path.join(self.tmp.name, "nope.bin")
        proc = run_tool(missing, "0" * 64)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"file not found", proc.stderr.lower())
        self.assertIn(missing.encode(), proc.stderr)

    def test_directory_is_not_a_file(self):
        proc = run_tool(self.tmp.name, "0" * 64)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"not a file", proc.stderr.lower())

    def test_unreadable_file(self):
        path = write_fixture(self.tmp.name, "locked.bin", b"secret")
        os.chmod(path, 0)
        try:
            proc = run_tool(path, "0" * 64)
        finally:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        lowered = proc.stderr.lower()
        self.assertTrue(b"unreadable" in lowered or b"cannot read" in lowered)

    def test_symlink_to_regular_file_verifies_normally(self):
        target = write_fixture(self.tmp.name, "target.bin", b"linked bytes")
        link = os.path.join(self.tmp.name, "link.bin")
        os.symlink(target, link)
        proc = run_tool(link, self.digest_of(b"linked bytes"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, ("OK %s\n" % link).encode())
        self.assertEqual(proc.stderr, b"")

    def test_dangling_symlink_is_file_not_found(self):
        link = os.path.join(self.tmp.name, "dangling.bin")
        os.symlink(os.path.join(self.tmp.name, "ghost.bin"), link)
        proc = run_tool(link, "0" * 64)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"file not found", proc.stderr.lower())

    def test_symlink_to_directory_is_not_a_file(self):
        link = os.path.join(self.tmp.name, "dirlink")
        os.symlink(self.tmp.name, link)
        proc = run_tool(link, "0" * 64)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"not a file", proc.stderr.lower())

    def test_verification_is_deterministic(self):
        path = write_fixture(self.tmp.name, "det.bin", b"deterministic")
        digest = self.digest_of(b"deterministic")
        first = run_tool(path, digest)
        second = run_tool(path, digest)
        self.assertEqual((first.returncode, first.stdout, first.stderr),
                         (second.returncode, second.stdout, second.stderr))

    def test_errors_have_no_stack_trace(self):
        proc = run_tool(os.path.join(self.tmp.name, "nope.bin"), "0" * 64)
        self.assertNotIn(b"Traceback", proc.stderr)
        proc = run_tool("only-one-arg")
        self.assertNotIn(b"Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
