#!/usr/bin/env python3
"""
Redis server management script.

Usage:
    python scripts/redis_server.py start
    python scripts/redis_server.py stop
    python scripts/redis_server.py status
    python scripts/redis_server.py restart
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class RedisServerConfig:
    """Redis server configuration."""

    host: str = "127.0.0.1"
    port: int = 6379
    data_dir: str = "./data/redis"
    log_file: str = "./data/redis/redis.log"
    password: str | None = None
    maxmemory: str = "1gb"
    maxmemory_policy: str = "allkeys-lru"


class RedisServerManager:
    """
    Standalone Redis server lifecycle management.

    Features:
    - Start/stop Redis server process
    - Health monitoring
    - Graceful shutdown
    - Configuration management
    """

    def __init__(self, config: RedisServerConfig) -> None:
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.log_file = Path(config.log_file)
        self.pid_file = self.data_dir / f"redis-{config.port}.pid"

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _build_args(self) -> list:
        """Build redis-server command arguments."""
        args = [
            "redis-server",
            "--daemonize", "yes",
            "--bind", self.config.host,
            "--port", str(self.config.port),
            "--dir", str(self.data_dir.absolute()),
            "--logfile", str(self.log_file.absolute()),
            "--pidfile", str(self.pid_file.absolute()),
            "--maxmemory", self.config.maxmemory,
            "--maxmemory-policy", self.config.maxmemory_policy,
            "--appendonly", "no",  # Disable persistence for chat app
            "--save", "",  # Disable RDB snapshots
        ]

        if self.config.password:
            args.extend(["--requirepass", self.config.password])

        return args

    def _get_pid(self) -> int | None:
        """Get Redis PID from pidfile."""
        if self.pid_file.exists():
            try:
                return int(self.pid_file.read_text().strip())
            except (OSError, ValueError):
                pass
        return None

    def is_running(self) -> bool:
        """Check if Redis is running."""
        pid = self._get_pid()
        if pid:
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                pass
            except PermissionError:
                return True  # Process exists but we can't signal it
        return False

    def start(self) -> bool:
        """Start Redis server."""
        if self.is_running():
            print(f"Redis already running on port {self.config.port}")
            return True

        self._ensure_dirs()

        try:
            result = subprocess.run(
                self._build_args(),
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"Failed to start Redis: {result.stderr}")
                return False

            # Wait for startup
            time.sleep(0.5)

            if self.is_running():
                pid = self._get_pid()
                print(f"Redis started on {self.config.host}:{self.config.port} (PID: {pid})")
                return True
            else:
                print("Redis failed to start. Check logs at:", self.log_file)
                return False

        except FileNotFoundError:
            print("redis-server not found. Please install Redis.")
            return False
        except Exception as e:
            print(f"Error starting Redis: {e}")
            return False

    def stop(self, timeout: float = 30.0) -> bool:
        """Stop Redis server gracefully."""
        if not self.is_running():
            print("Redis is not running")
            return True

        pid = self._get_pid()
        if not pid:
            print("Could not find Redis PID")
            return False

        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to Redis (PID: {pid})")

            # Wait for shutdown
            start = time.time()
            while time.time() - start < timeout:
                if not self.is_running():
                    print("Redis stopped")
                    # Clean up pid file
                    if self.pid_file.exists():
                        self.pid_file.unlink()
                    return True
                time.sleep(0.1)

            # Force kill if still running
            print("Redis did not stop gracefully, sending SIGKILL")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)

            if self.pid_file.exists():
                self.pid_file.unlink()

            print("Redis force killed")
            return True

        except ProcessLookupError:
            print("Redis process not found")
            if self.pid_file.exists():
                self.pid_file.unlink()
            return True
        except Exception as e:
            print(f"Error stopping Redis: {e}")
            return False

    def restart(self) -> bool:
        """Restart Redis server."""
        self.stop()
        time.sleep(1)
        return self.start()

    def status(self) -> dict:
        """Get Redis server status."""
        running = self.is_running()
        pid = self._get_pid() if running else None

        result = {
            "running": running,
            "pid": pid,
            "host": self.config.host,
            "port": self.config.port,
            "data_dir": str(self.data_dir),
        }

        if running:
            try:
                import redis
                r = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    password=self.config.password,
                    decode_responses=True,
                )
                info = r.info()
                result.update({
                    "version": info.get("redis_version"),
                    "uptime_seconds": info.get("uptime_in_seconds"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "used_memory_peak_human": info.get("used_memory_peak_human"),
                })
                r.close()
            except Exception as e:
                result["info_error"] = str(e)

        return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Redis server management for VLM Chat API"
    )
    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "status"],
        help="Command to execute",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("REDIS_HOST", "127.0.0.1"),
        help="Redis host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("REDIS_PORT", "6379")),
        help="Redis port (default: 6379)",
    )
    parser.add_argument(
        "--data-dir",
        default=os.getenv("REDIS_DATA_DIR", "./data/redis"),
        help="Data directory (default: ./data/redis)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("REDIS_PASSWORD"),
        help="Redis password (optional)",
    )

    args = parser.parse_args()

    config = RedisServerConfig(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        log_file=f"{args.data_dir}/redis.log",
        password=args.password or None,
    )

    manager = RedisServerManager(config)

    if args.command == "start":
        success = manager.start()
    elif args.command == "stop":
        success = manager.stop()
    elif args.command == "restart":
        success = manager.restart()
    elif args.command == "status":
        status = manager.status()
        print("\nRedis Server Status:")
        print(f"  Running: {status['running']}")
        if status['running']:
            print(f"  PID: {status.get('pid')}")
            print(f"  Host: {status['host']}:{status['port']}")
            if 'version' in status:
                print(f"  Version: {status['version']}")
                print(f"  Uptime: {status.get('uptime_seconds')}s")
                print(f"  Clients: {status.get('connected_clients')}")
                print(f"  Memory: {status.get('used_memory_human')}")
        print(f"  Data Dir: {status['data_dir']}")
        success = True

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
