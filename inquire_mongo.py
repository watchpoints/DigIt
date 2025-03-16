from pymongo import MongoClient
import pprint
import os
from dotenv import load_dotenv

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
def get_all_categories(collection):
    """
    获取所有可用的分类列表
    
    Args:
        collection: MongoDB collection对象
        
    Returns:
        list: 所有分类名称的列表
    """
    categories = collection.distinct("category")
    return list(categories)
def get_links_by_category(collection, category):
    """
    查询指定分类的链接列表
    
    Args:
        collection: MongoDB collection对象
        category: 要查询的分类名称
        
    Returns:
        list: 该分类下的链接列表，如果未找到则返回None
    """
    result = collection.find_one({"category": category})
    if result:
        return result.get("links")
    return None

def main():
    # 加载 .env 文件中的环境变量
    load_dotenv("/Users/keria/Documents/mofa/DigIt/.env")
    
    # 从环境变量获取MongoDB连接参数
    mongo_uri = os.getenv("MONGO_URI")
    mongo_db = os.getenv("MONGO_DB_NAME")
    mongo_collection = os.getenv("MONGO_COLLECTION_NAME") or "example_collection"
    
    # 确保必要的环境变量存在
    if not all([mongo_uri, mongo_db, mongo_collection]):
        print("请确保 .env 文件中 MONGO_URI、MONGO_DB_NAME 和 MONGO_COLLECTION_NAME 均已设置。")
        return

    # 连接到MongoDB
    client = MongoClient(mongo_uri)
    
    db = client[mongo_db]
    collection = db[mongo_collection]
    
    # 查询全部数据
    documents = collection.find()
    
    # 格式化输出结果
    for doc in documents:
        pprint.pprint(doc)

if __name__ == "__main__":
    main()