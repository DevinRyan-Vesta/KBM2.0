"""
System update utilities for managing app deployments.
"""
import subprocess
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class SystemUpdateManager:
    """Manages system updates via git and docker-compose."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def run_command(self, cmd: List[str], timeout: int = 300) -> Tuple[bool, str]:
        """
        Run a shell command and return (success, output).
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def run_git_on_host(self, git_args: List[str], timeout: int = 300) -> Tuple[bool, str]:
        """
        Run git command on the host using docker run with alpine/git.
        This bypasses permission issues with the mounted .git directory.
        """
        # Add safe.directory config to trust the mounted directory
        cmd = [
            "docker", "run", "--rm",
            "-v", "/volume1/KBM/KBM2.0:/git",
            "-w", "/git",
            "alpine/git",
            "-c", "safe.directory=/git"
        ] + git_args

        return self.run_command(cmd, timeout=timeout)

    def get_current_version(self) -> Dict[str, str]:
        """Get current git commit information."""
        success, output = self.run_command(["git", "log", "-1", "--oneline"])
        if not success:
            return {"error": output}

        commit_line = output.strip()
        parts = commit_line.split(" ", 1)
        commit_hash = parts[0] if len(parts) > 0 else "unknown"
        commit_message = parts[1] if len(parts) > 1 else ""

        # Get commit date
        success, date_output = self.run_command([
            "git", "log", "-1", "--format=%ci"
        ])
        commit_date = date_output.strip() if success else "unknown"

        # Get branch name
        success, branch_output = self.run_command([
            "git", "rev-parse", "--abbrev-ref", "HEAD"
        ])
        branch = branch_output.strip() if success else "unknown"

        return {
            "commit_hash": commit_hash,
            "commit_message": commit_message,
            "commit_date": commit_date,
            "branch": branch
        }

    def check_for_updates(self) -> Dict[str, any]:
        """Check if updates are available from remote."""
        # Fetch latest - run on host to avoid permission issues
        success, fetch_output = self.run_git_on_host(["fetch", "origin"])
        if not success:
            return {"error": f"Failed to fetch from remote: {fetch_output}"}

        # Get current branch
        current_version = self.get_current_version()
        branch = current_version.get("branch", "main")

        # Check for new commits
        success, output = self.run_command([
            "git", "log", f"HEAD..origin/{branch}", "--oneline"
        ])

        if not success:
            return {"error": "Failed to check for updates"}

        updates = []
        if output.strip():
            for line in output.strip().split("\n"):
                if line:
                    parts = line.split(" ", 1)
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
        # Run on host to avoid permission issues
        success, output = self.run_git_on_host(["pull", "origin", "main"])
        return success, output

    def rebuild_docker(self) -> Tuple[bool, str]:
        """Rebuild Docker containers by running build on host with full source access."""
        # Run docker compose build from host using modern docker CLI container
        # This gives the build process access to Dockerfile and all source files
        # The build runs on the host volume (/volume1/KBM/KBM2.0) not the container mount
        # Use docker:latest which includes the modern compose plugin
        cmd = [
            "docker", "run", "--rm",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", "/volume1/KBM/KBM2.0:/workspace",
            "-w", "/workspace",
            "docker:latest",
            "compose", "-f", "compose.yaml",
            "-p", "kbm20", "build", "--no-cache", "python-app"
        ]

        success, output = self.run_command(cmd, timeout=600)
        return success, output

    def restart_containers(self) -> Tuple[bool, str]:
        """Restart Docker containers by running commands on host."""
        # Run docker compose restart from host using modern docker CLI container
        # This allows the container to stop itself and have the host restart it
        # Use docker:latest which includes the modern compose plugin
        cmd = [
            "docker", "run", "--rm",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", "/volume1/KBM/KBM2.0:/workspace",
            "-w", "/workspace",
            "docker:latest",
            "compose", "-f", "compose.yaml",
            "-p", "kbm20", "up", "-d", "--no-build", "--force-recreate"
        ]

        success, output = self.run_command(cmd, timeout=300)
        if not success:
            return False, f"Failed to restart containers: {output}"

        return True, "Containers restarted successfully"

    def get_container_status(self) -> List[Dict[str, str]]:
        """Get status of running containers."""
        # Use docker ps instead of docker compose ps to avoid project name issues
        success, output = self.run_command([
            "docker", "ps", "-a", "--format", "json"
        ])

        if not success:
            return [{"error": "Failed to get container status"}]

        # Parse output (one JSON object per line)
        containers = []
        for line in output.strip().split("\n"):
            if line:
                try:
                    import json
                    container = json.loads(line)
                    containers.append({
                        "name": container.get("Names", "unknown"),
                        "status": container.get("Status", "unknown"),
                        "state": container.get("State", "unknown"),
                        "ports": container.get("Ports", "")
                    })
                except:
                    pass

        return containers if containers else [{"info": "No containers running"}]

    def get_logs(self, lines: int = 50) -> str:
        """Get recent container logs."""
        # Get logs from specific containers by name
        success, output = self.run_command([
            "docker", "logs", "python-app", "--tail", str(lines)
        ])
        if not success:
            return f"Error: {output}"

        # Also get nginx logs
        success_nginx, output_nginx = self.run_command([
            "docker", "logs", "nginx-proxy", "--tail", str(lines)
        ])

        if success_nginx:
            return f"=== Python App Logs ===\n{output}\n\n=== Nginx Logs ===\n{output_nginx}"

        return output

    def create_backup(self, backup_dir: str = "/app/backups") -> Tuple[bool, str]:
        """Create backup of databases."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")

        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)

        # Copy databases
        data_dirs = ["master_db", "tenant_dbs"]
        for data_dir in data_dirs:
            src = os.path.join(self.repo_path, data_dir)
            if os.path.exists(src):
                import shutil
                dest = os.path.join(backup_path, data_dir)
                try:
                    shutil.copytree(src, dest)
                except Exception as e:
                    return False, f"Failed to backup {data_dir}: {str(e)}"

        return True, f"Backup created at {backup_path}"

    def perform_update(self, rebuild: bool = False) -> Dict[str, any]:
        """
        Perform full update sequence.
        Returns dict with status of each step.
        """
        results = {
            "backup": {"status": "pending"},
            "pull": {"status": "pending"},
            "rebuild": {"status": "skipped"},
            "restart": {"status": "pending"},
            "overall": {"status": "pending"}
        }

        # Step 1: Backup
        success, message = self.create_backup()
        results["backup"] = {
            "status": "success" if success else "failed",
            "message": message
        }
        if not success:
            results["overall"]["status"] = "failed"
            return results

        # Step 2: Pull updates
        success, message = self.pull_updates()
        results["pull"] = {
            "status": "success" if success else "failed",
            "message": message
        }
        if not success:
            results["overall"]["status"] = "failed"
            return results

        # Step 3: Rebuild (optional)
        if rebuild:
            success, message = self.rebuild_docker()
            results["rebuild"] = {
                "status": "success" if success else "failed",
                "message": message
            }
            if not success:
                results["overall"]["status"] = "failed"
                return results

        # Step 4: Restart containers
        success, message = self.restart_containers()
        results["restart"] = {
            "status": "success" if success else "failed",
            "message": message
        }
        if not success:
            results["overall"]["status"] = "failed"
            return results

        results["overall"]["status"] = "success"
        return results


# Global instance
update_manager = SystemUpdateManager()
