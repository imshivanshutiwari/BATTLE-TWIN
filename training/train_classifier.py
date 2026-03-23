"""Terrain classifier training — classifies terrain from DEM+imagery into GO/SLOW-GO/NO-GO."""
import numpy as np
from pathlib import Path
from typing import Dict, Tuple
from utils.logger import get_logger
from utils.checkpoint import CheckpointManager
log = get_logger("TRAIN_CLASS")

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class TerrainClassifierNet(nn.Module if TORCH_AVAILABLE else object):
    """Simple CNN for terrain classification from elevation patches."""

    def __init__(self, n_classes=3):
        if TORCH_AVAILABLE:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1),
            )
            self.classifier = nn.Sequential(nn.Flatten(), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, n_classes))

    def forward(self, x):
        return self.classifier(self.features(x))


class TerrainClassifierTrainer:
    """Trains terrain classifier model."""

    def __init__(self, output_dir="checkpoints/terrain"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ckpt = CheckpointManager(str(self.output_dir))

    def generate_training_data(self, n_samples=500, patch_size=32) -> Tuple:
        """Generate synthetic terrain patches with labels."""
        rng = np.random.default_rng(42)
        patches = []
        labels = []
        for _ in range(n_samples):
            label = rng.choice([0, 1, 2])  # GO, SLOW_GO, NO_GO
            if label == 0:
                patch = rng.uniform(0, 5, (patch_size, patch_size))  # flat
            elif label == 1:
                patch = rng.uniform(10, 25, (patch_size, patch_size))  # moderate
            else:
                patch = rng.uniform(30, 60, (patch_size, patch_size))  # steep
            patches.append(patch)
            labels.append(label)
        return np.array(patches, dtype=np.float32), np.array(labels, dtype=np.int64)

    def train(self, epochs=20, lr=0.001) -> Dict:
        if not TORCH_AVAILABLE:
            log.warning("PyTorch not available — skipping CNN training")
            return {"status": "skipped", "reason": "no_torch"}
        X, y = self.generate_training_data()
        X_tensor = torch.tensor(X).unsqueeze(1)  # (N,1,32,32)
        y_tensor = torch.tensor(y)
        model = TerrainClassifierNet(n_classes=3)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()
        history = []
        for epoch in range(epochs):
            model.train()
            optimizer.zero_grad()
            out = model(X_tensor)
            loss = criterion(out, y_tensor)
            loss.backward()
            optimizer.step()
            acc = (out.argmax(1) == y_tensor).float().mean().item()
            history.append({"epoch": epoch+1, "loss": loss.item(), "accuracy": acc})
            if (epoch+1) % 5 == 0:
                log.info(f"Epoch {epoch+1}/{epochs}: loss={loss.item():.4f} acc={acc:.3f}")
        # Save
        self.ckpt.save({"model_state": model.state_dict(), "history": history}, tag="terrain_classifier")
        return {"final_loss": history[-1]["loss"], "final_accuracy": history[-1]["accuracy"],
                "epochs": epochs}


if __name__ == "__main__":
    trainer = TerrainClassifierTrainer()
    results = trainer.train(epochs=10)
    print(f"Results: {results}")
    print("train_classifier.py OK")
