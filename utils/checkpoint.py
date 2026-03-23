"""
Model and state checkpoint manager for BATTLE-TWIN.

Provides:
- PyTorch model checkpointing with metadata
- Battlefield state snapshots
- Auto-save with configurable intervals
- Checkpoint listing and cleanup
"""

import json
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
import numpy as np


CHECKPOINT_DIR = Path("checkpoints")


class CheckpointManager:
    """
    Manages model checkpoints and state snapshots.

    Supports PyTorch model saving/loading, battlefield
    state serialization, and automatic checkpoint rotation.
    """

    def __init__(
        self,
        checkpoint_dir: Optional[Path] = None,
        max_checkpoints: int = 10,
        auto_save_interval_s: int = 300,
    ):
        """
        Args:
            checkpoint_dir: Directory for checkpoints.
            max_checkpoints: Maximum number of checkpoints to retain.
            auto_save_interval_s: Auto-save interval in seconds.
        """
        self.checkpoint_dir = checkpoint_dir or CHECKPOINT_DIR
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self.auto_save_interval_s = auto_save_interval_s
        self._last_save_time: float = 0.0

    def save_model(
        self,
        model: torch.nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
        epoch: int = 0,
        metrics: Optional[Dict[str, float]] = None,
        name: str = "model",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Save a PyTorch model checkpoint.

        Args:
            model: PyTorch model to save.
            optimizer: Optional optimizer state to include.
            epoch: Current training epoch.
            metrics: Optional performance metrics dict.
            name: Checkpoint name prefix.
            extra: Additional data to save.

        Returns:
            Path to saved checkpoint file.
        """
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_epoch{epoch}_{timestamp}.pt"
        filepath = self.checkpoint_dir / filename

        checkpoint_data = {
            "model_state_dict": model.state_dict(),
            "epoch": epoch,
            "timestamp": timestamp,
            "metrics": metrics or {},
        }

        if optimizer is not None:
            checkpoint_data["optimizer_state_dict"] = optimizer.state_dict()

        if extra:
            checkpoint_data["extra"] = extra

        torch.save(checkpoint_data, filepath)

        # Save metadata JSON alongside
        meta_path = filepath.with_suffix(".json")
        meta = {
            "name": name,
            "epoch": epoch,
            "timestamp": timestamp,
            "metrics": metrics or {},
            "model_params": sum(p.numel() for p in model.parameters()),
            "file": filename,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self._rotate_checkpoints(name)
        self._last_save_time = time.time()
        return filepath

    def load_model(
        self,
        model: torch.nn.Module,
        filepath: Optional[Path] = None,
        name: str = "model",
        optimizer: Optional[torch.optim.Optimizer] = None,
        device: str = "cpu",
    ) -> Dict[str, Any]:
        """
        Load a model checkpoint.

        Args:
            model: PyTorch model to load weights into.
            filepath: Specific checkpoint file. If None, loads latest.
            name: Checkpoint name prefix (used to find latest).
            optimizer: Optional optimizer to restore state.
            device: Device to map checkpoint to.

        Returns:
            Dict with epoch, metrics, and any extra data.
        """
        if filepath is None:
            filepath = self.get_latest_checkpoint(name)

        if filepath is None or not filepath.exists():
            raise FileNotFoundError(f"No checkpoint found for '{name}'")

        checkpoint_data = torch.load(filepath, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint_data["model_state_dict"])

        if optimizer is not None and "optimizer_state_dict" in checkpoint_data:
            optimizer.load_state_dict(checkpoint_data["optimizer_state_dict"])

        return {
            "epoch": checkpoint_data.get("epoch", 0),
            "metrics": checkpoint_data.get("metrics", {}),
            "extra": checkpoint_data.get("extra", {}),
        }

    def save_state_snapshot(
        self,
        state_dict: Dict[str, Any],
        name: str = "battlefield_state",
    ) -> Path:
        """
        Save a battlefield state snapshot as JSON.

        Handles numpy arrays by converting to lists.

        Args:
            state_dict: State dictionary to snapshot.
            name: Snapshot name prefix.

        Returns:
            Path to saved snapshot file.
        """
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.json"
        filepath = self.checkpoint_dir / filename

        def _convert(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            if isinstance(obj, (np.int32, np.int64)):
                return int(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2, default=_convert)

        self._rotate_checkpoints(name, extension=".json")
        return filepath

    def load_state_snapshot(
        self,
        filepath: Optional[Path] = None,
        name: str = "battlefield_state",
    ) -> Dict[str, Any]:
        """
        Load a battlefield state snapshot.

        Args:
            filepath: Specific file. If None, loads latest.
            name: Snapshot name prefix.

        Returns:
            State dictionary.
        """
        if filepath is None:
            candidates = sorted(
                self.checkpoint_dir.glob(f"{name}_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                raise FileNotFoundError(f"No snapshot found for '{name}'")
            filepath = candidates[0]

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_latest_checkpoint(self, name: str = "model", extension: str = ".pt") -> Optional[Path]:
        """Get the most recent checkpoint file for a given name."""
        candidates = sorted(
            self.checkpoint_dir.glob(f"{name}_*{extension}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def list_checkpoints(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all checkpoints, optionally filtered by name.

        Returns:
            List of metadata dicts for each checkpoint.
        """
        pattern = f"{name}_*.json" if name else "*.json"
        results = []
        for meta_file in sorted(self.checkpoint_dir.glob(pattern)):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["meta_path"] = str(meta_file)
                results.append(meta)
            except (json.JSONDecodeError, KeyError):
                continue
        return results

    def should_auto_save(self) -> bool:
        """Check if enough time has passed for auto-save."""
        return (time.time() - self._last_save_time) >= self.auto_save_interval_s

    def _rotate_checkpoints(self, name: str, extension: str = ".pt") -> None:
        """Remove oldest checkpoints exceeding max_checkpoints."""
        candidates = sorted(
            self.checkpoint_dir.glob(f"{name}_*{extension}"),
            key=lambda p: p.stat().st_mtime,
        )
        while len(candidates) > self.max_checkpoints:
            oldest = candidates.pop(0)
            oldest.unlink(missing_ok=True)
            # Also remove metadata
            meta = oldest.with_suffix(".json")
            meta.unlink(missing_ok=True)

    def cleanup(self) -> None:
        """Remove all checkpoints."""
        if self.checkpoint_dir.exists():
            shutil.rmtree(self.checkpoint_dir)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    mgr = CheckpointManager(max_checkpoints=3)
    print(f"Checkpoint dir: {mgr.checkpoint_dir}")
    print(f"Checkpoints: {mgr.list_checkpoints()}")
    print(f"Should auto-save: {mgr.should_auto_save()}")

    # Test state snapshot
    test_state = {
        "units": {"alpha": {"lat": 34.25, "lon": -116.68}},
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    snap_path = mgr.save_state_snapshot(test_state, "test_state")
    print(f"Saved snapshot: {snap_path}")
    loaded = mgr.load_state_snapshot(name="test_state")
    print(f"Loaded snapshot keys: {list(loaded.keys())}")
    mgr.cleanup()
    print("checkpoint.py OK")
