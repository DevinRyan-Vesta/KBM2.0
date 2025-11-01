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
        # Fetch latest
        success, _ = self.run_command(["git", "fetch", "origin"])
        if not success:
            return {"error": "Failed to fetch from remote"}

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
        success, output = self.run_command(["git", "pull", "origin", "main"])
        return success, output

    def rebuild_docker(self) -> Tuple[bool, str]:
        """Rebuild Docker containers."""
        success, output = self.run_command([
            "docker", "compose", "build", "--no-cache"
        ], timeout=600)
        return success, output

    def restart_containers(self) -> Tuple[bool, str]:
        """Restart Docker containers."""
        # Stop containers
        success, stop_output = self.run_command(["docker", "compose", "down"])
        if not success:
            return False, f"Failed to stop containers: {stop_output}"

        # Start containers
        success, start_output = self.run_command(["docker", "compose", "up", "-d"])
        if not success:
            return False, f"Failed to start containers: {start_output}"

        return True, "Containers restarted successfully"

    def get_container_status(self) -> List[Dict[str, str]]:
        """Get status of running containers."""
        success, output = self.run_command([
            "docker", "compose", "ps", "--format", "json"
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
                        "name": container.get("Name", "unknown"),
                        "status": container.get("Status", "unknown"),
                        "state": container.get("State", "unknown"),
                        "ports": container.get("Publishers", [])
                    })
                except:
                    pass

        return containers if containers else [{"info": "No containers running"}]

    def get_logs(self, lines: int = 50) -> str:
        """Get recent container logs."""
        success, output = self.run_command([
            "docker", "compose", "logs", "--tail", str(lines)
        ])
        return output if success else f"Error: {output}"

    def create_backup(self, backup_dir: str = "/opt/kbm-backups") -> Tuple[bool, str]:
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
