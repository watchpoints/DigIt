import logging

import colorama


from mcp_llm.mcp_server.server import Server
from mcp_llm.llm.llm import OpenAIClient
import asyncio
import json
# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

SYSTEM_MESSAGE = (
    """
You are an efficient and reliable assistant with access to the following tools:

{}

Based on the user's query, select the appropriate tool.Without tool to use.return a ["no tool to use"]

IMPORTANT: When you need to use a tool, reply ONLY with a JSON object in the exact format below (without any extra text):
IMPORTANT: 工具名字不能重复，尽可能多用工具
!!你还可以生成多个可用工具的json，就像下面这样,尽可能的使用多种工具生成相应回答
[
    "tool": "tool-1-name",
    "arguments": {{
        "argument-name": "value you prefer"
    }},
    "tool": "tool-2-name",
    "arguments": {{
        "argument-name": "value you prefer"
    }},
    "tool": "tool-3-name",
    "arguments": {{
        "argument-name": "value you prefer"
    }},
    "tool": "tool-4-name",
    "arguments": {{
        "argument-name": "value you prefer"
    }},
    "tool": "tool-5-name",
    "arguments": {{
        "argument-name": "value you prefer"
    }},
    "tool": "tool-6-name",
    "arguments": {{
        "argument-name": "value you prefer"
    }},
    "tool": "tool-7-name",
    "arguments": {{
        "argument-name": "value you prefer"
    }},
    ...
]


After receiving a tool's response, process the information by:
1. Delivering a concise and clear summary.
2. Integrating only the most relevant details into a natural response.
3. Avoiding repetition of raw data.

Use only the tools defined above.
"""
)


class ChatSession:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(self, servers: list[Server], llm_client: OpenAIClient):
        self.servers: list[Server] = servers
        # self.inputs = inputs
        self.llm_client = llm_client
        self.messages = []

    async def cleanup_servers(self) -> None:
        """Clean up all servers properly."""
        print("begin to cleanup servers")
        cleanup_tasks = []
        for server in self.servers:
            # cleanup_tasks.append(asyncio.create_task(server.cleanup()))
            await server.cleanup()
        # if cleanup_tasks:
        #     try:
        #         await asyncio.gather(*cleanup_tasks, return_exceptions=False)
        #     except Exception:
        #         pass

    async def process_llm_response(self, llm_response: str) -> str:
        """Process the LLM response and execute tools if needed.

        Args:
            llm_response: The response from the LLM.

        Returns:
            The result of tool execution or the original response.
        """


        try:
            tool_calls = json.loads(llm_response)
            results = {}
            count = 0
            for tool_call in tool_calls:  # tool_calls 是一个 JSON 数组
                for server in self.servers:
                    tools = await server.list_tools()
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            result = await server.execute_tool(
                                tool_call["tool"], tool_call["arguments"]
                            )
                            print(f"Executed {tool_call['tool']} on {server}")
                        except Exception as e:
                            print(f"Failed to execute {tool_call['tool']} on {server}: {e}")

                        if isinstance(result, dict) and "progress" in result:
                            progress = result["progress"]
                            total = result["total"]
                            percentage = (progress / total) * 100
                            print(
                                f"Progress: {progress}/{total} ({percentage:.1f}%)"
                            )
                        results[f"{tool_call['tool']}_{count}"] = result
                count += 1
            if not results:
                return llm_response
            else:
                return results
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
                    print('begin to initialize:', server.name)
                    await server.initialize()
                except Exception as e:
                    logging.error(f"Failed to initialize server: {e}")
                    logging.error(e.__traceback__.tb_lineno)
                    # await self.cleanup_servers()
                    return False

            all_tools = []
            for server in self.servers:
                tools = await server.list_tools()
                all_tools.extend(tools)

            tools_description = "{"+"\n".join([tool.format_for_llm() for tool in all_tools])+"}"
            system_message = SYSTEM_MESSAGE.format(tools_description)
            # self.inputs['backstory'] = system_message
            self.messages = [{"role": "system", "content": system_message}]
            return True
        except Exception as e:
            logging.error(f"Initialization error: {e}")
            logging.error(e.__traceback__.tb_lineno)
            # await self.cleanup_servers()
            return False
    async def run(self, user_prompt: str) -> str:
        """Run a single prompt through the chat session.

        Args:
            user_prompt: The user's prompt to process.

        Returns:
            str: The final response from the assistant.
        """
        try:
            # self.messages.append({"role": "user", "content": user_prompt})
            # message = "".join(f"'role': '{item['role']}', 'content': '{item['content']}'" for item in self.messages)
            # self.inputs['task'] = user_prompt
            self.messages.append({"role": "user", "content": user_prompt})
            # llm_response = run_dspy_or_crewai_agent(self.inputs)
            llm_response = self.llm_client.get_response(self.messages)
            index = llm_response.find("[")
            rindex = llm_response.find("]")
            llm_response = llm_response[index:rindex + 1]
            print(llm_response)
            # print(llm_response)
            
            result = await self.process_llm_response(llm_response)
            
 
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


                    result = await self.process_llm_response(llm_response[llm_response.find('{'):llm_response.rfind("}")])

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