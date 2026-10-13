from mcp.server.fastmcp import FastMCP
import sys

server = FastMCP('DeepSearch test fixture', host='127.0.0.1', port=int(sys.argv[2]) if len(sys.argv)>2 else 8000, stateless_http=True, json_response=True)

@server.tool()
def echo(message: str) -> str:
    """Return the input for protocol verification."""
    return 'echo: '+message

@server.tool()
def unselected() -> str:
    """This tool must not be exposed when it is not selected."""
    return 'not selected'

if __name__ == '__main__':
    server.run(transport='streamable-http' if '--http' in sys.argv else 'stdio')
