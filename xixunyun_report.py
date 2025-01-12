#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: xixunyun_cookie.py(习讯云日周月报告)
Author: luoye
Date: 2024/11/15 13:00
cron: 54 12 * * *
new Env('习讯云日周月报告');
Update: 2024/11/15
"""

import asyncio
import calendar
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from usr_record import Xixunyun_record
from usr_report import (Xixunyun_report, Xixunyun_report_Ai,
                        Xixunyun_report_qian)
from usr_token import Xixunyun_login

##################################################
weizhi = os.path.dirname(os.path.abspath(__file__))
##################导入配置文件#####################
try:
    with open(f'{weizhi}{os.sep}data{os.sep}config.json', 'r', encoding="utf-8") as file:
        data = json.load(file)
        config = data['config'][0]
        version_config = config['version']
        from_config = config['from']
        platform_config = config['platform']
        key_config = r"{}".format(config['key'])
        Ai_peport = config['Ai_peport']['Ai_peport']
        MAX_CONCURRENT_USERS = config['Ai_peport']['report_max_concurrent_users']
        DELAY_MIN = config['Ai_peport']['report_delay_min']
        DELAY_MAX = config['Ai_peport']['report_delay_max']
        if Ai_peport == False or Ai_peport == "false":
            print("【控制台】配置文件中未启动Ai提交日、周、月报告功能，如需使用：\n请在 data/config.json 将 Ai_peport 改为 True ")
            os._exit(0)
        elif Ai_peport == True or Ai_peport == "true":
            print("【控制台】Ai提交日、周、月报告功能 | 启用中")
except:
    print("配置文件错误，结束运行 | 配置文件：config.json")
    os._exit(0)
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

def parse_time(time_str):
    # 将字符串 "HH:MM" 解析为小时和分钟
    time_parts = time_str.split(":")
    return int(time_parts[0]), int(time_parts[1])

async def send_report(token, school_id, business_type, word_name_guishu, name, account, result_queue, current_total, counters, counter_lock, *report_texts):
    """
    发送报告的异步函数
    """
    try:
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        delay_minutes = delay / 60
        print(f"{name} {account} 将在 {delay_minutes:.2f} 分钟后发送{business_type}报告。")
        
        await asyncio.sleep(delay)
        
        print(f"用户 {name}（账号：{account}）正在发送{business_type}报告内容：")
        print(*report_texts)
        
        response = Xixunyun_report_qian(token, school_id, business_type, word_name_guishu).get_report_qian(*report_texts)
        print(f"用户 {name}（账号：{account}）的 {business_type} 报告已发送，响应: {response}")
        
        result = None
        if response == "成功提交":
            result = (business_type, True, "成功提交")
            if business_type == 'day':
                async with counter_lock:
                    counters['day_success'] += 1
            elif business_type == 'week':
                async with counter_lock:
                    counters['week_success'] += 1
            elif business_type == 'month':
                async with counter_lock:
                    counters['month_success'] += 1
        # 其他情况不增加成功计数
        elif response in ["请求超时，可能是网络问题", "请求异常"]:
            result = (business_type, False, response)
        else:
            result = (business_type, False, "未知错误")
            
        # 将结果放入队列
        await result_queue.put((current_total, account, business_type, result))
        return result
    except Exception as e:
        print(f"发送报告时出错: {str(e)}")
        await result_queue.put((current_total, account, business_type, (business_type, False, str(e))))
        return (business_type, False, str(e))

async def worker(name, queue, qiandao_TF, counters, bot_message_parts, semaphore, counter_lock):
    print(f"{name} 启动")
    while True:
        user = await queue.get()
        if user is None:
            queue.task_done()  # 只在这里调用一次
            break
        try:
            print(f"{name} 开始处理用户 {user.get('name')}")
            await process_user(user, qiandao_TF, counters, bot_message_parts, semaphore, counter_lock)
            print(f"{name} 完成处理用户 {user.get('name')}")
        except Exception as e:
            print(f"[{name}] 处理用户 {user.get('name')} 时出错: {e}")
        finally:
            queue.task_done()  # 确保每个任务只调用一次

def run_worker_in_thread(worker_name, users, qiandao_TF, counters, bot_message_parts, semaphore, counter_lock):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def worker_task():
        for user in users:
            try:
                await process_user(user, qiandao_TF, counters, bot_message_parts, semaphore, counter_lock)
            except Exception as e:
                print(f"[{worker_name}] 处理用户 {user.get('name')} 时出错: {e}")
    
    loop.run_until_complete(worker_task())
    loop.close()

async def batch_process_users(worker_name, users, qiandao_TF, counters, bot_message_parts, semaphore, counter_lock):
    print(f"{worker_name} 启动")
    for user in users:
        try:
            print(f"{worker_name} 开始处理用户 {user.get('name')}")
            await process_user(user, qiandao_TF, counters, bot_message_parts, semaphore, counter_lock)
            print(f"{worker_name} 完成处理用户 {user.get('name')}")
        except Exception as e:
            print(f"[{worker_name}] 处理用户 {user.get('name')} 时出错: {e}")

def should_send_report(business_type, user_business_int, threshold, report_mode):
    def get_today_weekday():
        # 判断是否是星期天
        #is_sunday = debug_date.weekday() == 6        
        is_sunday = datetime.today().weekday() == 6        
        # 输出结果
        if is_sunday:
            return "星期日"
        else:
            return "不是"

    def is_end_of_month():
        # 判断今天是否是月底
        #today = debug_date.today()
        today = datetime.today()
        next_day = today + timedelta(days=1)  # 修改此行
        return next_day.month != today.month
    needs_business = False
    message = ""
    if report_mode == "1":
        if business_type == 'day':
            if isinstance(user_business_int, int) and user_business_int >= threshold:
                needs_business = True
                message = f"报告距离上次撰写已经超过{threshold}天 | 需要撰写"
            elif isinstance(user_business_int, int):
                message = f"报告距离上次撰写未超过{threshold}天 | 不需要撰写"
            elif user_business_int is None:
                needs_business = True
                message = "报告无记录 | 需要撰写"
            else:
                message = f"报告状态未知: {user_business_int}"
        elif business_type == 'week':
            today_weekday = get_today_weekday()
            if today_weekday == "星期日" and isinstance(user_business_int, int) and user_business_int > 1:
                needs_business = True
                message = f"今天是星期日 | 需要撰写周报"
            elif today_weekday == "星期日" and user_business_int is None:
                needs_business = True
                message = f"今天是星期日 | 用户从没写过周报 | 需要撰写周报"
            elif today_weekday == "星期日":
                message = f"今天是星期日，但报告距离上次撰写未超过1天 | 不需要撰写周报"
            else:
                message = f"今天不是星期日 | 不需要撰写周报"
        elif business_type == 'month':
            end_of_month = is_end_of_month()
            if end_of_month and isinstance(user_business_int, int) and user_business_int > 1:
                needs_business = True
                message = "今天是月底 | 需要撰写月报"
            elif end_of_month and user_business_int is None:
                needs_business = True
                message = f"今天是月底 | 用户从没写过月报 | 需要撰写月报"
            elif end_of_month:
                message = "今天是月底，但报告距离上次撰写未超过1天 | 不需要撰写月报"
            else:
                message = "今天不是月底 | 不需要撰写月报"
    elif report_mode == "2":
        # 原有模式的逻辑
        if isinstance(user_business_int, int):
            if user_business_int >= threshold:
                needs_business = True
                message = f"报告距离上次撰写已经超过{threshold}天 | 需要撰写"
            else:
                message = f"报告距离上次撰写未超过{threshold}天 | 不需要撰写"
        elif user_business_int is None:
            needs_business = True
            message = "报告无记录 | 需要撰写"
        elif user_business_int in ["请求超时，可能是网络问题", "请求异常"]:
            message = f"报告获取失败: {user_business_int}"
        else:
            message = f"报告状态未知: {user_business_int}"
    else:
        message = "未知的报告模式 | 不需要撰写"
    
    return needs_business, message

async def process_user(user, qiandao_TF, counters, bot_message_parts, semaphore, counter_lock):
    """
    处理单个用户的协程函数
    """
    name = user['name']
    school_id = user['school_id']
    token = user['token']
    moth = user['moth']
    word_name_guishu = user['word_name_guishu']
    password = user['password']
    account = user['account']
    model = user['model']
    mac = user['mac']
    phone = user['phone']
    jiuxu = user['jiuxu']
    standing = user['standing']
    day_report = user['day_report']
    week_report = user['week_report']
    month_report = user['month_report']
    report_mode = user['report_mode']

    # 使用锁来保护计数器更新
    async with counter_lock:
        counters['total'] += 1
        current_total = counters['total']
    
    print(f"\n-------- 当前用户 姓名：{name} 手机号：{phone} 学号：{account}   -------------本次序列第【{current_total}】位用户-------------\n")

    if not jiuxu:
        print("配置信息失效 跳过")
        async with counter_lock:
            counters['failure'] += 1
        return

    # 判断是否存在于有效期中
    ageing_TF = ageing(moth)
    if not ageing_TF:
        async with counter_lock:
            counters['failure'] += 1
        return

    pending_tasks = []
    reports_needed = 0
    reports_success = 0
    result_queue = asyncio.Queue()

    # 使用信号量控制并发请求
    async with semaphore:
        current_concurrent = MAX_CONCURRENT_USERS - semaphore._value
        print(f"当前并发数: {current_concurrent}/{MAX_CONCURRENT_USERS}")

        try:
            user_record_login = Xixunyun_record(token, school_id).get_record()
            if len(user_record_login) > 3:
                user_record_errow = user_record_login
                if user_record_errow == "请求异常":
                    print("因为请求异常，用户Token更新失败")
                    async with counter_lock:
                        counters['failure'] += 1
                    return
                
                elif user_record_errow == "请求超时，可能是网络问题":
                    print("----------------出现请求超时情况，终止当前用户任务---------------------")
                    async with counter_lock:
                        counters['failure'] += 1
                    return
                
                elif (user_record_errow.get('code') == 40511 and user_record_errow.get('message') == '登录超时') or (user_record_errow.get('code') == 40510):
                    print("【补救措施-登录超时】出现登录超时情况，重新获得用户Token")
                    usr_token_insp = Xixunyun_login(school_id, password, account, model, mac).get_token()
                    usr_token_insp_len = len(usr_token_insp)
                    if usr_token_insp_len > 7:
                        user_name, school_id, token, user_number, bind_phone, user_id, class_name, entrance_year, graduation_year = usr_token_insp
                        user_record_login = Xixunyun_record(token, school_id).get_record()
                        print(f"【补救措施-登录超时】成功获得用户Token: {token}")
                        if len(user_record_login) > 3:
                            user_record_errow = user_record_login
                            print("【补救措施-登录超时】错误[record]回复，用户[record]查询失败", user_record_errow)
                            async with counter_lock:
                                counters['failure'] += 1
                            return
                    else:
                        print(f"【补救措施-登录超时】失败，无法获得用户 Token")
                        print(f"{name} {account} 登录失败")
                        async with counter_lock:
                            counters['failure'] += 1
                        return
                else:
                    print("错误[record]回复，用户[record]查询失败", user_record_errow)
                    print(f"{name} {account} 登录失败")
                    async with counter_lock:
                        counters['failure'] += 1
                    return

            # 日 周 月 报告处理逻辑
            business_thresholds = {
                'day': 1,
                'week': 7,
                'month': 30
            }

            user_tasks = []  # 初始化用户任务列表

            for business_type in ['day', 'week', 'month']:
                # 根据用户配置决定是否处理该类型的报告
                if business_type == 'day' and not day_report:
                    print(f"{name} {account} 设置不需要撰写日报，跳过。")
                    async with counter_lock:
                        counters['day_not_needed'] = counters.get('day_not_needed', 0) + 1
                    continue
                if business_type == 'week' and not week_report:
                    print(f"{name} {account} 设置不需要撰写周报，跳过。")
                    async with counter_lock:
                        counters['week_not_needed'] = counters.get('week_not_needed', 0) + 1
                    continue
                if business_type == 'month' and not month_report:
                    print(f"{name} {account} 设置不需要撰写月报，跳过。")
                    async with counter_lock:
                        counters['month_not_needed'] = counters.get('month_not_needed', 0) + 1
                    continue
                try:
                    if not ageing_TF:
                        continue
                    
                    threshold = business_thresholds.get(business_type)

                    user_business_int = Xixunyun_report(token, school_id, business_type).get_report_int()
                    print(f"用户日、周、月报告 职业：{standing} | Day: {user_business_int if business_type == 'day' else '-'}, "
                          f"Week: {user_business_int if business_type == 'week' else '-'}, "
                          f"Month: {user_business_int if business_type == 'month' else '-'}")
                    
                    needs_business, message = should_send_report(business_type, user_business_int, threshold, report_mode)
                    print(message)
                    
                    if needs_business:
                        reports_needed += 1
                        async with counter_lock:
                            if business_type == 'day':
                                counters['day_written'] += 1
                            elif business_type == 'week':
                                counters['week_written'] += 1
                            elif business_type == 'month':
                                counters['month_written'] += 1
                        content = Xixunyun_report_Ai(token, school_id, business_type, standing).get_report_Ai()
                        if content:
                            all_true = all(item[0] for item in content)
                            
                            if all_true and len(content) == 3:
                                report_texts = [item[1] for item in content]
                                print(f"\————————成功获得{business_type}报告，等待发送————————\n")
                                
                                # 创建任务并保存引用
                                task = asyncio.create_task(
                                    send_report(
                                        token, school_id, business_type, word_name_guishu,
                                        name, account, result_queue, current_total, counters, counter_lock, *report_texts
                                    )
                                )
                                user_tasks.append(task)
                                reports_needed += 1
                    else:
                        async with counter_lock:
                            if "不需要撰写" in message:
                                if business_type == 'day':
                                    counters['day_not_needed'] = counters.get('day_not_needed', 0) + 1
                                elif business_type == 'week':
                                    counters['week_not_needed'] = counters.get('week_not_needed', 0) + 1
                                elif business_type == 'month':
                                    counters['month_not_needed'] = counters.get('month_not_needed', 0) + 1

                    # 在函数结束前等待所有该用户的任务完成
                    if user_tasks:
                        await asyncio.gather(*user_tasks)

                except Exception as e:
                    print(f"处理 {name} 的{business_type}报告时出错: {str(e)}")
                    continue

            # 在主程序结束前添加任务引用到全局列表
            if 'GLOBAL_PENDING_TASKS' not in globals():
                global GLOBAL_PENDING_TASKS
                GLOBAL_PENDING_TASKS = []
            GLOBAL_PENDING_TASKS.extend(pending_tasks)

            # 更新用户最终状态统计
            async with counter_lock:
                if reports_needed == 0:
                    counters['success'] += 1
                else:
                    # 暂时标记为处理中
                    counters['processing'] = counters.get('processing', 0) + 1

        except Exception as e:
            print(f"姓名：{name} 手机号：{phone} 学号：{account} 失败，错误: {str(e)}")
            async with counter_lock:
                counters['failure'] += 1
            return

async def main():
    #start_time_now = debug_date.now().strftime('%Y-%m-%d %H:%M:%S')
    start_time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    qiandao_TF = []
    counters = {
        'success': 0,
        'half_success': 0,
        'failure': 0,
        'total': 0,
        'day_success': 0,
        'week_success': 0,
        'month_success': 0,
        'processing': 0,
        'day_written': 0,   # 日报撰写总数
        'week_written': 0,  # 周报撰写总数
        'month_written': 0,  # 月报撰写总数
        'day_not_needed': 0,    # 不需要撰写的日报数
        'week_not_needed': 0,   # 不需要撰写的周报数
        'month_not_needed': 0   # 不需要撰写的月报数
    }
    bot_message = ""
    bot_message_after_word = ""
    start_fenpei_time = time.time()

    # 读取用户数据
    try:
        with open(f'{weizhi}{os.sep}data{os.sep}user.json', 'r', encoding="utf-8") as f:
            user_data = json.load(f)
        users = user_data['users']
        users_len = len(users)
        print(f"总用户：{users_len}, 当前模式 Ai日报周报月报 | 并行用户数：{MAX_CONCURRENT_USERS}")
    except Exception as e:
        print(f"读取用户数据失败: {e}")
        return

    # 创建锁和信号量
    counter_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_USERS)
    
    # 将用户分组
    chunk_size = max(1, (users_len + MAX_CONCURRENT_USERS - 1) // MAX_CONCURRENT_USERS)
    user_chunks = [users[i:i + chunk_size] for i in range(0, users_len, chunk_size)]
    
    # 创建线程池并执行任务
    try:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_USERS) as executor:
            # 创建一个列表来存储所有任务
            all_tasks = []
            for i, user_chunk in enumerate(user_chunks):
                worker_name = f'worker-{i+1}'
                loop = asyncio.get_event_loop()
                task = loop.run_in_executor(
                    executor,
                    run_worker_in_thread,
                    worker_name,
                    user_chunk,
                    qiandao_TF,
                    counters,
                    bot_message_after_word,
                    semaphore,
                    counter_lock
                )
                all_tasks.append(task)
                print(f"{worker_name} 已创建，分配了 {len(user_chunk)} 个用户")

            # 等待所有任务完成
            await asyncio.gather(*all_tasks)

        print("——————————————————————————————\n【任务库】所有用户任务已分配完毕")
        end_fenpei_time = time.time()
        execution_fenpei_time = end_fenpei_time - start_fenpei_time
        print(f"【任务库】所有任务分配所花时间【{execution_fenpei_time:.2f}秒】")
        bot_message += f"所有任务分配所花时间【{execution_fenpei_time:.2f}秒】\n"
        
        # 等待所有后台发送任务完成
        if 'GLOBAL_PENDING_TASKS' in globals():
            print(f"\n开始等待 {len(GLOBAL_PENDING_TASKS)} 个后台报告发送任务完成...")
            try:
                await asyncio.gather(*GLOBAL_PENDING_TASKS)
                print("所有报告发送任务已完成")
            except Exception as e:
                print(f"等待报告发送任务时出错: {e}")
        
        # 更新最终统计数据
        processing_count = counters.get('processing', 0)
        if processing_count > 0:
            print(f"\n处理最终统计数据，有 {processing_count} 个处理中的用户需要更新状态")
            # 将 processing 状态的用户更新为最终状态
            counters['success'] += processing_count
            counters['processing'] = 0
        
        start_task_back = time.time()
        
        # 计算成功率和统计信息
        total_tasks = counters['total']
        success_rate = (counters['success'] / total_tasks * 100) if total_tasks > 0 else 0
        half_success_rate = (counters['half_success'] / total_tasks * 100) if total_tasks > 0 else 0
        failure_rate = (counters['failure'] / total_tasks * 100) if total_tasks > 0 else 0

        end_task_back = time.time()
        execution_task_time = end_task_back - start_task_back
        total_execution_time = end_task_back - start_fenpei_time
        
        # 生成详细的汇总消息
        huizong_message = (
            f"{bot_message}\n"
            f"———————————\n"
            f"习讯云Ai日报周报月报执行报告\n"
            f"开始时间：{start_time_now}\n"
            f"———————————\n"
            f"任务统计信息：\n"
            f"• 总用户数：{users_len}人\n"
            f"• 成功用户：{counters['success']}人\n"
            f"  - 包含无需提交报告的用户\n"
            f"  - 包含需要提交且全部成功的用户\n"
            f"• 部分成功：{counters['half_success']}人\n"
            f"  - 需要提交多个报告但未全部成功\n"
            f"• 失败用户：{counters['failure']}人\n"
            f"  - 包含获取用户信息失败\n"
            f"  - 包含需要提交但全部失败的用户\n"
            f"———————————\n"
            f"报告类型统计：\n"
            #f"• 日报成功：{counters['day_success']}个\n"
            #f"• 周报成功：{counters['week_success']}个\n"
            #f"• 月报成功：{counters['month_success']}个\n"
            f"• 今日无需撰写日报：{counters.get('day_not_needed',0)}个\n"
            f"• 今日无需撰写周报：{counters.get('week_not_needed',0)}个\n"
            f"• 今日无需撰写月报：{counters.get('month_not_needed',0)}个\n"
            f"———————————\n"
            f"报告汇总：\n"
            f"• 今日撰写日报：{counters['day_written']}个\n"
            f"  - 成功：{counters['day_success']}个\n"
            f"• 今日撰写周报：{counters['week_written']}个\n"
            f"  - 成功：{counters['week_success']}个\n"
            f"• 今日撰写月报：{counters['month_written']}个\n"
            f"  - 成功：{counters['month_success']}个\n"
            f"———————————\n"
            f"• 总执行时间：{total_execution_time:.2f}秒"
        )
        
        print(huizong_message)
        
        # 推送消息
        try:
            bot_message_tuisong = load_send()
            if bot_message_tuisong is not None:
                print("发现推送服务|正在推送")
                bot_message_tuisong("习讯云助手", huizong_message)
            else:
                print("未找到推送服务")
        except Exception as e:
            print(f"推送消息失败: {e}")

    except Exception as e:
        print(f"执行过程中出错: {e}")
        return

    print("\n【任务库】所有任务执行完毕")

if __name__ == "__main__":  
    #用于测试的，模拟今天日期
    #debug_date = datetime(2024, 11, 17)
    asyncio.run(main())
