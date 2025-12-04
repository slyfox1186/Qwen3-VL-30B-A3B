#!/usr/bin/env python3
"""
Qwen3-VL Chat Application Runner

Starts: Frontend (Next.js) → Backend (FastAPI) → vLLM (if needed)
"""

import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

# Paths
ROOT_DIR = Path(__file__).parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"

# Global process tracking for cleanup
_processes: list[subprocess.Popen] = []
_shutting_down = False


def load_env():
    """Load .env file from root directory."""
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Load environment variables
load_env()

# vLLM Configuration (from .env or defaults)
VLLM_MODEL = os.environ.get("VLLM_MODEL", "cpatonn/Qwen3-VL-30B-A3B-Instruct-AWQ-4bit")
VLLM_HOST = os.environ.get("VLLM_HOST", "127.0.0.1")
VLLM_PORT = int(os.environ.get("VLLM_PORT", "8000"))
VLLM_GPU_MEM_UTILIZATION = os.environ.get("VLLM_GPU_MEM_UTILIZATION", "0.93")
VLLM_MAX_MODEL_LEN = os.environ.get("VLLM_MAX_MODEL_LEN", "16384")
VLLM_MAX_NUM_SEQS = os.environ.get("VLLM_MAX_NUM_SEQS", "1")
VLLM_DTYPE = os.environ.get("VLLM_DTYPE", "float16")
VLLM_QUANTIZATION = os.environ.get("VLLM_QUANTIZATION", "compressed-tensors")
VLLM_HEALTH_URL = f"http://{VLLM_HOST}:{VLLM_PORT}/health"

# Backend Configuration (from .env or defaults)
BACKEND_HOST = os.environ.get("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8080"))


def print_header(title: str):
    """Print a formatted section header."""
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def print_status(icon: str, message: str, indent: int = 0):
    """Print a formatted status message."""
    padding = "  " * indent
    print(f"{padding}{icon}  {message}")


def print_separator():
    """Print a visual separator."""
    print()


def wait_for_vllm_status(url: str, timeout_seconds: int = 120) -> bool:
    """Wait for vLLM health endpoint to respond."""
    try:
        import requests
    except ImportError:
        print_status("⚠️", "requests not installed; unable to poll vLLM status")
        time.sleep(5)
        return True

    for attempt in range(timeout_seconds):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        if attempt % 10 == 0 and attempt > 0:
            print_status("⏳", f"Loading model... ({attempt}s)", indent=1)
        time.sleep(1)
    return False


def kill_stale_vllm() -> None:
    """Force kill any existing vLLM processes to free GPU memory."""
    killed_any = False

    # Kill vLLM processes using psutil - use SIGKILL to prevent traceback output
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if "vllm" in cmdline.lower():
                    print_status("🔴", f"Killing stale vLLM (PID: {proc.info['pid']})", indent=1)
                    proc.kill()
                    killed_any = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass

    # Kill GPU memory-holding processes
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line and line != "No running compute apps found":
                    parts = line.split(", ")
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[0].strip())
                            process_name = parts[1].strip()
                            memory_usage = int(parts[2].strip())

                            if ("python" in process_name.lower() or "vllm" in process_name.lower()) and memory_usage > 100:
                                print_status("🔴", f"Killing GPU process (PID: {pid}, {memory_usage}MiB)", indent=1)
                                os.kill(pid, signal.SIGKILL)
                                killed_any = True
                        except (ValueError, ProcessLookupError, PermissionError):
                            continue
    except Exception:
        pass

    if killed_any:
        print_status("⏳", "Waiting for GPU memory release...", indent=1)
        time.sleep(2)


