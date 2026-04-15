from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
from fastmcp import FastMCP
import httpx
import os
from typing import Optional, List

mcp = FastMCP("Who-Dat")

BASE_URL = os.environ.get("WHO_DAT_BASE_URL", "http://localhost:8080")
AUTH_KEY = os.environ.get("AUTH_KEY", "")


def _build_headers(api_key: Optional[str] = None) -> dict:
    """Build request headers, including Authorization if available."""
    headers = {}
    key = api_key or AUTH_KEY
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


@mcp.tool()
async def get_whois(domain: str, api_key: Optional[str] = None) -> dict:
    """Retrieve WHOIS information for a single domain name. Use this when the user wants to look up registration details, expiry dates, nameservers, registrar, or ownership information for one specific domain."""
    headers = _build_headers(api_key)
    url = f"{BASE_URL}/{domain}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            try:
                return response.json()
            except Exception:
                return {"result": response.text}
        else:
            return {
                "error": f"Request failed with status {response.status_code}",
                "detail": response.text
            }


@mcp.tool()
async def get_whois_multi(domains: List[str], api_key: Optional[str] = None) -> dict:
    """Retrieve WHOIS information for multiple domains in a single request. Use this when the user wants to compare or batch-lookup registration details for several domains at once. Note: has a 2-second server-side timeout, so results for slow lookups may be partial."""
    headers = _build_headers(api_key)
    domains_param = ",".join(domains)
    url = f"{BASE_URL}/multi"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, params={"domains": domains_param})
        if response.status_code == 200:
            try:
                return response.json()
            except Exception:
                return {"result": response.text}
        else:
            return {
                "error": f"Request failed with status {response.status_code}",
                "detail": response.text
            }


@mcp.tool()
async def health_check() -> dict:
    """Check whether the WHOIS API server is alive and reachable. Use this to verify connectivity or diagnose issues before making other requests. Returns 'pong' if the server is healthy."""
    url = f"{BASE_URL}/ping"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return {"status": "healthy", "response": response.text}
            else:
                return {
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "detail": response.text
                }
        except httpx.ConnectError as e:
            return {"status": "unreachable", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": str(e)}




async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http")

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
