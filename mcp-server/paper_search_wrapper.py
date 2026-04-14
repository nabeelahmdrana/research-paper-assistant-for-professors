"""Wrapper to launch the paper_search_mcp MCP server.

paper_search_mcp uses relative imports so it cannot be run directly as
``python server.py``.  This wrapper is the correct entry point:

    python mcp-server/paper_search_wrapper.py

The backend's external_search_agent spawns this file via stdio_client.
"""

from paper_search_mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
