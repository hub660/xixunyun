#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: xixunyun_sign.py(习讯云打卡任务库-下班任务)
Author: luoye
Date: 2024/10/19 13:00
cron: 00 18 * * *
new Env('习讯云打卡任务库-下班任务');
Update: 2024/10/19
"""

import asyncio
import base64
import calendar
import json
import os
import random
import re
import time
from datetime import datetime, timedelta

import rsa

from usr_qian import Xixunyun_qian
from usr_record import Xixunyun_record
from usr_token import Xixunyun_login

##################################################
weizhi = os.path.dirname(os.path.abspath(__file__))
##################导入配置文件#####################
try:
    with open(f'{weizhi}{os.sep}data{os.sep}config.json', 'r',encoding="utf-8") as file:
        data = json.load(file)
        config = data['config'][0]
        version_config = config['version']
        from_config = config['from']
        platform_config = config['platform']
        pushMessageReduction = config['pushMessageReduction']
        key_config = r"{}".format(config['key'])
except:
    print("配置文件错误，结束运行 | 配置文件：config.json")
    os._exit()
# 加载通知服务
def load_send():
    import sys
    cur_path = os.path.abspath(os.path.dirname(__file__))
    sys.path.append(cur_path)
    if os.path.exists(cur_path + "/sendNotify.py"):
        try:
            from sendNotify import send
            return send
        except Exception as e:
            #print(f"加载通知服务失败：{e}")
            return None
    else:
        print("加载通知服务失败")
        return None
###########################################

def ageing(moth):
    if not re.match(r'^\d{4}-\d{2}(-\d{2})?:\d{4}-\d{2}(-\d{2})?$', moth):
        print("用户的时间范围格式不正确，应为'年-月:年-月' 或 '年-月-日:年-月-日' 或 '年-月:年-月-日'。")
        return False
    start_date_str, end_date_str = moth.split(':')
    try:
        # 尝试解析开始日期
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
            start_date = datetime.strptime(start_date_str, '%Y-%m')
            start_date = start_date.replace(day=1) # 将开始日期设置为当月的第一天
        # 尝试解析结束日期
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            end_date = datetime.strptime(end_date_str, '%Y-%m')
            end_date = end_date.replace(day=calendar.monthrange(end_date.year, end_date.month)[1])
    except ValueError:
        print("用户时间范围中的日期部分格式不正确，应为'年-月' 或 '年-月-日'。")
        return False
    current_date = datetime.now()
    if isinstance(end_date, datetime):
        end_date = end_date.replace(hour=23, minute=59, second=59)
    if start_date <= current_date <= end_date:
        print("【用户身份校验】用户在有效期内[激活]【√】")
        return True
    elif start_date > end_date:
        print("【用户身份校验】开始日期大于结束日期，请检查时间范围[跳过]【X】")
        return False
    else:
        print("【用户身份校验】用户不在有效期内[跳过]【X】")
        return False

def encrypt(latitude, longitude):
    #纬度，经度
    # 要加密的经纬度数据
    # 设置公钥
    public_key_data = f'''-----BEGIN PUBLIC KEY-----
    {key_config}
    -----END PUBLIC KEY-----'''
    public_key = rsa.PublicKey.load_pkcs1_openssl_pem(public_key_data)
    # 分别加密经度和纬度
    encrypted_longitude = rsa.encrypt(str(longitude).encode(), public_key)
    encrypted_latitude = rsa.encrypt(str(latitude).encode(), public_key)
    # 将加密后的数据转换为base64编码
    encrypted_longitude_base64 = base64.b64encode(encrypted_longitude)
    encrypted_latitude_base64 = base64.b64encode(encrypted_latitude)
    return encrypted_longitude_base64.decode(),encrypted_latitude_base64.decode()

def extract_province_city(address):
    #返回 省名 市名
    pattern = re.compile(r'(\w+省|\w+市|\w+特别行政区)(\w*市)?')
    match = pattern.search(address)
    if match:
        province, city = match.groups()
        if '市' in province or '特别行政区' in province:
            return province, province
        if city is None:
            return province, None
        return province, city
    else:
        return None, None

def parse_time(time_str):
    # 将字符串 "HH:MM" 解析为小时和分钟
    time_parts = time_str.split(":")
    return int(time_parts[0]), int(time_parts[1])

async def qiandao(token, school_id, province, city, address, address_name, latitude, longitude, remark, after_word_time, name, account):
    rnd = random.SystemRandom()
    delay_min = 0  # 默认延迟分钟数
    additional_delay_sec = 0  # 额外随机延迟秒数
    additional_delay_probability = 0.55  # 触发额外秒数延迟的概率（55%）

    # 解析 after_word_time
    if isinstance(after_word_time, int):
        if after_word_time == 0:
            delay_min = 0
        else:
            print("【签到系统】用户延迟参数 为非零数值但不是范围格式，直接进行签到")
    elif isinstance(after_word_time, str):
        if '-' in after_word_time:
            parts = after_word_time.split('-')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                min_val, max_val = int(parts[0]), int(parts[1])
                if min_val > max_val:
                    print("【控制台】用户延迟参数 格式不规范（最小值大于最大值），直接进行签到")
                else:
                    # 这里假设延迟签到的概率为55%，可以根据需要调整
                    if rnd.random() < 0.55:
                        delay_min = rnd.randint(min_val, max_val)
                        #print(f"【签到系统】{name} {account} 触发延迟机制，延迟{delay_min}分钟后签到")
            else:
                print("【控制台】用户延迟参数 格式不规范（不是两个数字用-分隔），直接进行签到")
        elif after_word_time.isdigit():
            delay_min = int(after_word_time)
            print(f"【签到系统】{name} {account} 设置固定延迟{delay_min}分钟后签到")
        else:
            print("【控制台】用户延迟参数 格式不规范，直接进行签到")
    else:
        print("【控制台】用户延迟参数 类型不支持，直接进行签到")

    # 生成额外的秒级延迟
    if rnd.random() < additional_delay_probability:
        additional_delay_sec = rnd.randint(1, 60)
        #print(f"【签到系统】{name} {account} 增加额外随机延迟{additional_delay_sec}秒")

    total_delay = delay_min * 60 + additional_delay_sec  # 总延迟时间（秒）

    try:
        if total_delay > 0:
            print(f"【签到系统】{name} {account} 将在{delay_min}分钟{additional_delay_sec}秒后执行签到")
            await asyncio.sleep(total_delay)
        else:
            print(f"【签到系统】{name} {account} 直接进行签到")

        latitude_bs4, longitude_bs4 = encrypt(latitude, longitude)
        qiandao_result = Xixunyun_qian(token, school_id, province, city, address, address_name, latitude_bs4, longitude_bs4, remark).get_qiandao()
        print(qiandao_result)

        if qiandao_result[0] == "error":
            if qiandao_result[1] == "请求超时，可能是网络问题":
                return "请求超时，可能是网络问题"
            elif qiandao_result[1] == "请求异常":
                return "请求异常"

        if qiandao_result[0] == True:
            qiandao_days = qiandao_result[1]
            print(f"{name} {account} 签到成功，连续签到 {qiandao_days} 天")
            return True, f"{name} {account} 成功", qiandao_days
        elif qiandao_result[0] == False:
            qiandao_error = qiandao_result[1]
            return False, f"{name} {account} 失败", qiandao_error

    except Exception as e:
        print(f"{name} {account} \n签到出问题了: {e}")
        return "ERROR", f"{name} {account} 失败", f"签到出问题了: {e}"

async def main():
    qiandao_TF = []
    # 获取用户列表
    users = user_data['users']
    users_len = len(users)
    bot_message = f"任务库执行报告\n数据库总用户：{users_len} 个\n"
    start_fenpei_time = time.time()
    bot_message_after_word = ""
    bot_message_error_login = 0
    bot_message_sure = 0
    bot_message_error = 0
    bot_message_surr_max = 0
    bot_message_sure_dontword = 0
    bot_message_sure_budaka = 0
    bot_message_error_surr_time = 0
    print(f"总用户：{users_len},当前指定打卡模式（下班）")

    print("-----------------------------")
    # 遍历每个用户
    shushushu = 0
    for user in users:
        name = user['name']
        school_id = user['school_id']
        token = user['token']
        moth = user['moth']
        mothxiu = user['mothxiu']
        word_long = user['word_long']
        word_latit = user['word_latit']
        word_name = user['word_name']
        word_name_guishu = user['word_name_guishu']
        home_long = user['home_long']
        home_latit = user['home_latit']
        home_name = user['home_name']
        home_name_guishu = user['home_name_guishu']
        model = user['model']
        phone = user['phone']
        account = user['account']
        time_user = user['time']
        jiuxu = user['jiuxu']
        password = user['password']
        mac = user['mac']
        after_word = user['after_word']

        shushushu+=1
        print(f"\n-------- 当前用户 姓名：{name} 手机号：{phone} 学号：{account}   -------------本次序列第【{shushushu}】位用户-------------\n") 
        if jiuxu == True:
            pass
        else:
            print("配置信息失效 跳过")
            continue
        #判断是否存在于有效期中
        ageing_TF = ageing(moth)
        try:
            if ageing_TF is False:
                continue
            elif ageing_TF is True:
                user_record_login = Xixunyun_record(token,school_id).get_record()
                if len(user_record_login) > 3:
                    user_record_errow = user_record_login
                    if user_record_errow == "请求异常":
                        print("因为请求异常，用户Token更新失败")
                        continue
                    elif user_record_errow == "请求超时，可能是网络问题":
                        print("----------------出现请求超时情况，终止所有任务---------------------")
                        break 
                    elif user_record_errow['code'] == 40511 and user_record_errow['message'] == '登录超时' or user_record_errow['code'] == "40511" and user_record_errow['message'] == '登录超时' or user_record_errow['code'] == 40510:
                        print("【补救措施-登录超时】出现登录超时情况，重新获得用户Token")
                        usr_token_insp = Xixunyun_login(school_id, password, account, model, mac).get_token()
                        usr_token_insp_len = len(usr_token_insp)
                        if usr_token_insp_len > 7:
                            user_name, school_id, token, user_number, bind_phone, user_id, class_name, entrance_year, graduation_year = usr_token_insp
                            user_record_login = Xixunyun_record(token,school_id).get_record()
                            print(f"【补救措施-登录超时】成功获得用户Token: {token}")
                            if len(user_record_login) > 3:
                                user_record_errow = user_record_login
                                print("【补救措施-登录超时】错误[record]回复，用户[record]查询失败",user_record_errow)
                                bbot_message_error_login += 1
                                bot_message_after_word = (f"{name} {account} 登录失败")
                                print(f"{name} {account} 登录失败")
                                continue
                        else:
                            print(f"【补救措施-登录超时】失败，无法获得用户 Token")
                            bot_message_error_login += 1
                            print(f"{name} {account} 登录失败")
                            bot_message_after_word = (f"{name} {account} 登录失败")
                            continue
                    else:
                        print("错误[record]回复，用户[record]查询失败",user_record_errow)
                        bot_message_error_login += 1
                        print(f"{name} {account} 登录失败")
                        bot_message_after_word = (f"{name} {account} 登录失败")
                        continue
                user_record = Xixunyun_record(token,school_id).get_record_aftr_work()
                print(user_record)
                if user_record != "今天没有签到记录":
                    today_date,today_word = user_record
                else:
                    bot_message_after_word += (f"{name} {account} 今日无上班,\n")
                    print("【控制台】未查询到用户今天的上班信息,不给予下班操作")
                    bot_message_sure_dontword += 1
                    continue
                #after_word 延迟打卡 （模拟真实用户非到点下班） 参数   0 即不需要 延迟打卡功能 到点直接打卡 ，-1 不需要打下班卡， 预期参数  最小数值-最大数值 （分钟）
                if after_word != "-1":
                    if today_date == datetime.now().strftime("%Y-%m-%d"):
                        if today_word == "上班":
                            print("【控制台】用户今天打过上班卡,执行下班操作")
                            #获取用户的地址
                            address = word_name_guishu
                            address_name = word_name
                            province,city = extract_province_city(address)
                            latitude = word_latit
                            longitude = word_long
                            if after_word == "0":
                                after_word_time = 0
                                print("【控制台】用户的延迟签到参数为0,执行直接签到")
                            else:
                                after_word_time = after_word
                                print(f"【控制台】用户的延迟签到参数为{after_word_time},进入随机定时任务")
                            remark = "8"
                            print(f"【创造计划任务】\n姓名：{name},地址：{address},纬度：{latitude},经度：{longitude},延迟签到定时任务：{after_word_time},签到 模式 [下班]")
                            task = asyncio.create_task(qiandao(token,school_id,province,city,address,address_name,latitude,longitude,remark,after_word_time,name,account))
                            qiandao_TF.append(task)                        
                            continue
                else:
                    print("【控制台】用户配置不需要执行【下班】操作")
                    bot_message_after_word += (f"{name} {account} 不打卡,\n")
                    bot_message_sure_budaka += 1
        except:
            print(f"姓名：{name} 手机号：{phone} 学号：{account} 失败")
            continue
    print("——————————————————————————————\n【任务库】所有用户任务已分配完毕，等待结果")
    end_fenpei_time = time.time()
    execution_fenpei_time = end_fenpei_time - start_fenpei_time
    print(f"【任务库】所有任务分配所花时间【{execution_fenpei_time:.2f}秒】")
    bot_message += (f"所有任务分配所花时间【{execution_fenpei_time:.2f}秒】\n")
    start_task_back = time.time()
    results = await asyncio.gather(*qiandao_TF)
    for result in results:
        print(f"1.{result[0]}2.{result[1]}3.{result[2]}")
        if isinstance(result, tuple):
            if result[0] == True:
                if len(result) >= 4:  # 确保元组有足够的元素
                    if pushMessageReduction == "false":
                        bot_message += (f"{result[1]} 成功,连续签到【{result[2]}】天,签到时间{result[3]}\n")
                    bot_message_sure += 1
                else:
                    if pushMessageReduction == "false":
                        bot_message += (f"{result[1]} 成功,连续签到【{result[2]}】天\n")
                    bot_message_sure += 1
            elif result[0] == False and result[2] != "今日签到次数已满" and result[2] != "每次签到时间间隔至少8小时":
                bot_message += (f"{result[1]} 失败,问题【{result[2]}】\n")
                bot_message_error += 1
            elif result[0] == False and result[2] == "今日签到次数已满":
                bot_message += (f"{result[1]} 签到次数已满\n")
                bot_message_surr_max += 1
            elif result[0] == False and result[2] == "每次签到时间间隔至少8小时":
                bot_message += (f"{result[1]} 打卡间隔时间不够\n")
                bot_message_error_surr_time += 1
            elif result[0] == "ERROR":
                bot_message += (f"{result[1]} 失败,问题【{result[2]}】\n")
                bot_message_error += 1
    end_task_back = time.time()
    execution_task_time = end_task_back - start_task_back
    bot_message += bot_message_after_word
    print(f"\n【任务库】所有任务执行所花时间【{execution_task_time:.2f}秒】\n————————————————————")
    bot_message += (f"所有任务执行所花时间【{execution_task_time:.2f}秒】")
    print(f"最终结果：\n{results}\n")
    print("结束")
    
    huizong_message = (f"{bot_message}\n———————————\n任务库数据汇总\n用户总数：{users_len}个\n成功：{bot_message_sure}个\n失败:{bot_message_error}个\n登录失败:{bot_message_error_login}个\n不打卡:{bot_message_sure_budaka}个\n签到次数已满:{bot_message_surr_max}个\n签到间隔不足:{bot_message_error_surr_time}")
    print(huizong_message)
    bot_message_tuisong = load_send()
    if bot_message_tuisong is not None:
        print("发现推送服务|正在推送")
        bot_message_tuisong("习讯云助手",huizong_message)
    
                       
if __name__ == "__main__":    
    with open(f'{weizhi}{os.sep}data{os.sep}user.json', 'r',encoding="utf-8") as f:
        user_data = json.load(f)

    asyncio.run(main())
