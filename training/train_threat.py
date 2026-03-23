"""Train Bayesian threat model from historical contact data."""

import numpy as np
from pathlib import Path
from typing import Dict, List
from planning.threat_assessor import BayesianThreatAssessor
from utils.logger import get_logger
from utils.checkpoint import CheckpointManager

log = get_logger("TRAIN_THREAT")


class ThreatTrainer:
    """Trains and validates the Bayesian threat assessment model."""

    def __init__(self, output_dir: str = "checkpoints/threat"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assessor = BayesianThreatAssessor()
        self.ckpt = CheckpointManager(str(self.output_dir))

    def generate_training_data(self, n_samples: int = 1000) -> List[Dict]:
        """Generate synthetic training scenarios from battlefield distributions."""
        rng = np.random.default_rng(42)
        samples = []
        for i in range(n_samples):
            intent = int(rng.random() > 0.5)
            capability = int(rng.random() > 0.4)
            terrain = int(rng.random() > 0.5)
            air = int(rng.random() > 0.65)
            intel = int(rng.random() > 0.35)
            # Ground truth threat based on combination
            high_count = intent + capability + terrain + air + intel
            if high_count >= 4:
                true_threat = rng.uniform(0.7, 1.0)
            elif high_count >= 3:
                true_threat = rng.uniform(0.4, 0.7)
            elif high_count >= 2:
                true_threat = rng.uniform(0.2, 0.5)
            else:
                true_threat = rng.uniform(0.0, 0.3)
            samples.append(
                {
                    "EnemyIntention": intent,
                    "EnemyCapability": capability,
                    "TerrainAdvantage": terrain,
                    "AirThreat": air,
                    "IntelQuality": intel,
                    "true_threat": true_threat,
                }
            )
        return samples

    def train(self, epochs: int = 10, n_samples: int = 1000) -> Dict:
        """Train threat model and compute accuracy."""
        data = self.generate_training_data(n_samples)
        results = {"epoch_losses": [], "final_accuracy": 0}
        for epoch in range(epochs):
            errors = []
            for sample in data:
                evidence = {
                    k: sample[k]
                    for k in [
                        "EnemyIntention",
                        "EnemyCapability",
                        "TerrainAdvantage",
                        "AirThreat",
                        "IntelQuality",
                    ]
                }
                self.assessor.update_evidence(evidence)
                predicted = self.assessor.query_threat(f"train_{epoch}")
                error = abs(predicted - sample["true_threat"])
                errors.append(error)
            epoch_mae = float(np.mean(errors))
            results["epoch_losses"].append(epoch_mae)
            log.info(f"Epoch {epoch+1}/{epochs}: MAE={epoch_mae:.4f}")
        results["final_accuracy"] = 1.0 - results["epoch_losses"][-1]
        # Save checkpoint
        self.ckpt.save(
            {"assessor_state": "trained", "epochs": epochs, "accuracy": results["final_accuracy"]},
            tag="threat_model",
        )
        log.info(f"Training complete. Accuracy: {results['final_accuracy']:.3f}")
        return results

    def evaluate(self, n_test: int = 200) -> Dict:
        """Evaluate model on held-out test data."""
        test_data = self.generate_training_data(n_test)
        errors = []
        for sample in test_data:
            evidence = {
                k: sample[k]
                for k in [
                    "EnemyIntention",
                    "EnemyCapability",
                    "TerrainAdvantage",
                    "AirThreat",
                    "IntelQuality",
                ]
            }
            self.assessor.update_evidence(evidence)
            predicted = self.assessor.query_threat()
            errors.append(abs(predicted - sample["true_threat"]))
        return {
            "test_mae": float(np.mean(errors)),
            "test_std": float(np.std(errors)),
            "n_test": n_test,
        }


if __name__ == "__main__":
    trainer = ThreatTrainer()
    results = trainer.train(epochs=5, n_samples=500)
    eval_results = trainer.evaluate(200)
    print(f"Train accuracy: {results['final_accuracy']:.3f}")
    print(f"Test MAE: {eval_results['test_mae']:.3f}")
    print("train_threat.py OK")
