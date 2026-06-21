"""PyTorch-based training on simulation transcripts -- entirely optional
and decoupled from the simulation runtime (core/runner.py never imports
anything from this package, and nothing here imports core.world). Only
actually calling train_imitation()/build_policy() requires PyTorch
installed (the [finetune] extra); listing/running/replaying simulations
does not.
"""
