from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
from fastmcp import FastMCP
import httpx
import os
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Who-Dat")

BASE_URL = "https://who-dat.as93.net"


def _build_headers(api_key: Optional[str] = None) -> dict:
    """Build authorization headers using provided api_key or AUTH_KEY env var."""
    headers = {}
    key = api_key or os.environ.get("AUTH_KEY", "")
    if key:
        # Strip 'Bearer ' prefix if already present, then re-add it cleanly
        if key.lower().startswith("bearer "):
            key = key[7:]
        headers["Authorization"] = f"Bearer {key}"
    return headers


@mcp.tool()
async def check_health() -> dict:
    """Ping the WHO-DAT API to verify it is online and reachable. Use this before making other requests to confirm the service is available, or when troubleshooting connectivity issues."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{BASE_URL}/ping")
        response.raise_for_status()
        return {"status": "ok", "response": response.text}


@mcp.tool()
async def lookup_domain(domain: str, api_key: Optional[str] = None) -> dict:
    """Retrieve full WHOIS information for a single domain name, including registrar details, registration/expiration dates, nameservers, and registrant contact info. Use this when you need detailed WHOIS data for one specific domain."""
    headers = _build_headers(api_key)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{BASE_URL}/{domain}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def lookup_multiple_domains(domains: List[str], api_key: Optional[str] = None) -> dict:
    """Retrieve WHOIS information for multiple domains in a single concurrent request with a 2-second timeout. Use this when you need to compare registration details across several domains at once, or bulk-check domain ownership/expiration. More efficient than calling lookup_domain repeatedly."""
    headers = _build_headers(api_key)
    domains_param = ",".join(domains)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{BASE_URL}/multi",
            params={"domains": domains_param},
            headers=headers
        )
        response.raise_for_status()
        return response.json()




async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http")

class _FixAcceptHeader:
    """Ensure Accept header includes both types FastMCP requires."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            accept = headers.get(b"accept", b"").decode()
            if "text/event-stream" not in accept:
                new_headers = [(k, v) for k, v in scope["headers"] if k != b"accept"]
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                scope = dict(scope, headers=new_headers)
        await self.app(scope, receive, send)

app = _FixAcceptHeader(Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
