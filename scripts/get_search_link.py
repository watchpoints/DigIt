import json
import os
from dora import Node, DoraStatus
import pyarrow as pa
from mofa.kernel.utils.util import load_agent_config, load_dora_inputs_and_task, create_agent_output
from mofa.run.run_agent import run_dspy_agent, run_crewai_agent, run_dspy_or_crewai_agent
from mofa.utils.files.dir import get_relative_path
from transformers import pipeline
from pymongo import MongoClient
from dotenv import load_dotenv

def classify_text(text):
    yaml_path = get_relative_path(__file__, sibling_directory_name='configs', target_file_name='get_search_link.yml')
    inputs = load_agent_config(yaml_path)
    inputs['task'] = text
    result= run_dspy_or_crewai_agent(inputs)
    index = result.find("{")
    rindex = result.rfind("}")
    result = result[index:rindex+1]
    return json.loads(result)

def execute_query(query):
    """
    Connects to MongoDB using the URI from .env, then executes the provided query.

    Args:
        query (dict): The MongoDB query.

    Returns:
        list: A list of documents matching the query.
    
    Raises:
        pymongo.errors.ConnectionError: If connection to MongoDB fails
        pymongo.errors.OperationFailure: If query execution fails
    """
    load_dotenv()

    # MongoDB connection parameters
    MONGO_URI = os.getenv("MONGO_URI")

    # Connection options
    connection_options = {
        "connectTimeoutMS": int(os.getenv("MONGO_CONNECTION_TIMEOUT_MS", 5000)),
        "socketTimeoutMS": int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", 10000)),
        "maxPoolSize": int(os.getenv("MONGO_MAX_POOL_SIZE", 50)),
        "retryWrites": os.getenv("MONGO_RETRY_WRITES", "true").lower() == "true"
    }
    mongo_uri = os.getenv("MONGO_URI")
    mongo_db = os.getenv("MONGO_DB_NAME")
    mongo_collection = os.getenv("MONGO_COLLECTION_NAME") or "example_collection"
    
    
    try:
        client = MongoClient(mongo_uri, **connection_options)
    
        db = client[mongo_db]
        collection = db[mongo_collection]
        
        # Execute query with timeout
        result = list(collection.find(query).max_time_ms(30000))
        return result
    
    except Exception as e:
        print(f"MongoDB Error: {str(e)}")
        raise
    finally:
        client.close()

class Operator:
    def on_event(
        self,
        dora_event,
        send_output,
    ) -> DoraStatus:
        if dora_event["type"] == "INPUT":
            agent_inputs = ['data','task']
            if dora_event["id"] in agent_inputs:
                task = dora_event["value"][0].as_py()
                query = classify_text(task)
                agent_result = execute_query(query)
                send_output("search_link_output", pa.array([create_agent_output(agent_name='get-search-link', agent_result=agent_result,dataflow_status=os.getenv('IS_DATAFLOW_END',True))]),dora_event['metadata'])
                print('reasoner_results:', agent_result)

        return DoraStatus.CONTINUE
    
def main():
    test_search_words = [
        "图像识别最有效的机器学习算法是什么？",
        "请告诉我人工智能在医疗保健领域的伦理影响。",
        "Python中用于数据可视化的最佳库有哪些？",
        "解释深度学习中迁移学习的概念。",
        "寻找学习强化学习的资源。",
        "自然语言处理的当前趋势是什么？",
        "哪里可以找到关于云计算平台的信息？",
        "数据安全的最佳实践是什么？",
        "解释监督学习和无监督学习之间的区别。",
        "查找关于使用TensorFlow构建神经网络的教程。",
        "区块链技术在加密货币之外的应用有哪些？",
        "请告诉我互联网的历史。",
        "查找kitti数据集"
    ]
    for i in test_search_words:
        query = classify_text(i)
        # agent_result = execute_query(query)
        # print(agent_result)
        print(i, ":", query)

if __name__ == "__main__":
    main()