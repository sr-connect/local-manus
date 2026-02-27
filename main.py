#!/usr/bin/env python3
"""Entry point — starts the LocalManus server."""
import sys
import uvicorn
import config


def main():
    print(f"""
╔══════════════════════════════════════════╗
║         ⚡  LocalManus  ⚡               ║
║  Open-source local agentic AI system     ║
╠══════════════════════════════════════════╣
║  Provider : {config.LLM_PROVIDER:<30}║
║  Workspace: {str(config.WORKSPACE_DIR)[:30]:<30}║
║  URL      : http://{config.HOST}:{config.PORT:<21}║
╚══════════════════════════════════════════╝
    """)

    uvicorn.run(
        "api.server:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
