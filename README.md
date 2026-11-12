# Checksum-verification tool — Requirements

## 1. Goal

Provide a small command-line checksum-verification tool with one input mode,
one output mode, useful help text, and predictable errors.

This document is the complete public requirements contract for that goal.
It defines observable behavior only and prescribes no implementation
language, internal design, or private process.

## 2. Scope

- In scope: verifying the bytes of one regular file against one expected
  checksum supplied on the command line, reporting the verdict, documenting
  usage via help text, and failing predictably on misuse and environment
  errors.
- Out of scope: checksum generation, multiple input modes (standard input,
  multiple files, directories, recursion, manifest files, remote URLs),
  multiple output modes (machine-readable formats, quiet/verbose flags),
  configuration files, and any network or privileged operation.

## 3. Command shape and the single input mode (normative)

- R1: The tool exposes exactly one executable command named
  `checksum-verify`.
- R2: The tool accepts exactly one input mode: two positional arguments,
  `checksum-verify <file> <expected-sha256>`.
  - `<file>` is a path to a single regular file to verify.
  - `<expected-sha256>` is the expected SHA-256 checksum of the file's
    raw bytes, encoded as exactly 64 hexadecimal characters
    (`[0-9a-fA-F]{64}`). Uppercase and lowercase hex are both accepted and
    compared case-insensitively.
  - No other input mode is supported: no standard-input mode, no zero- or
    three-or-more-argument file mode, no directory mode, no glob expansion
    by the tool itself beyond what the shell passes as one path, no
    `--check` manifest mode, and no flag-based input alternatives.
- R3: The checksum algorithm is fixed to SHA-256 computed over the exact
  raw bytes of `<file>`, with no normalization of line endings, encoding,
  or trailing newlines. An empty file verifies against the well-known
  SHA-256 of the empty string
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## 4. Single output mode (normative)

- R4: The tool has exactly one output mode: human-readable text on
  standard output. There are no format-selection flags (such as
  `--json`/`--quiet`/`--verbose`).
- R5: On a completed verification the tool prints exactly one line to
  standard output and nothing else to standard output:
  - match: `OK <file>` (using the `<file>` argument bytes verbatim),
  - mismatch: `FAIL <file>`.
  - The line is terminated by a single trailing newline.
  - On both the match (exit `0`) and mismatch (exit `1`) paths the tool
    writes nothing to standard error.
- R6: Help output (section 5) is the only other permitted standard-output
  content, and it appears only when help is requested.

## 5. Help text (normative)

- R7: `checksum-verify --help` and `checksum-verify -h` print useful help
  to standard output, write nothing to standard error, and exit with code 0
  without performing verification and without requiring valid
  `<file>`/`<expected-sha256>` arguments.
- R8: The help text states the single input mode (command synopsis with
  the two positional arguments), the SHA-256/hex requirement, the single
  output mode (the `OK`/`FAIL` line), the meaning of each exit code in
  section 6, and at least one match example and one mismatch example.
- R9: `--help`/`-h` takes precedence: when either appears anywhere in the
  invocation, the tool behaves as R7/R8 regardless of other arguments.

## 6. Predictable errors and exit codes (normative)

- R10: Exit codes are fixed and exhaustive:
  - `0`: verification performed and checksum matched, or help requested.
  - `1`: verification performed and checksum did not match.
  - `2`: no verification performed because of a usage or environment
    error (wrong argument count, invalid checksum format, file missing,
    not a regular file, unreadable, or an I/O failure while reading).
- R11: Every exit-`2` condition prints a single human-readable error to
  standard error and prints nothing to standard output. The message names
  the failure category: `usage` (argument count/shape), `invalid checksum`
  (non-hex or wrong length), `file not found` (missing path), `not a file`
  (directory or non-regular file), `unreadable`/`cannot read` (permissions
  or I/O failure). No stack trace or internal path is printed.
- R12: Error behavior is deterministic: the same argv plus the same file
  state always yields the same exit code and the same stderr failure
  category. Verification behavior is deterministic: the same file bytes
  plus the same `<expected-sha256>` (modulo hex case) always yields the
  same exit code and the same stdout line.
- R13: Invalid `<expected-sha256>` (wrong length, non-hex characters, or
  hex with surrounding whitespace) is a usage error (exit `2`), never a
  mismatch (exit `1`). Validation follows a total precedence order:
  checksum-shape validation first, so `invalid checksum` wins over every
  file-side report; then `file not found`; then `not a file`; then
  `unreadable`/`cannot read`. An invalid checksum shape combined with a
  missing, directory, non-regular, or unreadable `<file>` therefore reports
  `invalid checksum`.
- R14: Missing-file, not-a-file, unreadable-file, and read-failure cases
  all exit `2` with the corresponding R11 category; none is reported as a
  mismatch.

## 7. Material boundary cases (normative)

- R15: Zero, one, or three-or-more positional arguments (without
  `--help`/`-h`) exit `2` with a `usage` error stating the expected
  two-argument synopsis.
- R16: A nonexistent `<file>` exits `2` with a `file not found` error
  naming the supplied path.
- R17: A directory (or other non-regular file) passed as `<file>` exits
  `2` with a `not a file` error; the tool never hashes directories.
  Symlinks are resolved (followed) and classified by their target: a
  symlink whose target is a regular file is verified normally against the
  target's bytes; a dangling symlink exits `2` with a `file not found`
  error; a symlink whose target is a directory or other non-regular file
  exits `2` with a `not a file` error.
- R18: An unreadable `<file>` or a mid-read I/O failure exits `2` with an
  `unreadable`/`cannot read` error.
- R19: An empty file verifies normally per R3 (match iff the expected hex
  equals the empty-string SHA-256).
- R20: A file whose bytes differ by even one byte from the expected hash
  preimage exits `1` with `FAIL <file>` on stdout.
- R21: Hex case does not matter: the uppercase and lowercase spellings of
  the same digest both verify identically.

## 8. Testability

Each numbered requirement is verifiable by running the built tool with
controlled argv and fixture files and observing exit codes plus the exact
captured `stdout`/`stderr` streams: R2/R3/R15–R21 by matrixing valid and
invalid argv against empty, small, one-byte-different, dangling-symlink,
directory-target-symlink, and regular-file-symlink fixtures; R4–R6 by
asserting stdout contains exactly the one specified line (or help text
only) and stderr is empty on completed verification paths; R7–R9 by
invoking help with and without other arguments and asserting stdout holds
the help text only with empty stderr; R10–R14 by asserting the exit-code
table and stderr categories, determinism by repeat runs, and total
precedence by combining an invalid checksum with missing, directory,
non-regular, and unreadable fixtures in the R13 order.

## 9. Unresolved requirements

None. Every behavior above is implementable and testable as written; no
requirement is blocked on an external decision.
