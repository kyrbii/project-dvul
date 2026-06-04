import logging
import os
import ast
import tempfile
import subprocess
import sys
import shutil

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_IMAGE = os.environ.get(
    "PLOT_SANDBOX_IMAGE", "project_dvul_plot_sandbox:latest"
)
DEFAULT_DOCKER_BINARY = os.environ.get("PLOT_SANDBOX_DOCKER_BIN", "docker")
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("PLOT_SANDBOX_TIMEOUT_SECS", "10"))


def find_docker_binary() -> str | None:
    if os.path.isabs(DEFAULT_DOCKER_BINARY) and os.path.exists(DEFAULT_DOCKER_BINARY):
        return DEFAULT_DOCKER_BINARY
    if shutil.which(DEFAULT_DOCKER_BINARY):
        return DEFAULT_DOCKER_BINARY
    for candidate in ["/usr/bin/docker", "/bin/docker", "/usr/local/bin/docker"]:
        if os.path.exists(candidate):
            return candidate
    return None


def execute_plot_code(code: str, df: pd.DataFrame) -> str:
    """
    Executes matplotlib code in a hardened sandbox container.
    Returns the SVG string of the generated plot.
    """
    # Clean code (remove markdown fences if present)
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if len(lines) > 2:
            code = "\n".join(lines[1:-1])
        else:
            code = code.replace("```python", "").replace("```", "").strip()

    # Quick AST check before launching the sandbox container
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return "Sandbox Error: import statements are not allowed."
            if isinstance(node, ast.Attribute) and getattr(node, 'attr', '').startswith('__'):
                return "Sandbox Error: access to dunder attributes is disallowed."
    except Exception as e:
        return f"Sandbox Error: invalid code ({e})"

    docker_bin = find_docker_binary()
    if not docker_bin:
        return (
            "Sandbox Error: docker executable not found. "
            "Install Docker in the backend image or set PLOT_SANDBOX_DOCKER_BIN."
        )

    with tempfile.TemporaryDirectory() as td:
        code_file = os.path.join(td, "code.py")
        csv_file = os.path.join(td, "data.csv")
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)
        df.to_csv(csv_file, index=False)

        docker_cmd = [
            docker_bin,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:exec",
            "--pids-limit",
            "64",
            "--memory",
            "300m",
            "--cpus",
            "0.25",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-v",
            f"{td}:/workspace:ro",
            DEFAULT_SANDBOX_IMAGE,
            "/workspace/code.py",
            "/workspace/data.csv",
        ]

        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            if proc.returncode == 0:
                return proc.stdout
            stderr = proc.stderr.strip()
            if "permission denied" in stderr.lower():
                return (
                    "Sandbox Error: Docker permission denied. "
                    "Ensure /var/run/docker.sock is mounted into the backend container and accessible."
                )
            return f"Sandbox Error: runner failed (code {proc.returncode}): {stderr}"
        except subprocess.TimeoutExpired:
            return "Sandbox Error: execution timed out"
        except Exception as e:
            logger.exception("Failed to run sandbox container")
            return f"Sandbox Error: {e}"
