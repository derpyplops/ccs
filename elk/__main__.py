from .extraction.extraction_main import run as run_extraction
from .extraction.parser import get_extraction_parser
from .training.parser import get_training_parser
from .training.train import train
from argparse import ArgumentParser
from pathlib import Path
import json


def run():
    parser = ArgumentParser(add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "extract",
        help="Extract hidden states from a model.",
        parents=[get_extraction_parser()],
    )
    subparsers.add_parser(
        "train",
        help="Train a set of ELK probes on hidden states from `elk extract`.",
        parents=[get_training_parser()],
    )
    subparsers.add_parser(
        "eval", help="Evaluate a set of ELK probes generated by `elk train`."
    )
    args = parser.parse_args()

    # Default to CUDA iff available
    if args.device is None:
        import torch

        args.device = "cuda" if torch.cuda.is_available() else "cpu"

    if model := getattr(args, "model", None):
        config_path = Path(__file__).parent / "default_config.json"
        with open(config_path, "r") as f:
            default_config = json.load(f)
            model_shortcuts = default_config["model_shortcuts"]

        # Dereference shortcut
        args.model = model_shortcuts.get(model, model)

    for key in list(vars(args).keys()):
        print("{}: {}".format(key, vars(args)[key]))

    # TODO: Implement the rest of the CLI
    if args.command == "extract":
        run_extraction(args)
    elif args.command == "train":
        train(args)
    elif args.command == "eval":
        raise NotImplementedError
    else:
        raise ValueError(f"Unknown command {args.command}")


if __name__ == "__main__":
    run()