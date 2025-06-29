#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
查询到底有没有重复的环境变量跟 环境变量不存在 数据库中的值！！
"""

import json
import os
import sys

# 获取当前文件路径
weizhi = os.path.dirname(os.path.abspath(__file__))

# 用户数据库文件路径
user_json_path = os.path.join(weizhi, 'data', 'user.json')

# 获取环境变量中的 Cookies
def get_cookies():
    cookie_env = os.getenv('XIXUNYUN_COOKIE')
    if cookie_env:
        if '&' in cookie_env:
            cookies = cookie_env.split('&')
        elif '\n' in cookie_env:
            cookies = cookie_env.split('\n')
        else:
            cookies = [cookie_env]
        cookies = list(set(filter(None, cookies)))
        print(f"成功获取 {len(cookies)} 个 Cookie")
        return cookies
    else:
        print("环境变量 'XIXUNYUN_COOKIE' 不存在")
        return []

# 解析 Cookie 并提取用户信息
def parse_cookies(cookies):
    users = []
    for cookie in cookies:
        pairs = [pair.split('=') for pair in cookie.split(',')]
        user = {pair[0].strip(): pair[1].strip() for pair in pairs if len(pair) == 2}
        if 'name' in user and 'account' in user:
            users.append({
                'name': user['name'],
                'account': user['account']
            })
        else:
            print(f"Cookie 格式不完整: {cookie}")
    
    # 使用集合去重时，确保 (name, account) 的组合是唯一的
    unique_users = list({(user['name'], user['account']): user for user in users}.values())
    print(f"解析后得到 {len(unique_users)} 个唯一的当前用户")
    
    # 统计用户出现的次数，找出重复的用户
    from collections import Counter
    user_counts = Counter((user['name'], user['account']) for user in users)
    duplicate_users = [ {'name': name, 'account': account} 
                       for (name, account), count in user_counts.items() if count > 1 ]
    print(f"找到 {len(duplicate_users)} 个重复的用户")
    
    return unique_users, duplicate_users

# 读取 user.json 中的用户
def load_user_json():
    if not os.path.exists(user_json_path):
        print(f"用户数据库文件不存在: {user_json_path}")
        sys.exit(1)
    try:
        with open(user_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        users = data.get('users', [])
        users_len = len(users)
        print(f"用户信息库总共有 {users_len} 个用户")
        return users
    except Exception as e:
        print(f"读取 user.json 失败: {e}")
        sys.exit(1)

# 检查缺失的用户
def find_missing_users(current_users, existing_users):
    existing_set = {(user['name'], user['account']) for user in existing_users}
    missing = []
    for user in current_users:
        if (user['name'], user['account']) not in existing_set:
            missing.append(user)
            print(f"缺失用户: 姓名={user['name']}, 账号={user['account']}")
    print(f"找到 {len(missing)} 个缺失的用户")
    return missing

def main():
    # 获取当前 Cookies
    cookies = get_cookies()
    cookie_count = len(cookies)
    if not cookies:
        print("没有找到任何 Cookies")
        sys.exit(1)
    # 输出 Cookie 的总个数
    print(f"总共有 {cookie_count} 个 Cookie")
    
    # 解析 Cookies，获取唯一用户和重复用户
    current_users, duplicate_users = parse_cookies(cookies)
    current_user_count = len(current_users)
    print(f"解析后得到 {current_user_count} 个唯一的当前用户")
    if not current_users:
        print("没有解析到有效的用户信息")
        sys.exit(1)

    # 加载现有用户
    existing_users = load_user_json()
    existing_user_count = len(existing_users)

    # 查找缺失用户
    missing_users = find_missing_users(current_users, existing_users)
    missing_count = len(missing_users)

    # 输出缺失用户结果
    if missing_users:
        print(f"以下用户不存在于 user.json 中 (总个数: {missing_count}):")
        for user in missing_users:
            user_info = f"姓名: {user['name']}, 账号: {user['account']}"
            print(user_info)
    else:
        print("所有当前用户均存在于 user.json 中。")
    print(f"缺失用户总数: {missing_count}")
    
    # 输出重复的用户
    if duplicate_users:
        print(f"以下用户是重复的 (总个数: {len(duplicate_users)}):")
        for user in duplicate_users:
            user_info = f"姓名: {user['name']}, 账号: {user['account']}"
            print(user_info)
    else:
        print("没有重复的用户。")
        
if __name__ == "__main__":
    main()