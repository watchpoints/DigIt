from mofa.kernel.utils.util import load_agent_config
from mcp_llm.chat.session import ChatSession
from mcp_llm.configuration import Configuration
from mcp_llm.mcp_server.server import Server
from mofa.utils.files.dir import get_relative_path
import logging
import asyncio

def initialize():
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
    return ChatSession(servers=servers, inputs=inputs)

async def process():
    chat_session = initialize()
    try:
        await chat_session.initialize()
        result = await chat_session.run("搜索一下3D Gaussian Splatting模型如何展示")
        print(result)
    except Exception as e:
        # 捕获 GeneratorExit 进行清理
       logging.error("fuck")
    finally:
        await chat_session.cleanup_servers()

asyncio.run(process())

print("done")


