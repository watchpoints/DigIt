from mofa.kernel.utils.util import load_agent_config
from mcp_llm.chat.session import ChatSession
from mcp_llm.configuration import Configuration
from mcp_llm.mcp_server.server import Server
from mofa.utils.files.dir import get_relative_path
import logging
import asyncio
import asyncio_atexit


config = Configuration()
server_config_path = get_relative_path(__file__, sibling_directory_name='mcp_llm/configs', target_file_name='servers_config.json')
server_config = config.load_config(server_config_path)
logging.info(f"Server config: {server_config}")
servers = [
    Server(name, srv_config)
    for name, srv_config in server_config["mcpServers"].items()
]
print("mcp load done!")
yaml_path = get_relative_path(__file__, sibling_directory_name='mcp_llm/configs', target_file_name='chat_session.yml')
inputs = load_agent_config(yaml_path)
chat_session = ChatSession(servers=servers, inputs=inputs)


async def process():
    try:
        await chat_session.initialize()
        result = await chat_session.run("告诉我关于苹果的新闻")
    except Exception as e:
        await chat_session.cleanup_servers()
        
    return result

text = asyncio.run(process())

print(text)


