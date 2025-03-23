from mofa.agent_build.base.base_agent import MofaAgent, run_agent
from mofa.kernel.utils.util import load_agent_config
from mcp_llm.chat.session import ChatSession
from mcp_llm.configuration import Configuration
from mcp_llm.mcp_server.server import Server
from mofa.utils.files.dir import get_relative_path
import asyncio
import logging
from dora import Node
import json
import pyarrow as pa
import asyncio_atexit


config = Configuration()
server_config_path = get_relative_path(__file__, sibling_directory_name='mcp_llm/configs', target_file_name='servers_config.json')
server_config = config.load_config(server_config_path)
logging.info(f"Server config: {server_config}")
servers = [
    Server(name, srv_config)
    for name, srv_config in server_config["mcpServers"].items()
]
yaml_path = get_relative_path(__file__, sibling_directory_name='mcp_llm/configs', target_file_name='chat_session.yml')
inputs = load_agent_config(yaml_path)
chat_session = ChatSession(servers=servers, inputs=inputs)

async def run_agent(task):
    try:
        await chat_session.initialize()
        result = await chat_session.run(task)
    except Exception as e:
        asyncio_atexit.register(chat_session.cleanup_servers)
    return result
                
                
def main():
    agent = MofaAgent(agent_name='mcp_llm')
    result = asyncio.run(run_agent(agent.receive_parameter('task')))
    print(result)
    agent.send_output(agent_output_name="mcp_llm_output", agent_result=result)
    
   

if __name__ == "__main__":
    main()
