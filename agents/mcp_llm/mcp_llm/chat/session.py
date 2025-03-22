import logging

import colorama

import yaml
import json
from mcp_llm.mcp_server.server import Server
from mofa.run.run_agent import run_dspy_or_crewai_agent
# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SYSTEM_MESSAGE = """
    'You are a helpful assistant with access to these tools:\n\n'
    '{tools_description}\n\n'
    'Choose the appropriate tool based on the user's question. '
    'If no tool is needed, reply directly.\n\n'
    'IMPORTANT: When you need to use a tool, you must ONLY respond with '
    'the exact JSON object format below, nothing else:\n'
    '{{\n'
    '    "tool": "tool-name",\n'
    '    "arguments": {{\n'
    '        "argument-name": "value"\n'
    '   }}\n'
    '}}\n\n'
    'After receiving a tool's response:\n'
    '1. Transform the raw data into a natural, conversational response\n'
    '2. Keep responses concise but informative\n'
    '3. Focus on the most relevant information\n'
    '4. Use appropriate context from the user's question\n'
    '5. Avoid simply repeating the raw data\n\n'
    'Please use only the tools that are explicitly defined above'
"""


class ChatSession:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(self, servers: list[Server], inputs) -> None:
        self.servers: list[Server] = servers
        self.inputs = inputs
        self.messages = []
        self.result = ""

    async def cleanup_servers(self) -> None:
        """Clean up all servers properly."""
        for server in self.servers:
            try:
                await server.cleanup()
            except Exception as e:
                logging.warning(f"Warning during cleanup of server {server.name}: {e}")

    async def process_llm_response(self, llm_response: str) -> str:
        """Process the LLM response and execute tools if needed.

        Args:
            llm_response: The response from the LLM.

        Returns:
            The result of tool execution or the original response.
        """
        import json

        try:
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                logging.info(f"Executing tool: {tool_call['tool']}")
                logging.info(f"With arguments: {tool_call['arguments']}")

                for server in self.servers:
                    tools = await server.list_tools()
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            result = await server.execute_tool(
                                tool_call["tool"], tool_call["arguments"]
                            )

                            if isinstance(result, dict) and "progress" in result:
                                progress = result["progress"]
                                total = result["total"]
                                percentage = (progress / total) * 100
                                logging.info(
                                    f"Progress: {progress}/{total} ({percentage:.1f}%)"
                                )

                            return f"Tool execution result: {result}"
                        except Exception as e:
                            error_msg = f"Error executing tool: {str(e)}"
                            logging.error(error_msg)
                            return error_msg

                return f"No server found with tool: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response

    async def initialize(self) -> bool:
        """Initialize servers and prepare the system message.

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        try:
            for server in self.servers:
                try:
                    await server.initialize()
                except Exception as e:
                    logging.error(f"Failed to initialize server: {e}")
                    await self.cleanup_servers()
                    return False

            all_tools = []
            for server in self.servers:
                tools = await server.list_tools()
                all_tools.extend(tools)

            tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])
            system_message = SYSTEM_MESSAGE.format(tools_description=tools_description)
            self.inputs['backstory'] = system_message
            return True
        except Exception as e:
            logging.error(f"Initialization error: {e}")
            await self.cleanup_servers()
            return False
    async def run(self, user_prompt: str) -> str:
        """Run a single prompt through the chat session.

        Args:
            user_prompt: The user's prompt to process.

        Returns:
            str: The final response from the assistant.
        """
        try:
            self.messages.append({"role": "user", "content": user_prompt})
            message = "".join(f"'role': '{item['role']}', 'content': '{item['content']}'" for item in self.messages)
            self.inputs['task'] = message
            llm_response = run_dspy_or_crewai_agent(self.inputs)
            logging.info(
                f"\n{colorama.Fore.BLUE}Assistant: {llm_response}"
                f"{colorama.Style.RESET_ALL}"
            )

            result = await self.process_llm_response(llm_response)

            # self.inputs['task'] = f"""
            #         这是提问的内容
            #         {user_prompt}
            #         以下是工具提供的信息
            #         {result}
            #         请进行总结
            # """
            # final_response = run_dspy_or_crewai_agent(self.inputs)
            # logging.info(
            #     f"\n{colorama.Fore.GREEN}Final response: {final_response}"+f"{colorama.Style.RESET_ALL}")
            # return final_response
            return result
        except Exception as e:
            error_msg = f"Error processing prompt: {str(e)}"
            print(e.__traceback__.tb_lineno)
            logging.error(error_msg)
            return error_msg
        
    async def start(self) -> None:
        """Main chat session handler."""
        try:
            init_success = await self.initialize()
            if not init_success:
                return

            while True:
                try:
                    user_input = input("input sth:")
                    self.messages.append({"role": "user", "content": user_input})

                    llm_response = await self.llm_client.get_response(self.messages)
                    logging.info(
                        f"\n{colorama.Fore.BLUE}Assistant: {llm_response}"
                        f"{colorama.Style.RESET_ALL}"
                    )

                    result = await self.process_llm_response(llm_response)

                    if result != llm_response:
                        self.messages.append(
                            {"role": "assistant", "content": llm_response}
                        )
                        self.messages.append({"role": "system", "content": result})

                        final_response = self.llm_client.get_response(self.messages)
                        logging.info(
                            f"\n{colorama.Fore.GREEN}Final response: {final_response}"
                            f"{colorama.Style.RESET_ALL}"
                        )
                        self.messages.append(
                            {"role": "assistant", "content": final_response}
                        )
                    else:
                        self.messages.append(
                            {"role": "assistant", "content": llm_response}
                        )

                except KeyboardInterrupt:
                    logging.info("process user_input error.")
                    break

        finally:
            await self.cleanup_servers()