"""Training callbacks — logging, checkpointing, early stopping."""
import time
from typing import Any, Callable, Dict, List, Optional
from utils.logger import get_logger
log = get_logger("CALLBACKS")

try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False


class TrainingCallback:
    def on_epoch_start(self, epoch: int, logs: Dict = None): pass
    def on_epoch_end(self, epoch: int, logs: Dict = None): pass
    def on_train_start(self, logs: Dict = None): pass
    def on_train_end(self, logs: Dict = None): pass


class LoggingCallback(TrainingCallback):
    def on_epoch_end(self, epoch, logs=None):
        if logs:
            loss = logs.get("loss", 0)
            acc = logs.get("accuracy", 0)
            log.info(f"Epoch {epoch}: loss={loss:.4f} acc={acc:.3f}")


class EarlyStoppingCallback(TrainingCallback):
    def __init__(self, patience: int = 5, min_delta: float = 0.001, monitor: str = "loss"):
        self.patience = patience
        self.min_delta = min_delta
        self.monitor = monitor
        self.best_value = float('inf') if "loss" in monitor else float('-inf')
        self.counter = 0
        self.should_stop = False

    def on_epoch_end(self, epoch, logs=None):
        if not logs:
            return
        current = logs.get(self.monitor, self.best_value)
        improved = (current < self.best_value - self.min_delta if "loss" in self.monitor
                    else current > self.best_value + self.min_delta)
        if improved:
            self.best_value = current
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
                log.info(f"Early stopping at epoch {epoch}")


class WandBCallback(TrainingCallback):
    def __init__(self, project: str = "battle-twin", run_name: str = None):
        self.project = project
        self.run_name = run_name
        self._run = None

    def on_train_start(self, logs=None):
        if WANDB_AVAILABLE:
            try:
                self._run = wandb.init(project=self.project, name=self.run_name, config=logs or {})
            except Exception as e:
                log.warning(f"W&B init failed: {e}")

    def on_epoch_end(self, epoch, logs=None):
        if self._run and logs:
            wandb.log(logs, step=epoch)

    def on_train_end(self, logs=None):
        if self._run:
            wandb.finish()


class TimingCallback(TrainingCallback):
    def __init__(self):
        self._start = 0
        self._epoch_start = 0
        self.epoch_times: List[float] = []

    def on_train_start(self, logs=None):
        self._start = time.time()

    def on_epoch_start(self, epoch, logs=None):
        self._epoch_start = time.time()

    def on_epoch_end(self, epoch, logs=None):
        self.epoch_times.append(time.time() - self._epoch_start)

    def on_train_end(self, logs=None):
        total = time.time() - self._start
        log.info(f"Training took {total:.1f}s, avg epoch: {sum(self.epoch_times)/max(len(self.epoch_times),1):.2f}s")


class CallbackRunner:
    """Runs multiple callbacks."""
    def __init__(self, callbacks: List[TrainingCallback] = None):
        self.callbacks = callbacks or []

    def fire(self, event: str, **kwargs):
        for cb in self.callbacks:
            getattr(cb, event, lambda **kw: None)(**kwargs)

    @property
    def should_stop(self):
        return any(getattr(cb, "should_stop", False) for cb in self.callbacks)


if __name__ == "__main__":
    runner = CallbackRunner([LoggingCallback(), TimingCallback(), EarlyStoppingCallback(patience=3)])
    runner.fire("on_train_start")
    for e in range(10):
        runner.fire("on_epoch_start", epoch=e)
        runner.fire("on_epoch_end", epoch=e, logs={"loss": 0.5 - e*0.04, "accuracy": 0.5 + e*0.04})
        if runner.should_stop:
            break
    runner.fire("on_train_end")
    print("callbacks.py OK")
