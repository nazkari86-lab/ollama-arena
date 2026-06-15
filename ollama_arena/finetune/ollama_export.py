"""Wrap a GGUF as an Ollama Modelfile and register it."""
from __future__ import annotations
import logging, subprocess
from pathlib import Path

log = logging.getLogger("arena.finetune.ollama")


_MODELFILE_TEMPLATE = """\
FROM {gguf_path}
TEMPLATE """ + '"""' + """{{- if .System }}{{ .System }}\n{{ end -}}{{- if .Prompt }}### Instruction:\n{{ .Prompt }}\n\n### Response:\n{{ end -}}{{- .Response -}}""" + '"""' + """
PARAMETER stop "### Instruction:"
PARAMETER stop "### Response:"
PARAMETER temperature 0.2
PARAMETER num_ctx 4096
"""


def build_modelfile(gguf_path: str, out_path: str = "Modelfile") -> str:
    p = Path(out_path)
    p.write_text(_MODELFILE_TEMPLATE.format(gguf_path=str(Path(gguf_path).absolute())))
    return str(p)


def install_to_ollama(modelfile_path: str, model_name: str) -> bool:
    """Run `ollama create <name> -f <modelfile>`."""
    try:
        r = subprocess.run(
            ["ollama", "create", model_name, "-f", modelfile_path],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            log.error(f"[ollama_export] {r.stderr}")
            return False
        log.info(f"[ollama_export] installed model '{model_name}'")
        return True
    except Exception as e:
        log.error(f"[ollama_export] {e}")
        return False
