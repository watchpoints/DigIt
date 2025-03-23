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

node = Node()
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

async def process(task):
    global chat_session
    try:
        await chat_session.initialize()
        result = await chat_session.run(task)
        logging.info(result)
    except Exception as e:
        logging.error(f"Error initializing chat session: {e}")
    

async def run_agent():
    global chat_session
    for event in node:
        if event["type"] == "INPUT":
            agent_inputs = ['data','task']  
            if event["id"] in agent_inputs:
                task = event['value'][0].as_py()
                result = await process(task)
                node.send_output("mcp_llm_output", pa.array([json.dumps(result)]), event['metadata'])
        elif event['type'] == 'STOP':
            try:
                await chat_session.cleanup_servers()
            except Exception as e:
                await chat_session.cleanup_servers()
                



    
def main():
    asyncio.run(run_agent())
   

if __name__ == "__main__":
    asyncio.run(main())
