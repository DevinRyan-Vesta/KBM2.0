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

    def check_for_updates(self) -> Dict[str, any]:
        """Check if updates are available from remote."""
        # Fetch latest from remote
        success, fetch_output = self.run_command(['git', 'fetch', 'origin'], timeout=60)
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

    def pull_updates(self) -> Tuple[bool, str]:
        """Pull latest code from git."""
        # Pull from current branch
        current_version = self.get_current_version()
        branch = current_version.get("branch", "main")

        success, output = self.run_command(['git', 'pull', 'origin', branch], timeout=120)

        if not success:
            return False, f"Failed to pull updates: {output}"

        return True, output

    def restart_containers(self) -> Tuple[bool, str]:
        """
        Restart Docker containers using docker compose restart.

        Simple and reliable:
        1. Uses the docker socket mounted in the container
        2. Automatically detects project name and working directory
        3. Restarts without rebuilding (code changes are live via volume mounts)
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

        # Build docker compose restart command
        compose_cmd = [
            'docker', 'compose',
            '-f', config_file,
            '-p', project_name,
            'restart'
        ]

        # Create a restart script that will execute after a delay
        restart_script = f"""#!/bin/sh
# Wait to ensure the HTTP response is sent
sleep 3

# Execute the restart
cd {working_dir}
{' '.join(compose_cmd)} > {self.repo_path}/restart_output.log 2>&1

# Log completion
echo "" >> {self.repo_path}/restart_output.log
echo "Restart completed at $(date)" >> {self.repo_path}/restart_output.log
"""

        # Write restart script
        script_path = self.repo_path / 'restart_now.sh'
        try:
            with open(script_path, 'w') as f:
                f.write(restart_script)
            os.chmod(script_path, 0o755)

            # Clear previous log
            log_path = self.repo_path / 'restart_output.log'
            with open(log_path, 'w') as f:
                f.write(f"=== Container Restart Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"Project: {project_name}\n")
                f.write(f"Working Dir: {working_dir}\n")
                f.write(f"Config: {config_file}\n")
                f.write(f"Command: {' '.join(compose_cmd)}\n")
                f.write("=" * 60 + "\n\n")

            # Execute restart script in background
            subprocess.Popen(
                ['/bin/sh', str(script_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            return True, "Container restart initiated. The application will reload in a few seconds. Check restart_output.log for details."

        except Exception as e:
            return False, f"Failed to initiate restart: {str(e)}"

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

        # Step 4: Restart containers
        # Note: We don't rebuild because code changes are live via volume mounts
        # Rebuilding is only needed for dependency changes (requirements.txt)
        success, message = self.restart_containers()
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
