"""
System update utilities for managing app deployments.

This module provides a simple, portable way to manage system updates via git
and Docker Compose. It automatically detects the deployment environment and
uses the appropriate paths and commands.
"""
import subprocess
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class SystemUpdateManager:
    """Manages system updates via git and docker compose."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self._project_info = None

    def _get_project_info(self) -> Dict[str, str]:
        """
        Auto-detect Docker project information from the running container.
        This makes the code portable across different deployments.
        """
        if self._project_info:
            return self._project_info

        try:
            # Get our own container ID
            hostname = os.environ.get('HOSTNAME', '')
            if not hostname:
                with open('/etc/hostname', 'r') as f:
                    hostname = f.read().strip()

            # Inspect our own container to get project info
            result = subprocess.run(
                ['docker', 'inspect', hostname],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                container_info = json.loads(result.stdout)[0]
                # Compose labels live under .Config.Labels in `docker inspect`,
                # not at the top level. The original code looked at the top
                # level, got an empty dict, and silently fell back to wrong
                # defaults — which made the sidecar updater run against a
                # phantom project.
                labels = container_info.get('Config', {}).get('Labels', {}) or {}

                project_name = labels.get('com.docker.compose.project')
                working_dir = labels.get('com.docker.compose.project.working_dir')
                config_files = labels.get('com.docker.compose.project.config_files')

                if project_name and working_dir:
                    # config_files is comma-separated when the user started
                    # compose with multiple -f flags (e.g. COMPOSE_FILE set
                    # to compose.yaml:compose.traefik.yaml). We need to
                    # preserve all of them so the next `up -d` reconstructs
                    # the same compose merge — otherwise switching to a
                    # Traefik-style override would silently fall back to the
                    # default file on the next update.
                    if config_files:
                        config_file_list = [f.strip() for f in config_files.split(',') if f.strip()]
                    else:
                        config_file_list = ['compose.yaml']
                    self._project_info = {
                        'project_name': project_name,
                        'working_dir': working_dir,
                        'config_file': config_file_list[0],          # legacy single-file callers
                        'config_files': config_file_list,            # full list for the sidecar
                        'container_id': hostname,
                    }
                    return self._project_info

                print(
                    "Warning: compose labels missing on this container "
                    f"(project={project_name!r}, working_dir={working_dir!r}). "
                    "Falling back to defaults — the sidecar updater may target "
                    "the wrong project."
                )
        except Exception as e:
            print(f"Warning: Could not auto-detect project info: {e}")

        # Conservative fallback. We hardcode the known production defaults
        # rather than self.repo_path (which is the *container* path /app —
        # not what `docker run -v` needs on the host).
        self._project_info = {
            'project_name': 'kbm',
            'working_dir': '/opt/kbm',
            'config_file': 'compose.yaml',
            'config_files': ['compose.yaml'],
            'container_id': os.environ.get('HOSTNAME', 'python-app'),
        }
        return self._project_info

    def run_command(self, cmd: List[str], timeout: int = 300, cwd: str = None) -> Tuple[bool, str]:
        """Run a shell command and return (success, output)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            success = result.returncode == 0
            if success:
                output = result.stdout
            else:
                # Combine both streams on failure — git and docker split
                # diagnostics across stdout/stderr, and losing either half
                # has repeatedly made update failures undebuggable.
                output = "\n".join(p for p in (result.stderr, result.stdout) if p and p.strip())
            return success, output.strip()
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout} seconds"
        except Exception as e:
            return False, f"Error executing command: {str(e)}"

    def _get_own_image(self) -> Optional[str]:
        """Return the image tag this container runs, or None outside docker."""
        info = self._get_project_info()
        success, image = self.run_command(
            ['docker', 'inspect', '-f', '{{.Config.Image}}', info['container_id']],
            timeout=5,
        )
        image = (image or "").strip()
        return image if success and image else None

    def _get_update_branch(self) -> str:
        """Resolve which branch updates should track.

        Order: UPDATE_BRANCH env var -> current checked-out branch ->
        origin's default branch -> 'main'. Handles detached HEAD (a state
        past failed updates have left repos in), which used to make branch
        detection return the literal string 'HEAD' and break every
        subsequent fetch/reset.
        """
        env_branch = (os.environ.get('UPDATE_BRANCH') or '').strip()
        if env_branch:
            return env_branch

        success, branch = self.run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], timeout=15)
        branch = (branch or "").strip()
        if success and branch and branch != 'HEAD':
            return branch

        # Detached HEAD — fall back to origin's default branch.
        success, ref = self.run_command(
            ['git', 'symbolic-ref', 'refs/remotes/origin/HEAD'], timeout=15
        )
        if success and ref.strip().startswith('refs/remotes/origin/'):
            return ref.strip().rsplit('/', 1)[-1]
        return 'main'

    def check_docker_available(self) -> Tuple[bool, str]:
        """Check if docker and docker compose are available."""
        # Check docker
        success, output = self.run_command(['docker', '--version'], timeout=5)
        if not success:
            return False, "Docker CLI not available in container"

        # Check docker socket
        if not os.path.exists('/var/run/docker.sock'):
            return False, "Docker socket not mounted at /var/run/docker.sock"

        # Check docker compose
        success, output = self.run_command(['docker', 'compose', 'version'], timeout=5)
        if not success:
            return False, "Docker Compose plugin not available"

        return True, "Docker and Docker Compose are available"

    def get_current_version(self) -> Dict[str, str]:
        """Get current git commit information."""
        # Get commit hash and message
        success, output = self.run_command(['git', 'log', '-1', '--format=%h %s'])
        if not success:
            return {"error": output}

        parts = output.split(' ', 1)
        commit_hash = parts[0] if len(parts) > 0 else "unknown"
        commit_message = parts[1] if len(parts) > 1 else ""

        # Get commit date
        success, commit_date = self.run_command(['git', 'log', '-1', '--format=%ci'])
        commit_date = commit_date if success else "unknown"

        # Get branch name
        success, branch = self.run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        branch = branch if success else "unknown"

        return {
            "commit_hash": commit_hash,
            "commit_message": commit_message,
            "commit_date": commit_date,
            "branch": branch
        }

    def _fix_git_ownership_via_sidecar(self) -> Tuple[bool, str]:
        """Self-heal `.git` ownership before a fetch/pull.

        The repo on the host accumulates root-owned files whenever an operator
        runs `git pull` directly from an SSH session (host user is usually
        root on a single-purpose VPS). Subsequent in-container fetches —
        running as the non-root appuser, UID 1000 — then fail with
        "insufficient permission for adding an object" because git can't
        write new pack files alongside the root-owned ones.

        We can't chown from inside python-app (appuser is unprivileged), so
        we spawn a tiny short-lived alpine container as root via the mounted
        docker socket. It chowns the host's repo to UID 1000:1000, exits,
        and the in-container fetch proceeds with predictable ownership.

        Synchronous (we wait for the sidecar to exit). Sub-second in
        practice. Best-effort: failures are logged and we continue, since
        the chmod fallback below + appuser already owning some of the tree
        often gets us through.
        """
        info = self._get_project_info()
        host_working_dir = info.get('working_dir')
        if not host_working_dir:
            return False, "no working_dir on container labels — skipping ownership fix"

        # Prefer our own image (always present locally, has chown) so this
        # never depends on pulling alpine over the network — a failure mode
        # we've hit on locked-down VPSes. Alpine remains the fallback when
        # image detection fails.
        image = self._get_own_image() or 'alpine:latest'
        cmd = [
            'docker', 'run', '--rm',
            '-v', f'{host_working_dir}:/repo',
            image,
            'chown', '-R', '1000:1000', '/repo/.git',
        ]
        success, output = self.run_command(cmd, timeout=60)
        if not success:
            return False, f"chown sidecar failed: {output}"
        return True, "ownership fixed via sidecar"

    def _fix_git_permissions(self) -> Tuple[bool, str]:
        """Make sure git can fetch + pull from inside the container.

        Two layers:
          1. Tell git to trust the directory (handles the "dubious ownership"
             complaint when host & container UIDs differ).
          2. Run an alpine sidecar as root to chown the repo back to appuser
             (UID 1000) — heals any drift caused by host-side git ops.
          3. As a fallback when the sidecar can't run (no docker socket,
             etc.), chmod whatever appuser can reach inside .git.
        """
        # Configure git to trust the directory
        self.run_command(['git', 'config', '--global', 'safe.directory', str(self.repo_path)])

        # Primary fix: re-chown via privileged sidecar.
        ok, message = self._fix_git_ownership_via_sidecar()
        if ok:
            return True, message

        # Fallback path — best-effort chmod for files appuser already owns.
        git_dir = self.repo_path / '.git'
        if git_dir.exists():
            try:
                import subprocess
                subprocess.run(['chmod', '-R', 'u+w', str(git_dir)], capture_output=True, check=False)
                subprocess.run(['chmod', '-R', 'g+w', str(git_dir)], capture_output=True, check=False)
            except Exception:
                pass

        return True, f"sidecar chown skipped ({message}); applied chmod fallback"

    def check_for_updates(self) -> Dict[str, any]:
        """Check if updates are available from remote."""
        # Fix git permissions first
        self._fix_git_permissions()

        # Fetch latest from remote
        success, fetch_output = self.run_command(['git', 'fetch', 'origin'], timeout=60)
        if not success:
            # If fetch fails due to permissions, try to fix and retry
            if "Permission denied" in fetch_output or "FETCH_HEAD" in fetch_output:
                # Try to fix permissions on .git directory
                try:
                    git_dir = self.repo_path / '.git'
                    if git_dir.exists():
                        import subprocess
                        # Try to change ownership (may fail, that's okay)
                        subprocess.run(['chmod', '-R', 'u+w', str(git_dir)], capture_output=True)

                        # Retry fetch
                        success, fetch_output = self.run_command(['git', 'fetch', 'origin'], timeout=60)
                except:
                    pass

            if not success:
                return {"error": f"Failed to fetch from remote: {fetch_output}"}

        # Get the branch updates track (handles detached HEAD / env override)
        current_version = self.get_current_version()
        branch = self._get_update_branch()

        # Check for new commits
        success, output = self.run_command(['git', 'log', f'HEAD..origin/{branch}', '--format=%h %s'])

        if not success:
            return {"error": f"Failed to check for updates: {output}"}

        # Parse updates
        updates = []
        if output:
            for line in output.split('\n'):
                if line.strip():
                    parts = line.split(' ', 1)
                    updates.append({
                        "commit_hash": parts[0],
                        "message": parts[1] if len(parts) > 1 else ""
                    })

        return {
            "has_updates": len(updates) > 0,
            "update_count": len(updates),
            "updates": updates,
            "current_version": current_version
        }

    def _has_dirty_tracked_files(self) -> bool:
        """Return True if any tracked file in the working tree differs from
        the index. Untracked files are ignored."""
        # `git diff --quiet` returns 1 when there are unstaged changes.
        # We invoke it via run_command which only checks for returncode == 0.
        success, _ = self.run_command(['git', 'diff', '--quiet'], timeout=15)
        if not success:
            return True
        # Also check staged changes (rare for the updater but be safe).
        success, _ = self.run_command(['git', 'diff', '--cached', '--quiet'], timeout=15)
        return not success

    def _auto_stash(self) -> Optional[str]:
        """Stash any dirty working-tree changes so a pull can proceed.

        Returns a human-readable description of what was stashed (so we can
        surface it to the operator), or None if nothing was stashed.

        We DON'T auto-pop after the pull. If the stash actually contained
        real edits the operator wanted, popping post-pull could conflict
        with the new code in subtle ways. Leaving the stash in place means
        the operator can `git stash list` and `git stash apply` themselves.
        """
        if not self._has_dirty_tracked_files():
            return None

        # What's dirty? Capture short status before stashing for the message.
        ok, status_output = self.run_command(['git', 'status', '--porcelain'], timeout=15)
        files = []
        if ok and status_output:
            for line in status_output.splitlines():
                # Porcelain v1: " M path/to/file" or "M  path/to/file" etc.
                stripped = line[3:].strip() if len(line) > 3 else line.strip()
                if stripped:
                    files.append(stripped)

        from datetime import datetime as _dt
        message = f"system-update auto-stash {_dt.utcnow().isoformat(timespec='seconds')}Z"
        ok, output = self.run_command(['git', 'stash', 'push', '-m', message], timeout=30)
        if not ok:
            # Couldn't stash for some reason — caller will see pull fail.
            return None

        if files:
            preview = ', '.join(files[:5])
            if len(files) > 5:
                preview += f", +{len(files) - 5} more"
            return f"Auto-stashed {len(files)} dirty file(s): {preview}"
        return "Auto-stashed dirty working tree."

    def pull_updates(self) -> Tuple[bool, str]:
        """Bring local repo to origin/<branch> via fetch + hard reset.

        Why hard reset instead of `git pull`:
          - `git pull` runs a merge under the hood. The merge step refuses
            to proceed when the working tree differs from HEAD on any path
            the incoming commit touches. We've seen recurring "phantom diff"
            failures here — `git diff --quiet` reports clean (so our auto
            stash skips), but the merge still complains. Likely a
            line-endings / mtime-cache mismatch only the merge code notices.
          - The system updater's intent is "make this VPS match origin/main",
            not "merge upstream into local edits". Hard reset matches that
            intent and bypasses the whole merge.

        Safety net: we still stash anything dirty BEFORE resetting, so if
        an operator did genuinely edit a file on the host, their changes
        end up in `git stash list` instead of being silently destroyed.
        """
        # Fix git permissions first (chown sidecar + fallback chmod).
        self._fix_git_permissions()

        branch = self._get_update_branch()

        # Belt: stash anything tracked-and-dirty so it's recoverable later.
        stash_msg = self._auto_stash()

        # Fetch the latest objects from origin.
        ok, fetch_output = self.run_command(['git', 'fetch', 'origin', branch], timeout=120)
        if not ok:
            # One retry after another permissions fix, mirroring the old
            # behavior — git fetch is the most common spot to hit perms.
            self._fix_git_permissions()
            ok, fetch_output = self.run_command(['git', 'fetch', 'origin', branch], timeout=120)
            if not ok:
                msg = f"Failed to fetch updates: {fetch_output}"
                if stash_msg:
                    msg += f"\n(Note: {stash_msg} — recover with `git stash list`.)"
                return False, msg

        # Suspenders: hard-reset to the freshly-fetched ref. This bypasses
        # the merge entirely so phantom diffs in the working tree can't
        # block us.
        ok, reset_output = self.run_command(
            ['git', 'reset', '--hard', f'origin/{branch}'], timeout=60,
        )
        if not ok:
            msg = f"Failed to reset to origin/{branch}: {reset_output}"
            if stash_msg:
                msg += f"\n(Note: {stash_msg} — recover with `git stash list`.)"
            return False, msg

        # Compose a friendly message for the UI.
        message = reset_output or "Updated."
        if stash_msg:
            message = f"{message}\n{stash_msg} — recover with `git stash list` / `git stash apply`."
        return True, message

    def restart_containers(self, rebuild: bool = False) -> Tuple[bool, str]:
        """
        Trigger a restart (or rebuild + restart) of the compose project.

        Uses a short-lived **sidecar container** rather than spawning a script
        inside ourselves: when this container restarts, anything running inside
        it dies, so multi-step compose operations are unreliable. A sidecar
        lives in its own PID namespace and survives our restart.

        The sidecar runs `docker compose up -d` (or `up -d --build` when
        rebuild=True), which:
          - picks up compose.yaml changes (new mounts, env vars, etc.) — unlike
            `docker compose restart`, which would miss them
          - is a no-op when nothing has changed
          - rebuilds the image when --build is passed (used after
            requirements.txt changes)
        """
        # Check if docker is available
        available, message = self.check_docker_available()
        if not available:
            return False, f"Cannot restart containers: {message}"

        # Get project information
        project_info = self._get_project_info()
        project_name = project_info['project_name']
        working_dir = project_info['working_dir']
        # Use the full list of files so multi-file setups (e.g. Traefik
        # override via COMPOSE_FILE=compose.yaml:compose.traefik.yaml) keep
        # working through the in-app updater.
        config_files = project_info.get('config_files') or [project_info['config_file']]

        # Sidecar uses our own image, which already has docker + docker compose
        # CLI installed (see Dockerfile). Discover the image tag via inspect on
        # ourselves so we don't have to hardcode it.
        image = self._get_own_image()
        if not image:
            return False, "Could not detect image for sidecar updater"

        # Mount the host project dir at the SAME path inside the sidecar.
        # Compose labels record config_files as ABSOLUTE host paths (e.g.
        # /opt/kbm/compose.yaml); the old /work mount made those -f flags
        # point at nothing inside the sidecar, so `compose up` failed there
        # every time — and the failure was invisible (see log note below).
        # Same-path mounting makes absolute -f paths, relative paths, and
        # --build contexts all resolve identically to the host.
        compose_file_flags = ' '.join(f'-f {f}' for f in config_files)
        compose_args = f"{compose_file_flags} -p {project_name} up -d"
        if rebuild:
            compose_args += " --build"

        # The log must live in a directory that is bind-mounted into the app
        # container, or the UI can never read what the sidecar wrote. The
        # repo root is NOT mounted (only subdirs are) — backups/ is, on
        # every deployment, so the restart log lives there.
        log_in_sidecar = f"{working_dir}/backups/restart_output.log"
        sidecar_script = (
            f"sleep 5; "
            f"cd '{working_dir}'; "
            f"mkdir -p '{working_dir}/backups'; "
            f"echo '=== Sidecar updater started at '$(date)' ===' > {log_in_sidecar}; "
            f"echo 'Project: {project_name}' >> {log_in_sidecar}; "
            f"echo 'Rebuild: {str(rebuild).lower()}' >> {log_in_sidecar}; "
            f"echo 'Command: docker compose {compose_args}' >> {log_in_sidecar}; "
            f"echo '------------------------------------------------------------' >> {log_in_sidecar}; "
            f"if docker compose {compose_args} >> {log_in_sidecar} 2>&1; then "
            f"  echo '=== SUCCESS: sidecar finished at '$(date)' ===' >> {log_in_sidecar}; "
            f"else "
            f"  echo '=== FAILED: docker compose exited non-zero at '$(date)' ===' >> {log_in_sidecar}; "
            f"fi"
        )

        sidecar_name = f"kbm-updater-{int(datetime.now().timestamp())}"
        sidecar_cmd = [
            'docker', 'run', '--rm', '-d',
            '--name', sidecar_name,
            '-v', '/var/run/docker.sock:/var/run/docker.sock',
            '-v', f'{working_dir}:{working_dir}',
            '-w', working_dir,
            image,
            'sh', '-c', sidecar_script,
        ]

        # Seed the log so the UI has something to show before the sidecar wakes up
        try:
            log_dir = self.repo_path / 'backups'
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / 'restart_output.log', 'w') as f:
                f.write(f"=== Sidecar updater scheduled at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"Sidecar name: {sidecar_name}\n")
                f.write(f"Image:        {image}\n")
                f.write(f"Project:      {project_name}\n")
                f.write(f"Working dir:  {working_dir}\n")
                f.write(f"Rebuild:      {rebuild}\n")
                f.write("Sleeping 5s, then running: docker compose " + compose_args + "\n")
                f.write("If this message is still here after a minute, the sidecar\n")
                f.write("never wrote its log — check `docker ps -a` for the sidecar.\n")
                f.write("=" * 60 + "\n\n")
        except Exception:
            pass  # best-effort

        success, output = self.run_command(sidecar_cmd, timeout=15)
        if not success:
            return False, f"Failed to launch sidecar updater: {output}"

        action = "Rebuild + restart" if rebuild else "Restart"
        return True, (
            f"{action} initiated via sidecar container ({sidecar_name}). "
            "The application will reload in 5–30 seconds. "
            "Refresh the page after a moment, or check the restart log below."
        )

    def get_container_status(self) -> List[Dict[str, str]]:
        """Get status of running containers in this project."""
        project_info = self._get_project_info()
        project_name = project_info['project_name']

        # Use docker compose ps to get containers in this project
        success, output = self.run_command([
            'docker', 'compose',
            '-p', project_name,
            'ps', '--format', 'json'
        ])

        if not success:
            # Fallback to docker ps with project filter
            success, output = self.run_command([
                'docker', 'ps', '-a',
                '--filter', f'label=com.docker.compose.project={project_name}',
                '--format', 'json'
            ])

            if not success:
                return [{"error": "Failed to get container status"}]

        # Parse JSON output. Depending on the compose/docker version this is
        # either NDJSON (one object per line) or a single JSON array — handle
        # both, or newer hosts show a bogus "No containers found".
        def _entry(container: dict) -> dict:
            return {
                "name": container.get("Name") or container.get("Names", "unknown"),
                "status": container.get("Status", "unknown"),
                "state": container.get("State", "unknown"),
            }

        containers = []
        stripped = output.strip()
        if stripped.startswith('['):
            try:
                containers = [_entry(c) for c in json.loads(stripped)]
            except Exception:
                containers = []
        if not containers:
            for line in output.split('\n'):
                if line.strip():
                    try:
                        containers.append(_entry(json.loads(line)))
                    except Exception:
                        pass

        return containers if containers else [{"info": "No containers found in project"}]

    def get_logs(self, lines: int = 50) -> str:
        """Get recent container logs from this project."""
        project_info = self._get_project_info()
        container_id = project_info['container_id']

        # Get logs from our own container
        success, output = self.run_command([
            'docker', 'logs', container_id, '--tail', str(lines)
        ])

        if not success:
            return f"Error retrieving logs: {output}"

        return output

    def get_restart_log(self) -> str:
        """Get the restart output log if it exists.

        Lives in backups/ because that directory is bind-mounted in every
        deployment — the sidecar (writing on the host) and this container
        (reading at /app/backups) see the same file. The legacy repo-root
        location is checked as a fallback for pre-2.1 deployments.
        """
        for log_path in (self.repo_path / 'backups' / 'restart_output.log',
                         self.repo_path / 'restart_output.log'):
            try:
                if log_path.exists():
                    with open(log_path, 'r') as f:
                        return f.read()
            except Exception as e:
                return f"Error reading restart log: {str(e)}"
        return "No restart log found. The restart may not have executed yet or no restart has been performed."

    BACKUP_RETENTION = 10  # keep this many backup_* directories, prune older

    def _prune_old_backups(self, backup_dir: Path) -> int:
        """Delete oldest backup_* dirs beyond BACKUP_RETENTION. Returns the
        number pruned. Unbounded backups have filled VPS disks before — a
        full disk then breaks the next git fetch AND the app itself."""
        import shutil
        try:
            backups = sorted(
                (p for p in backup_dir.glob('backup_*') if p.is_dir()),
                key=lambda p: p.name,
            )
            excess = backups[:-self.BACKUP_RETENTION] if len(backups) > self.BACKUP_RETENTION else []
            for old in excess:
                shutil.rmtree(old, ignore_errors=True)
            return len(excess)
        except Exception:
            return 0

    def create_backup(self, backup_dir: str = None) -> Tuple[bool, str]:
        """Create backup of databases.

        SQLite files are copied with sqlite3's online backup API, which is
        safe against concurrent writes — a plain file copy of a live
        database can capture a torn, unusable file. Non-database files are
        copied normally. Old backups beyond BACKUP_RETENTION are pruned.
        """
        if backup_dir is None:
            backup_dir = "/app/backups" if os.path.exists("/app/backups") else str(self.repo_path / "backups")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = Path(backup_dir)
        backup_path = backup_root / f"backup_{timestamp}"

        try:
            import shutil
            import sqlite3

            backup_path.mkdir(parents=True, exist_ok=True)

            def safe_copy(src_file: Path, dest_file: Path):
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                if src_file.suffix == '.db':
                    src_conn = sqlite3.connect(f"file:{src_file}?mode=ro", uri=True)
                    try:
                        dest_conn = sqlite3.connect(str(dest_file))
                        try:
                            src_conn.backup(dest_conn)
                        finally:
                            dest_conn.close()
                    finally:
                        src_conn.close()
                else:
                    shutil.copy2(src_file, dest_file)

            db_dirs = ["master_db", "tenant_dbs", "KBM2_data"]
            backed_up = []

            for db_dir in db_dirs:
                src = self.repo_path / db_dir
                if src.exists() and src.is_dir():
                    for src_file in src.rglob('*'):
                        if src_file.is_file():
                            safe_copy(src_file, backup_path / db_dir / src_file.relative_to(src))
                    backed_up.append(db_dir)

            if not backed_up:
                return False, "No database directories found to backup"

            pruned = self._prune_old_backups(backup_root)
            message = f"Backup created at {backup_path} (backed up: {', '.join(backed_up)})"
            if pruned:
                message += f"; pruned {pruned} old backup(s)"
            return True, message

        except Exception as e:
            return False, f"Failed to create backup: {str(e)}"

    def preflight(self) -> Dict[str, any]:
        """Health-check everything an update depends on, BEFORE updating.

        Returns {'ok': bool, 'checks': [{name, ok, detail}, ...]}. Surfaced
        in the System Updates UI so the operator can see exactly what would
        break instead of finding out mid-update.
        """
        checks: List[Dict[str, any]] = []

        def add(name: str, ok: bool, detail: str):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        # 1) Docker CLI + socket + compose plugin
        ok, msg = self.check_docker_available()
        add("Docker access", ok, msg)

        # 2) Compose project labels (sidecar targets the right project)
        info = self._get_project_info()
        add(
            "Compose project detection",
            bool(info.get('project_name') and info.get('working_dir')),
            f"project={info.get('project_name')!r}, dir={info.get('working_dir')!r}, "
            f"files={info.get('config_files')!r}",
        )

        # 3) Git repo reachable and on a real branch
        version = self.get_current_version()
        add("Git repository", "error" not in version,
            version.get("error") or f"on {version.get('branch')} @ {version.get('commit_hash')}")
        add("Update branch", True, f"updates track origin/{self._get_update_branch()}")

        # 4) Every code package the app imports must be volume-mounted, or
        #    `git pull` inside this container never reaches the host and the
        #    next rebuild crash-loops on the missing package. This exact
        #    failure has happened before — check it automatically now.
        try:
            mounted = set()
            with open('/proc/self/mounts') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) > 1 and parts[1].startswith('/app/'):
                        mounted.add(parts[1][len('/app/'):].split('/')[0])
            code_units = [
                'app_multitenant.py', 'config.py', 'templates', 'static',
                'auth', 'accounts', 'app_admin', 'inventory', 'checkout',
                'main', 'contacts', 'properties', 'audits', 'smartlocks',
                'exports', 'search', 'settings', 'helpcenter', 'utilities',
                'middleware',
            ]
            missing = [u for u in code_units if u not in mounted]
            if os.path.exists('/proc/self/mounts') and mounted:
                add("Code volume mounts", not missing,
                    "all code packages mounted" if not missing
                    else f"NOT mounted (updates won't reach them): {', '.join(missing)} — "
                         "add to compose.yaml volumes and re-run `docker compose up -d`")
            else:
                add("Code volume mounts", True, "not running under docker mounts (skipped)")
        except Exception as e:
            add("Code volume mounts", True, f"check skipped: {e}")

        # 5) Backups dir writable (restart log + db backups land there)
        backups = self.repo_path / 'backups'
        try:
            backups.mkdir(parents=True, exist_ok=True)
            probe = backups / '.preflight_probe'
            probe.write_text('ok')
            probe.unlink()
            add("Backups directory writable", True, str(backups))
        except Exception as e:
            add("Backups directory writable", False, f"{backups}: {e}")

        # 6) Disk space (updates need room for backups + image layers)
        try:
            import shutil as _shutil
            usage = _shutil.disk_usage(str(self.repo_path))
            free_gb = usage.free / (1024 ** 3)
            add("Disk space", free_gb >= 1.0, f"{free_gb:.1f} GB free")
        except Exception as e:
            add("Disk space", True, f"check skipped: {e}")

        return {"ok": all(c["ok"] for c in checks), "checks": checks}

    def perform_update(self, rebuild: bool = False) -> Dict[str, any]:
        """
        Perform full update sequence.

        Args:
            rebuild: If True, rebuild containers (not recommended - increases downtime)

        Returns dict with status of each step.
        """
        results = {
            "backup": {"status": "pending"},
            "pull": {"status": "pending"},
            "restart": {"status": "pending"},
            "overall": {"status": "pending"}
        }

        # Step 1: Check Docker availability
        available, message = self.check_docker_available()
        if not available:
            results["overall"] = {
                "status": "failed",
                "message": f"Docker not available: {message}"
            }
            return results

        # Step 2: Backup databases
        success, message = self.create_backup()
        results["backup"] = {
            "status": "success" if success else "warning",
            "message": message
        }
        # Don't fail if backup fails - continue with update

        # Step 3: Pull updates
        success, message = self.pull_updates()
        results["pull"] = {
            "status": "success" if success else "failed",
            "message": message
        }
        if not success:
            results["overall"] = {
                "status": "failed",
                "message": "Failed to pull updates from git"
            }
            return results

        # Step 4: Restart containers (with optional rebuild for requirements.txt changes)
        success, message = self.restart_containers(rebuild=rebuild)
        results["restart"] = {
            "status": "success" if success else "failed",
            "message": message
        }
        if not success:
            results["overall"] = {
                "status": "failed",
                "message": "Failed to restart containers"
            }
            return results

        results["overall"] = {
            "status": "success",
            "message": "Update completed successfully. Application restarting..."
        }
        return results


# Global instance
update_manager = SystemUpdateManager()
