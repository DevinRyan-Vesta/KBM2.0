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
                labels = container_info.get('Labels', {})

                # Extract compose project info from labels
                project_name = labels.get('com.docker.compose.project', 'kbm20')
                working_dir = labels.get('com.docker.compose.project.working_dir', str(self.repo_path))
                config_files = labels.get('com.docker.compose.project.config_files', 'compose.yaml')

                self._project_info = {
                    'project_name': project_name,
                    'working_dir': working_dir,
                    'config_file': config_files.split(',')[0] if config_files else 'compose.yaml',
                    'container_id': hostname
                }
                return self._project_info
        except Exception as e:
            print(f"Warning: Could not auto-detect project info: {e}")

        # Fallback to defaults
        self._project_info = {
            'project_name': 'kbm20',
            'working_dir': str(self.repo_path),
            'config_file': 'compose.yaml',
            'container_id': os.environ.get('HOSTNAME', 'python-app')
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
            output = result.stdout if success else result.stderr
            return success, output.strip()
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout} seconds"
        except Exception as e:
            return False, f"Error executing command: {str(e)}"

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

    def _fix_git_permissions(self) -> Tuple[bool, str]:
        """
        Fix git permissions issues by configuring git to skip permission checks.
        This is needed when .git directory is mounted from host with different ownership.
        """
        # Configure git to trust the directory
        self.run_command(['git', 'config', '--global', 'safe.directory', str(self.repo_path)])

        # Try to fix permissions on critical .git directories
        git_dir = self.repo_path / '.git'
        if git_dir.exists():
            try:
                # Try to make entire .git directory writable recursively
                import subprocess
                subprocess.run(['chmod', '-R', 'u+w', str(git_dir)],
                             capture_output=True,
                             check=False)

                # Also try to make it group writable for good measure
                subprocess.run(['chmod', '-R', 'g+w', str(git_dir)],
                             capture_output=True,
                             check=False)
            except Exception as e:
                # If chmod fails, that's okay - we'll try to continue anyway
                pass

            # Specifically target critical files/dirs that git needs to write to
            critical_paths = [
                git_dir / 'FETCH_HEAD',
                git_dir / 'HEAD',
                git_dir / 'index',
                git_dir / 'objects',
                git_dir / 'refs',
                git_dir / 'logs',
            ]

            for path in critical_paths:
                if path.exists():
                    try:
                        import stat
                        if path.is_dir():
                            # For directories, try to make them and all contents writable
                            subprocess.run(['chmod', '-R', '775', str(path)],
                                         capture_output=True,
                                         check=False)
                        else:
                            # For files, just make them writable
                            path.chmod(0o664)
                    except:
                        pass

        return True, "Git permissions configured"

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

        # Get current branch
        current_version = self.get_current_version()
        branch = current_version.get("branch", "main")

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
        """Pull latest code from git.

        Auto-stashes any dirty working-tree files first so the pull can
        proceed even if some file looks modified to the in-container git
        (typically a line-ending or file-mode phantom diff that doesn't
        appear from the host's git).
        """
        # Fix git permissions first
        self._fix_git_permissions()

        # Pull from current branch
        current_version = self.get_current_version()
        branch = current_version.get("branch", "main")

        # Stash anything dirty so `git pull` doesn't refuse the merge.
        stash_msg = self._auto_stash()

        success, output = self.run_command(['git', 'pull', 'origin', branch], timeout=120)

        if not success:
            # If pull fails due to permissions, try to fix and retry
            if "Permission denied" in output or "FETCH_HEAD" in output:
                try:
                    git_dir = self.repo_path / '.git'
                    if git_dir.exists():
                        import subprocess
                        subprocess.run(['chmod', '-R', 'u+w', str(git_dir)], capture_output=True)

                        # Retry pull
                        success, output = self.run_command(['git', 'pull', 'origin', branch], timeout=120)
                except:
                    pass

            if not success:
                msg = f"Failed to pull updates: {output}"
                if stash_msg:
                    msg += f"\n(Note: {stash_msg} — recover with `git stash list` / `git stash apply`.)"
                return False, msg

        if stash_msg:
            output = f"{output}\n{stash_msg} — recover with `git stash list` / `git stash apply`."
        return True, output

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
        config_file = project_info['config_file']

        # Sidecar uses our own image, which already has docker + docker compose
        # CLI installed (see Dockerfile). Discover the image tag via inspect on
        # ourselves so we don't have to hardcode it.
        success, image = self.run_command(
            ['docker', 'inspect', '-f', '{{.Config.Image}}', project_info['container_id']],
            timeout=5,
        )
        if not success or not image:
            return False, f"Could not detect image for sidecar updater: {image}"

        # Build the command the sidecar runs. The sleep gives our HTTP response
        # time to flush before the project starts churning.
        compose_args = f"-f {config_file} -p {project_name} up -d"
        if rebuild:
            compose_args += " --build"

        log_in_sidecar = "/work/restart_output.log"
        sidecar_script = (
            f"set -e; "
            f"sleep 5; "
            f"cd /work; "
            f"echo '=== Sidecar updater started at '$(date)' ===' > {log_in_sidecar}; "
            f"echo 'Project: {project_name}' >> {log_in_sidecar}; "
            f"echo 'Rebuild: {str(rebuild).lower()}' >> {log_in_sidecar}; "
            f"echo '------------------------------------------------------------' >> {log_in_sidecar}; "
            f"docker compose {compose_args} >> {log_in_sidecar} 2>&1; "
            f"echo '' >> {log_in_sidecar}; "
            f"echo '=== Sidecar finished at '$(date)' ===' >> {log_in_sidecar}"
        )

        sidecar_name = f"kbm-updater-{int(datetime.now().timestamp())}"
        sidecar_cmd = [
            'docker', 'run', '--rm', '-d',
            '--name', sidecar_name,
            '-v', '/var/run/docker.sock:/var/run/docker.sock',
            '-v', f'{working_dir}:/work',
            '-w', '/work',
            image,
            'sh', '-c', sidecar_script,
        ]

        # Seed the log so the UI has something to show before the sidecar wakes up
        try:
            log_path = self.repo_path / 'restart_output.log'
            with open(log_path, 'w') as f:
                f.write(f"=== Sidecar updater scheduled at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"Sidecar name: {sidecar_name}\n")
                f.write(f"Image:        {image}\n")
                f.write(f"Project:      {project_name}\n")
                f.write(f"Working dir:  {working_dir}\n")
                f.write(f"Rebuild:      {rebuild}\n")
                f.write("Sleeping 5s, then running: docker compose " + compose_args + "\n")
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

        # Parse JSON output (one object per line)
        containers = []
        for line in output.split('\n'):
            if line.strip():
                try:
                    container = json.loads(line)
                    containers.append({
                        "name": container.get("Name") or container.get("Names", "unknown"),
                        "status": container.get("Status", "unknown"),
                        "state": container.get("State", "unknown"),
                    })
                except:
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
        """Get the restart output log if it exists."""
        log_path = self.repo_path / 'restart_output.log'
        try:
            if log_path.exists():
                with open(log_path, 'r') as f:
                    return f.read()
            else:
                return "No restart log found. The restart may not have executed yet or no restart has been performed."
        except Exception as e:
            return f"Error reading restart log: {str(e)}"

    def create_backup(self, backup_dir: str = None) -> Tuple[bool, str]:
        """Create backup of databases."""
        if backup_dir is None:
            backup_dir = "/app/backups" if os.path.exists("/app/backups") else str(self.repo_path / "backups")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(backup_dir) / f"backup_{timestamp}"

        try:
            # Create backup directory
            backup_path.mkdir(parents=True, exist_ok=True)

            # Copy database directories
            import shutil

            db_dirs = ["master_db", "tenant_dbs", "KBM2_data"]
            backed_up = []

            for db_dir in db_dirs:
                src = self.repo_path / db_dir
                if src.exists() and src.is_dir():
                    dest = backup_path / db_dir
                    shutil.copytree(src, dest)
                    backed_up.append(db_dir)

            if not backed_up:
                return False, "No database directories found to backup"

            return True, f"Backup created at {backup_path} (backed up: {', '.join(backed_up)})"

        except Exception as e:
            return False, f"Failed to create backup: {str(e)}"

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
