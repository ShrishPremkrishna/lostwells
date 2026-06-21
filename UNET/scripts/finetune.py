#!/usr/bin/env python3
"""Fine-tune LBNL's pretrained CATALOG U-Net on Appalachian tiles (optional).

Continues training FROM the released `unet_model.h5` (never from scratch), using
the SAME training configuration baked into that checkpoint (read directly from the
released weights' optimizer/loss config):
    loss      = BinaryFocalCrossentropy(gamma=2)   -> sm.losses.BinaryFocalLoss
    optimizer = Adam(learning_rate=5e-5, beta_1=0.9, beta_2=0.999)
    metric    = BinaryIoU(threshold=0.5)           -> sm.metrics.IOUScore + FScore
Matching the original config keeps the fine-tuned weights compatible with the
inference pipeline. A low LR (5e-5) protects the pretrained features.

Inputs: the .npz (image, mask) tiles from make_labels.py.
Run on a GPU host with the env in ../requirements.txt (TF 2.15 + segmentation-
models 1.0.1 + numpy<2), or Colab via the tf_keras shim (see ../README.md).

Usage:
    python finetune.py \
        --tiles ../data/patches/OH ../data/patches/WV \
        --model ../data/lbnl/unet_model.h5 \
        --out   ../checkpoints/unet_appalachia.h5 \
        --epochs 25 --batch 8 --freeze-encoder-epochs 3
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("SM_FRAMEWORK", "tf.keras")
# On Colab/modern TF you must ALSO set this BEFORE importing tensorflow:
#   os.environ["TF_USE_LEGACY_KERAS"] = "1"   (and `pip install tf_keras`)


def load_tiles(dirs: list[str]):
    files = []
    for d in dirs:
        files += sorted(Path(d).glob("*.npz"))
    if not files:
        raise SystemExit(f"[ft] no .npz tiles found in {dirs} (run make_labels.py)")
    X = np.empty((len(files), 256, 256, 3), dtype=np.float32)
    Y = np.empty((len(files), 256, 256, 1), dtype=np.float32)
    groups = []
    for i, f in enumerate(files):
        z = np.load(f)
        X[i] = z["image"].astype("float32")
        Y[i, ..., 0] = z["mask"].astype("float32")
        groups.append(str(z["quad"]) if "quad" in z else f.stem.rsplit("_", 2)[0])
    print(f"[ft] loaded {len(files)} tiles "
          f"({int((Y.sum(axis=(1,2,3))>0).sum())} contain wells)")
    return X, Y, np.asarray(groups)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiles", nargs="+", required=True, help="dirs of .npz tiles")
    ap.add_argument("--model", required=True, help="pretrained unet_model.h5")
    ap.add_argument("--out", default="../checkpoints/unet_appalachia.h5")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--freeze-encoder-epochs", type=int, default=3,
                    help="warm up with the resnet34 encoder frozen for N epochs")
    args = ap.parse_args()

    import segmentation_models as sm
    sm.set_framework("tf.keras")
    from tensorflow import keras

    preprocess = sm.get_preprocessing("resnet34")
    X, Y, groups = load_tiles(args.tiles)
    X = preprocess(X)

    # Split by whole quadrangle. Random tile splitting leaks overlapping pixels
    # into both sets and inflates validation metrics.
    rng = np.random.default_rng(0)
    unique_groups = rng.permutation(np.unique(groups))
    if len(unique_groups) < 2:
        raise SystemExit("[ft] need tiles from at least two quadrangles for a leakage-safe split")
    n_val_groups = max(1, int(round(len(unique_groups) * args.val_frac)))
    n_val_groups = min(n_val_groups, len(unique_groups) - 1)
    val_groups = set(unique_groups[:n_val_groups])
    is_val = np.array([g in val_groups for g in groups])
    Xtr, Ytr, Xva, Yva = X[~is_val], Y[~is_val], X[is_val], Y[is_val]
    print(f"[ft] split by quad: train={len(Xtr)} tiles / "
          f"{len(unique_groups)-n_val_groups} quads; validation={len(Xva)} tiles / "
          f"{n_val_groups} quads")

    model = keras.models.load_model(args.model, compile=False)
    loss = sm.losses.BinaryFocalLoss()                # gamma=2.0 (checkpoint default)
    metrics = [sm.metrics.IOUScore(threshold=0.5), sm.metrics.FScore(threshold=0.5)]

    def compile_(lr):
        model.compile(keras.optimizers.Adam(lr), loss, metrics)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    cbs = [
        keras.callbacks.ModelCheckpoint(args.out, save_best_only=True,
                                        monitor="val_loss", mode="min"),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=4),
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=8,
                                      restore_best_weights=True),
    ]

    # Stage 1: freeze the resnet34 encoder, train the decoder only (protects the
    # pretrained features from large early gradients).
    if args.freeze_encoder_epochs > 0:
        for lyr in model.layers:
            if any(k in lyr.name for k in ("stage", "conv0", "bn_data", "data")):
                lyr.trainable = False
        compile_(args.lr)
        print("[ft] stage 1: encoder frozen (decoder warm-up)")
        model.fit(Xtr, Ytr, validation_data=(Xva, Yva), batch_size=args.batch,
                  epochs=args.freeze_encoder_epochs, callbacks=cbs)
        for lyr in model.layers:
            lyr.trainable = True

    # Stage 2: unfreeze everything, fine-tune at the low LR.
    compile_(args.lr)
    print("[ft] stage 2: all layers trainable")
    model.fit(Xtr, Ytr, validation_data=(Xva, Yva), batch_size=args.batch,
              epochs=args.epochs, callbacks=cbs)
    print(f"[ft] best model saved -> {args.out}")
    print("[ft] run inference with:  python ../unet/infer.py --model "
          f"{args.out} ...")


if __name__ == "__main__":
    main()