def get_gpu_status() -> str:
    """Get current GPU memory status."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            used, total = result.stdout.strip().split(", ")
            used_gb = float(used) / 1024
            total_gb = float(total) / 1024
            free_gb = total_gb - used_gb
            return f"{used_gb:.1f}GB / {total_gb:.1f}GB ({free_gb:.1f}GB free)"
    except Exception:
        pass
    return "Unknown"


def kill_process_tree(proc: subprocess.Popen, timeout: float = 3.0) -> None:
    """Kill a process and all its children."""
    try:
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)

        # Send SIGTERM to children first
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        # Terminate parent
        parent.terminate()

        # Wait briefly for graceful shutdown
        gone, alive = psutil.wait_procs([parent] + children, timeout=timeout)

        # Force kill any remaining
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass

    except psutil.NoSuchProcess:
        pass
    except Exception:
        # Fallback: just try to kill the main process
        try:
            proc.kill()
        except Exception:
            pass


def graceful_shutdown(signum: int | None = None, frame=None) -> None:
    """Handle graceful shutdown of all processes."""
    global _shutting_down

    if _shutting_down:
        return
    _shutting_down = True

    print()
    print_header("SHUTTING DOWN")

    # Shutdown in reverse order (vLLM last to keep model in VRAM if desired)
    for proc in reversed(_processes):
        if proc and proc.poll() is None:
            try:
                # Identify process for logging
                try:
                    p = psutil.Process(proc.pid)
                    name = p.name()
                except Exception:
                    name = f"PID {proc.pid}"

                print_status("🛑", f"Stopping {name}...")
                kill_process_tree(proc, timeout=3.0)
            except Exception:
                pass

    print()
    print_status("✅", "All services stopped.")
    print()

    # Exit immediately
    os._exit(0)


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Also register with atexit as a fallback
    atexit.register(graceful_shutdown)


def main():
    global _processes

    # Set up signal handlers first
    setup_signal_handlers()

    # Parse arguments
    prod_mode = "--prod" in sys.argv
    no_vllm = "--no-vllm" in sys.argv
    backend_only = "--backend-only" in sys.argv
    frontend_only = "--frontend-only" in sys.argv

    # Clear Next.js cache to prevent stale build issues
    next_cache = FRONTEND_DIR / ".next"
    if next_cache.exists():
        import shutil
        shutil.rmtree(next_cache, ignore_errors=True)

    # Banner
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║           🤖  Qwen3-VL Chat Application                    ║")
    print("╚════════════════════════════════════════════════════════════╝")

    mode = "Production" if prod_mode else "Development"
    print_status("📦", f"Mode: {mode}")
    print_status("📊", f"GPU:  {get_gpu_status()}")

    # Track processes started by this script
    frontend_proc = None
    backend_proc = None
    vllm_proc = None

    try:
        # 1. Start Frontend FIRST (unless backend-only)
        if not backend_only:
            print_header("FRONTEND (Next.js)")

            if not FRONTEND_DIR.exists():
                print_status("❌", f"Directory not found: {FRONTEND_DIR}")
                return 1

            # Install dependencies if needed
            if not (FRONTEND_DIR / "node_modules").exists():
                print_status("📦", "Installing dependencies...")
                subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)

            # Pass environment variables to frontend
            frontend_env = os.environ.copy()

            if prod_mode:
                print_status("🔨", "Building for production...")
                subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True, env=frontend_env)
                frontend_proc = subprocess.Popen(
                    ["npm", "run", "start"],
                    cwd=FRONTEND_DIR,
                    env=frontend_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                frontend_proc = subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=FRONTEND_DIR,
                    env=frontend_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            _processes.append(frontend_proc)
            print_status("✅", "Started on http://localhost:3000")
            time.sleep(2)

        # 2. Start Backend (unless frontend-only)
        if not frontend_only:
            print_header("BACKEND (FastAPI)")

            if not BACKEND_DIR.exists():
                print_status("❌", f"Directory not found: {BACKEND_DIR}")
                return 1

            # Precompile Python bytecode in production mode
            if prod_mode:
                print_status("🔨", "Precompiling Python bytecode...")
                import compileall
                compileall.compile_dir(BACKEND_DIR / "app", quiet=1, optimize=2)

            uvicorn_cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                BACKEND_HOST,
                "--port",
                str(BACKEND_PORT),
            ]

            # Add production optimizations
            if prod_mode:
                uvicorn_cmd.extend(["--workers", "1"])

            backend_proc = subprocess.Popen(
                uvicorn_cmd,
                cwd=BACKEND_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            _processes.append(backend_proc)
            print_status("✅", f"Started on http://{BACKEND_HOST}:{BACKEND_PORT}")
            print_status("📚", f"API Docs: http://{BACKEND_HOST}:{BACKEND_PORT}/docs")
            time.sleep(1)

        # 3. Start vLLM (unless --no-vllm or --frontend-only)
        if not no_vllm and not frontend_only:
            print_header("vLLM SERVER")

            # Check if vLLM is already running
            if wait_for_vllm_status(VLLM_HEALTH_URL, timeout_seconds=3):
                print_status("✅", "Already running (keeping model in VRAM)")
            else:
                print_status("🔄", "Starting server...")
                kill_stale_vllm()

                # Suppress Pydantic warnings and optimize CUDA memory
                env = os.environ.copy()
                env["PYTHONWARNINGS"] = "ignore"
                env["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

                vllm_cmd = [
                    sys.executable,
                    "-m",
                    "vllm.entrypoints.openai.api_server",
                    "--model",
                    VLLM_MODEL,
                    "--host",
                    VLLM_HOST,
                    "--port",
                    str(VLLM_PORT),
                    "--gpu-memory-utilization",
                    VLLM_GPU_MEM_UTILIZATION,
                    "--max-model-len",
                    VLLM_MAX_MODEL_LEN,
                    "--dtype",
                    VLLM_DTYPE,
                    "--quantization",
                    VLLM_QUANTIZATION,
                    "--max-num-seqs",
                    VLLM_MAX_NUM_SEQS,
                    "--enable-prefix-caching",
                    "--enable-chunked-prefill",
                    "--kv-cache-dtype",
                    "fp8",
                    "--enable-auto-tool-choice",
                    "--tool-call-parser",
                    "hermes",
                ]

                vllm_proc = subprocess.Popen(vllm_cmd, env=env)
                _processes.append(vllm_proc)

                print_status("⏳", "Loading model (this may take a few minutes)...")
                print_status("📦", f"Model: {VLLM_MODEL}", indent=1)

                if wait_for_vllm_status(VLLM_HEALTH_URL, timeout_seconds=300):
                    print_status("✅", "Server ready!")
                else:
                    print_status("⚠️", "Server may not be fully ready, continuing...")

        # Summary
        print()
        print("╔════════════════════════════════════════════════════════════╗")
        print("║                    ✅  ALL SERVICES READY                  ║")
        print("╠════════════════════════════════════════════════════════════╣")
        if frontend_proc:
            print("║  🌐  Frontend    http://localhost:3000                     ║")
        if backend_proc:
            print(f"║  🔧  Backend     http://{BACKEND_HOST}:{BACKEND_PORT}                        ║")
        if vllm_proc or (not no_vllm and not frontend_only):
            print(f"║  🤖  vLLM        http://{VLLM_HOST}:{VLLM_PORT}                         ║")
        print("╠════════════════════════════════════════════════════════════╣")
        print("║                   Press Ctrl+C to stop                     ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()

        # Wait for processes
        while True:
            if frontend_proc and frontend_proc.poll() is not None:
                print_status("⚠️", "Frontend process exited")
                break
            if backend_proc and backend_proc.poll() is not None:
                print_status("⚠️", "Backend process exited")
                break
            if vllm_proc and vllm_proc.poll() is not None:
                print_status("⚠️", "vLLM process exited")
                break
            time.sleep(1)

    except KeyboardInterrupt:
        # Signal handler will take care of cleanup
        pass

    except Exception as e:
        print_status("❌", f"Error: {e}")
        graceful_shutdown()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
