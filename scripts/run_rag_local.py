"""Run the authenticated web app with local RAG; no cloud key or business DB needed.

Example: python -m scripts.run_rag_local --host 0.0.0.0 --port 8059
Requires Ollama and downloaded qwen3:8b / qwen3-embedding:0.6b models.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.error import URLError
from urllib.request import build_opener, ProxyHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8059, type=int)
    parser.add_argument("--mode", choices=("demo", "mysql"), default="demo")
    default_runtime = Path(__file__).resolve().parents[2] / "cyberhub-ai-runtime"
    parser.add_argument("--runtime-dir", type=Path, default=default_runtime)
    parser.add_argument("--ollama-bin", default=os.getenv("CYBERHUB_OLLAMA_BIN"))
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    child = None
    opener = build_opener(ProxyHandler({}))
    base = os.getenv("CYBERHUB_OLLAMA_URL", "http://127.0.0.1:11435")
    # Validate before making the inventory request, including environment URLs.
    from cyberhub_manager.ai.ollama import OllamaTransport
    OllamaTransport(base)

    def inventory():
        with opener.open(base + "/api/tags", timeout=3) as response:
            return json.load(response)

    try:
        try:
            models = inventory()
        except (URLError, OSError):
            binary = args.ollama_bin or shutil.which("ollama")
            portable = runtime / "ollama-v0.40.15" / "bin" / "ollama"
            if not binary and portable.is_file():
                binary = str(portable)
            if not binary:
                parser.error("install Ollama or supply --ollama-bin; see docs/RAG_5A_RUNBOOK.md")
            env = os.environ | {
                "OLLAMA_HOST": base, "OLLAMA_MODELS": str(runtime / "models"),
                "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "2",
            }
            log = (runtime / "ollama-server.log").open("ab")
            try:
                child = subprocess.Popen([binary, "serve"], env=env, stdout=log, stderr=log)
            finally:
                log.close()
            for _ in range(40):
                if child.poll() is not None:
                    parser.error("Ollama did not start; inspect the runtime log")
                try:
                    models = inventory()
                    break
                except (URLError, OSError):
                    time.sleep(0.25)
            else:
                parser.error("Ollama startup timed out")
        names = {model["name"] for model in models["models"]}
        required = {os.getenv("CYBERHUB_LLM_MODEL", "qwen3:8b"), os.getenv("CYBERHUB_EMBEDDING_MODEL", "qwen3-embedding:0.6b")}
        if missing := required - names:
            parser.error("download models before starting: " + ", ".join(sorted(missing)) + "; see docs/RAG_5A_RUNBOOK.md")
        os.environ.update(CYBERHUB_ASSISTANT_ENABLED="true", CYBERHUB_WEB_MODE=args.mode,
                          CYBERHUB_ASSISTANT_AUDIT_PATH=str(runtime / "assistant" / "audit.sqlite3"))
        from cyberhub_manager.web import create_app
        print("Loading approved knowledge and warming local models…", flush=True)
        app = create_app()
        print(f"Local RAG ready: http://{args.host}:{args.port}/ ; mode={args.mode}", flush=True)
        app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    finally:
        # Never stop an existing model service owned by another invocation.
        if child is not None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    main()
