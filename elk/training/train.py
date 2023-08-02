"""Main training loop."""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
import torch
from simple_parsing import subgroups

from ..metrics import evaluate_preds
from ..run import Run
from ..training.supervised import train_supervised
from ..utils.typing import assert_type
from .ccs_reporter import CcsConfig
from .common import FitterConfig
from .eigen_reporter import EigenFitterConfig


@dataclass
class Elicit(Run):
    """Full specification of a reporter training run."""

    net: FitterConfig = subgroups(
        {"ccs": CcsConfig, "eigen": EigenFitterConfig}, default="eigen"  # type: ignore
    )
    """Config for building the reporter network."""

    supervised: Literal["single", "inlp", "cv"] = "single"
    """Whether to train a supervised classifier, and if so, whether to use
    cross-validation. Defaults to "single", which means to train a single classifier
    on the training data. "cv" means to use cross-validation."""

    def create_models_dir(self, out_dir: Path):
        lr_dir = out_dir / "lr_models"

        lr_dir.mkdir(parents=True, exist_ok=True)

        return lr_dir

    def apply_to_layer(
        self,
        layer: int,
        devices: list[str],
        world_size: int,
    ) -> dict[str, pd.DataFrame]:
        """Train a single reporter on a single layer."""

        self.make_reproducible(seed=self.net.seed + layer)
        device = self.get_device(devices, world_size)

        train_dict = self.prepare_data(device, layer, "train")
        val_dict = self.prepare_data(device, layer, "val")

        (first_train_h, train_gt), *rest = train_dict.values()
        (_, v, d) = first_train_h.shape
        if not all(other_h.shape[-1] == d for other_h, _ in rest):
            raise ValueError("All datasets must have the same hidden state size")

        lr_dir = self.create_models_dir(assert_type(Path, self.out_dir))

        # Fit supervised logistic regression model

        lr_models = train_supervised(
            train_dict,
            device=device,
            mode=self.supervised,
        )
        with open(lr_dir / f"layer_{layer}.pt", "wb") as file:
            torch.save(lr_models, file)

        row_bufs = defaultdict(list)
        for ds_name in val_dict:
            val_h, val_gt = val_dict[ds_name]
            train_h, train_gt = train_dict[ds_name]
            meta = {"dataset": ds_name, "layer": layer}

            for mode in ("none", "full"):
                for i, model in enumerate(lr_models):
                    row_bufs["lr_eval"].append(
                        {
                            **meta,
                            "ensembling": mode,
                            "inlp_iter": i,
                            **evaluate_preds(val_gt, model(val_h), mode).to_dict(),
                        }
                    )

                    row_bufs["train_lr_eval"].append(
                        {
                            **meta,
                            "ensembling": mode,
                            "inlp_iter": i,
                            **evaluate_preds(train_gt, model(train_h), mode).to_dict(),
                        }
                    )

        return {k: pd.DataFrame(v) for k, v in row_bufs.items()}
