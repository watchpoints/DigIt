import logging

import colorama


from mcp_llm.mcp_server.server import Server
from mofa.run.run_agent import run_dspy_or_crewai_agent
import asyncio
# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

SYSTEM_MESSAGE = (
    """
You are an efficient and reliable assistant with access to the following tools:
{}

Based on the user's query, select the appropriate tool. If no tool is needed, reply directly.

IMPORTANT: When you need to use a tool, reply ONLY with a JSON object in the exact format below (without any extra text):
!!你还可以生成多个可用工具的json，就像下面这样,尽可能的使用多种工具生成相应回答
{{
    "tool": "tool-name",
    "arguments": {{
        "argument-name": value
    }},
    "tool": "tool-name",
    "arguments": {{
        "argument-name": value
    }},
    ...
}},


After receiving a tool's response, process the information by:
1. Delivering a concise and clear summary.
2. Integrating only the most relevant details into a natural response.
3. Avoiding repetition of raw data.

Use only the tools defined above.
"""
)


class ChatSession:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(self, servers: list[Server], inputs) -> None:
        self.servers: list[Server] = servers
        self.inputs = inputs
        self.messages = []
        self.result = ""

    async def cleanup_servers(self) -> None:
        """Clean up all servers properly."""
        cleanup_tasks = []
        for server in self.servers:
            cleanup_tasks.append(asyncio.create_task(server.cleanup()))
        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=False)
            except Exception:
                pass

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
            results = {}
            if "tool" in tool_call and "arguments" in tool_call:
                logging.debug(f"Executing tool: {tool_call['tool']}")
                logging.debug(f"With arguments: {tool_call['arguments']}")

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
                                logging.debug(
                                    f"Progress: {progress}/{total} ({percentage:.1f}%)"
                                )
                            results[tool_call['tool']] = result.content[0].text
                            return results
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
            self.inputs['backstory'] = system_message
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
            self.inputs['task'] = user_prompt
            llm_response = run_dspy_or_crewai_agent(self.inputs)
            logging.info(
                f"\n{colorama.Fore.BLUE}Assistant: {llm_response}"
                f"{colorama.Style.RESET_ALL}"
            )
            print(llm_response)
            input_json = llm_response[llm_response.find('{'):llm_response.rfind("}") + 1]
            tool_result = await self.process_llm_response(input_json)
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
            return tool_result
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