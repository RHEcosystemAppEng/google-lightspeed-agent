"""MCP server configuration and connection management."""

from dataclasses import dataclass
from typing import Literal

from lightspeed_agent.config import get_settings


@dataclass
class MCPServerConfig:
    """Configuration for the Red Hat Lightspeed MCP server."""

    transport_mode: Literal["stdio", "http", "sse"]
    server_url: str | None = None
    read_only: bool = True
    container_image: str = "ghcr.io/redhatinsights/red-hat-lightspeed-mcp:latest"
    timeout: float = 60.0
    sse_read_timeout: float = 300.0

    @classmethod
    def from_settings(cls) -> "MCPServerConfig":
        """Create configuration from application settings."""
        settings = get_settings()
        return cls(
            transport_mode=settings.mcp_transport_mode,
            server_url=settings.mcp_server_url,
            read_only=settings.mcp_read_only,
            timeout=settings.mcp_timeout,
            sse_read_timeout=settings.mcp_sse_read_timeout,
        )

    def get_stdio_command(self) -> str:
        """Get the command for stdio transport."""
        return "podman"

    def get_stdio_args(self) -> list[str]:
        """Get the arguments for stdio transport."""
        args = [
            "run",
            "--interactive",
            "--rm",
            self.container_image,
        ]
        if self.read_only:
            args.append("--readonly")
        return args

    def get_http_url(self) -> str:
        """Get the URL for HTTP transport."""
        return f"{self.server_url}/mcp"
