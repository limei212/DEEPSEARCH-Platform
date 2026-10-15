from mcp.server.fastmcp import FastMCP

server=FastMCP('Recoverable page error fixture')

@server.tool()
def page(url:str)->str:
    """Return a synthetic page or a recoverable navigation timeout."""
    if url.endswith('/missing'):
        raise ValueError('页面访问超时：synthetic fixture')
    return '已读取虚拟网页：'+url

if __name__=='__main__':server.run(transport='stdio')
