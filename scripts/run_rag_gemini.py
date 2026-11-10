"""Run CyberHub using a Gemini API key, without a local model runtime."""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8059)
    parser.add_argument("--mode", choices=("demo", "mysql"), default="demo")
    parser.add_argument("--runtime-dir", type=Path, default=root.parent / "cyberhub-ai-runtime")
    args = parser.parse_args(argv)
    if not os.getenv("GEMINI_API_KEY", "").strip():
        parser.error("set GEMINI_API_KEY in .env; create a key at https://aistudio.google.com/api-keys")
    runtime = args.runtime_dir.resolve()
    os.environ.update(CYBERHUB_ASSISTANT_ENABLED="true", CYBERHUB_ASSISTANT_PROVIDER="gemini",
                      CYBERHUB_WEB_MODE=args.mode,
                      CYBERHUB_ASSISTANT_AUDIT_PATH=str(runtime / "assistant" / "audit.sqlite3"))
    from cyberhub_manager.web import create_app
    from cyberhub_manager.ai.errors import ProviderAuthenticationError, ProviderError, ProviderRateLimitError

    print("Gemini API: sending approved knowledge to Google to build the retrieval index.", flush=True)
    print("Questions and authorized context will be sent to Google. Free-tier quotas apply.", flush=True)
    try:
        app = create_app()
    except ProviderAuthenticationError:
        parser.error("Gemini rejected the API key or project permissions; check GEMINI_API_KEY in AI Studio")
    except ProviderRateLimitError:
        parser.error("Gemini quota is exhausted while indexing; check the project's free-tier quota in AI Studio")
    except ProviderError:
        parser.error("Gemini startup failed; check your connection and configured model access in AI Studio")
    print(f"Gemini RAG ready: http://{args.host}:{args.port}/ ; mode={args.mode}", flush=True)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
