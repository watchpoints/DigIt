import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI

def get_search_engines_json(prompt):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://api.siliconflow.cn/v1")
    try:
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1",
            messages=[
                {
                    "role": "system",
                    "content": "You are a friendly assistant here to help you with your search engine classification.你必须给出大部分基于中国用户的相关信息，采用可靠的较为官方的网站链接。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        # output = response.choices[0].text.strip()
        # Parse the output as JSON
        output = response.choices[0].message.content
        index = output.find("{")
        rindex = output.rfind("}")
        output = output[index:rindex+1]
        print(output)
        return json.loads(output)
    except Exception as e:
        print("Failed to get valid JSON from OpenAI:", e)
        return None
def insert_by_category(collection, search_engines_json):
    results = []
    for category, links in search_engines_json.items():
        doc = {
            "category": category,
            "links": links
        }
        result = collection.insert_one(doc)
        results.append(result.inserted_id)
    return results

def main():
    # Load variables from .env
    load_dotenv()

    # Read MongoDB environment variables
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME")
    collection_name = os.getenv("MONGO_COLLECTION_NAME") or "example_collection"
    connection_timeout = int(os.getenv("MONGO_CONNECTION_TIMEOUT_MS", "5000"))
    socket_timeout = int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "10000"))
    max_pool_size = int(os.getenv("MONGO_MAX_POOL_SIZE", "50"))
    retry_writes = os.getenv("MONGO_RETRY_WRITES", "true").lower() in ("true", "1", "yes")

    # Create MongoDB client with configurations from .env
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=connection_timeout,
        socketTimeoutMS=socket_timeout,
        maxPoolSize=max_pool_size,
        retryWrites=retry_writes
    )

    # Test connection to MongoDB
    try:
        client.server_info()
    except Exception as e:
        print("Failed to connect to MongoDB:", e)
        return

    # Select database and collection
    db = client[db_name]
    collection = db[collection_name]
    # Clear the entire collection
    delete_result = collection.delete_many({})
    print(f"Cleared {delete_result.deleted_count} documents from the collection.")

    # Create a prompt for OpenAI to output a JSON containing different categories of search engines
    prompt = (
        "请输出一个有效的json，该json包含以下搜索引擎分类及其对应的网站搜索链接, !!!请注意，请输出网站独有的查询路径，每个分类下的列表中的链接应类似于 'https://google.com/q/'，每个类别至少10条，格式如下：\n"
        "!!!{\n"
        '  "视频": ["https://google.com/q/", "...", ...],\n'
        '  "购物": ["https://google.com/q/", "...", ...],\n'
        '  "音乐": ["https://google.com/q/", "...", ...],\n'
        '  "招聘": ["https://google.com/q/", "...", ...],\n'
        '  "学术": ["https://google.com/q/", "...", ...],\n'
        '  "百科": ["https://google.com/q/", "...", ...],\n'
        '  "数据集": ["https://google.com/q/", "...", ...],\n'
        '  "新闻": ["https://google.com/q/", "...", ...],\n'
        '  "图片": ["https://google.com/q/", "...", ...],\n'
        '  "地图": ["https://google.com/q/", "...", ...],\n'
        '  "翻译": ["https://google.com/q/", "...", ...],\n'
        '  "编程": ["https://google.com/q/", "...", ...],\n'
        '  "社交媒体": ["https://google.com/q/", "...", ...],\n'
        '  "政府": ["https://google.com/q/", "...", ...],\n'
        '  "金融": ["https://google.com/q/", "...", ...],\n'
        '  "医疗": ["https://google.com/q/", "...", ...],\n'
        '  "法律": ["https://google.com/q/", "...", ...],\n'
        '  "专利": ["https://google.com/q/", "...", ...],\n'
        '  "科技": ["https://google.com/q/", "...", ...],\n'
        '  "旅游": ["https://google.com/q/", "...", ...]\n'
        "}!!!\n"
        "请确保输出的内容仅为json格式，不要包含任何多余的文本。"
    )

    # Get JSON data from OpenAI
    search_engines_json = get_search_engines_json(prompt)
    if search_engines_json is None:
        return

    # Insert the JSON data into MongoDB
    # result = collection.insert_one(search_engines_json)
    result = insert_by_category(collection, search_engines_json)
    print("Inserted document ID:", result)

if __name__ == "__main__":
    main()