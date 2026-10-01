# SQLite WAL Backup And Restore Proof

Read only for a SQLite WAL backup/restore audit. This is proof guidance, not write or repair authority.

1. Trace each named wrapper to its actual backup helper before diagnosing a main-file copy. A manifest's raw main-file replacement instruction is a separate restore risk, not proof its backup used `copyfile`.
2. On a temporary WAL database, hold a reader across a committed write. Compare the backup's logical rows with the live committed state. Test restore separately after another write; backup success alone does not prove restore correctness.
3. Check for backup sidecars before reopening it: opening a WAL-mode backup can create them. Explicitly close every test connection before temporary-directory cleanup on Windows.
4. Report the backup and restore verdicts separately with their evidence. Any repair still requires its own scoped authority.
