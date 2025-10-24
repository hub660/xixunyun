import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from zhipuai import ZhipuAI

weizhi = os.path.dirname(os.path.abspath(__file__))
##################导入配置文件#####################
try:
    with open(f'{weizhi}{os.sep}data{os.sep}config.json', 'r',encoding="utf-8") as file:
        data = json.load(file)
        config = data['config'][0]
        version_config = config['version']
        from_config = config['from']
        platform_config = config['platform']
        key_config = config['key']
        client = ZhipuAI(api_key=config['Ai_peport']['ZhipuAI_key'])
        model=config['Ai_peport']['ZhipuAI_model']
except:
    print("配置文件错误，结束运行 | 配置文件：config.json")
    os._exit()

###########################################
class Xixunyun_report:
    def __init__(self, Token, school_id, business_type):
        # business_type 有 day、week、month
        self.token = Token
        self.school_id = school_id
        self.business_type = business_type

    def get_report_int(self):
        from_shebei = from_config #来源
        shebei_version = version_config  #版本
        platform = platform_config  #设备类

        headers = {
            "Host": "api.xixunyun.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/3.8.1"
        }

        params = {
            "business_type": self.business_type,
            "page_no": "1",
            "page_size": "20",
            "order": "create_time.desc",
            "token": self.token,
            "from": from_shebei,
            "version": shebei_version,
            "platform": platform,
            "entrance_year": "0",
            "graduate_year": "0",
            "school_id": self.school_id
        }

        try:
            # 发送请求
            response = requests.get("https://api.xixunyun.com/Reports/StudentSearch", params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # ("提取用户的日或周或月的报告列表，然后再从里面获得时间戳，找到大的一个，来跟今天进行判断，获得相差几天") 
                # 返回 相差的日期 （int) 或者 用户没有任何报告 (None)
                # 请求失败返回  请求超时，可能是网络问题、请求异常、会话已失效，请重新登录-1
                print(f"模式:{self.business_type}")
                # 检查返回的状态码
                if data.get('code', 0) != 20000:
                    return data.get('message', '未知错误')
                
                report_list = data.get('data', {}).get('list', [])
                
                # 如果没有报告数据
                if report_list is None or len(report_list) == 0:
                    print("用户没有报告")
                    return None

                # 提取时间戳
                create_times = [
                    int(item.get('create_time', 0)) for item in report_list
                ]
                
                if create_times: 
                    max_create_time = max(create_times)
                    max_create_date = datetime.fromtimestamp(max_create_time, tz=timezone.utc).date()
                    current_date = datetime.now(timezone.utc).date()
                    days_diff = (current_date - max_create_date).days
                    print(f"上次做报告的时间相对于今天相差{days_diff}天,模式{self.business_type}")
                    return days_diff

                else:
                    return None
        except requests.exceptions.Timeout:
            return "请求超时，可能是网络问题"
        except requests.exceptions.RequestException as e:
            return "请求异常"

class Xixunyun_report_qian:
    def __init__(self, Token, school_id, business_type, address):
        # business_type 有 day、week、month
        self.token = Token
        self.school_id = school_id
        self.business_type = business_type
        self.address = address

    def get_report_qian(self, content_1, content_2, content_3):
        from_shebei = from_config  # 来源
        shebei_version = version_config  # 版本
        platform = platform_config  # 设备类

        def generate_date_range(business_type):
            # 传出 'start_date' 'end_date'
            # 开始时间 与 结束时间
            # 日报 就 今天与今天
            # 周报 就 7天前的日期与今天
            # 月报 就 30天前的日期与今天
            # 'end_date' 结束日期
            # 'start_date' 开始日期
            # 格式为 年/月/日
            report_type = business_type
            today = datetime.now()
            if report_type == "day":
                start_date = today
                end_date = today
            elif report_type == "week":
                start_date = today - timedelta(days=7)
                end_date = today
            elif report_type == "month":
                start_date = today - timedelta(days=30)
                end_date = today
            return {
                'start_date': start_date.strftime('%Y/%m/%d'),
                'end_date': end_date.strftime('%Y/%m/%d')
            }

        date_range = generate_date_range(self.business_type)
        start_date, end_date = date_range['start_date'], date_range['end_date']

        ###################
        headers = {
            "Host": "api.xixunyun.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/3.8.1"
        }

        params = {
            "business_type": self.business_type,
            "page_no": "1",
            "page_size": "20",
            "order": "create_time.desc",
            "token": self.token,
            "from": from_shebei,
            "version": shebei_version,
            "platform": platform,
            "entrance_year": "0",
            "graduate_year": "0",
            "school_id": self.school_id
        }

        data = {
            'end_date': end_date,
            'address': self.address,
            'attachment': '',
            'business_type': self.business_type,
            'content': json.dumps([
                {
                    'content': content_1,
                    'require': '1',
                    'sort': '1',
                    'title': '实习工作具体现状及实习任务完成情况',
                },
                {
                    'content': content_2,
                    'require': '0',
                    'sort': '2',
                    'title': '主要收获及工作成就',
                },
                {
                    'content': content_3,
                    'require': '0',
                    'sort': '3',
                    'title': '工作中的问题及需要老师的指导帮助',
                },
            ]),
            'start_date': start_date,
        }

        try:
            # 发送请求，使用 POST 方法，并且使用 data 参数传递表单数据
            response = requests.post(
                "https://api.xixunyun.com/Reports/StudentOperator",
                params=params,
                data=data,
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                print(data)
                if data.get('code', 0) != 20000:
                    return data.get('message', '未知错误')
                elif data.get('code', 0) == 20000:
                    print("成功提交")
                    return "成功提交"
        except requests.exceptions.Timeout:
            return "请求超时，可能是网络问题"
        except requests.exceptions.RequestException as e:
            return "请求异常"
        
class Xixunyun_report_Ai:
    def __init__(self, Token, school_id, business_type,standing):
        self.token = Token
        self.school_id = school_id
        self.business_type = business_type
        self.standing = standing

    def get_report_Ai(self):
        # 传出 content_1、content_2、content_3
        def generate_fairy_tale(client, messages):
            response = client.chat.asyncCompletions.create(
                model=model,  
                messages=messages,
            )
            task_id = response.id
            task_status = ''
            get_cnt = 0
            while task_status != 'SUCCESS' and task_status != 'FAILED' and get_cnt <= 40:
                result_response = client.chat.asyncCompletions.retrieve_completion_result(id=task_id)
                task_status = result_response.task_status
                time.sleep(1)
                get_cnt += 1
            return result_response

        if self.business_type == "day":
            business_type_china = "日报"
        elif self.business_type == "week":
            business_type_china = "周报"
        elif self.business_type == "month":
            business_type_china = "月报"
        # 创建多问题的列表，每个问题对应一个分开的请求
        request1 = [{"role": "system", "content": "你是一个专注于攥写实习报告的机器人，你只需要根据我的要求攥写，切记必须是中文回复，并且不能涉及任何地名、人名，如果需要提到人物，请使用人物关系的称号，例如(上司、老板、同事、朋友)。"},
                    {"role": "user", "content": f"写关于'实习工作具体现状及实习任务完成情况'的实习[{business_type_china}]报告，字数不能少于65字，不能高于90字，以第一人称视角。我的岗位是[{self.standing}]，带有感情，减少标点符号的使用，语句通常，尽量使用大白话。"}]
        request2 = [{"role": "system", "content": "你是一个专注于攥写实习报告的机器人，你只需要根据我的要求攥写，切记必须是中文回复，并且不能涉及任何地名、人名，如果需要提到人物，请使用人物关系的称号，例如(上司、老板、同事、朋友)。"},
                    {"role": "user", "content": f"写关于'主要收获及工作成就'的实习[{business_type_china}]报告，字数不能少于65字，不能高于90字，以第一人称视角。我的岗位是[{self.standing}]，带有感情，减少标点符号的使用，语句通常，尽量使用大白话。"}]
        request3 = [{"role": "system", "content": "你是一个专注于攥写实习报告的机器人，你只需要根据我的要求攥写，切记必须是中文回复，并且不能涉及任何地名、人名，如果需要提到人物，请使用人物关系的称号，例如(上司、老板、同事、朋友)。"},
                    {"role": "user", "content": f"写关于'工作中的问题及需要老师的指导帮助'的实习[{business_type_china}]报告，字数不能少于65字，不能高于90字，以第一人称视角。我的岗位是[{self.standing}]，带有感情，减少标点符号的使用，语句通常，尽量使用大白话。"}]

        # 异步生成童话故事
        result1 = generate_fairy_tale(client, request1)
        result2 = generate_fairy_tale(client, request2)
        result3 = generate_fairy_tale(client, request3)

        # 分别保存每个请求的返回内容和状态
        if result1.task_status == 'SUCCESS':
            content_1 = result1.choices[0].message.content
        else:
            content_1 = (False,"请求失败，状态为:" + result1.task_status)

        if result2.task_status == 'SUCCESS':
            content_2 = result2.choices[0].message.content
        else:
            content_2 = (False,"请求失败，状态为:" + result2.task_status)

        if result3.task_status == 'SUCCESS':
            content_3 = result3.choices[0].message.content
        else:
            content_3 = (False,"请求失败，状态为:" + result3.task_status)
        print(f"问题1: {content_1}")
        print(f"问题2: {content_2}")
        print(f"问题3: {content_3}")
        if content_1[0] != False:
            content_1 = True,content_1
        if content_2[0] != False:
            content_2 = True,content_2
        if content_3[0] != False:
            content_3 = True,content_3

        return content_1,content_2,content_3

if __name__ == "__main__":
    # 假设这些变量已经被正确赋值
    Token = '23cfab69452b12c23a140665e44a26ad'
    school_id = 842
    business_type = "day"
    
    #usr_record_insp = Xixunyun_report(Token, school_id, business_type).get_report_int()
    #print(usr_record_insp)
    word_name_guishu = "浙江省嘉兴市桐乡市乌镇镇乌镇汽车度假中心"
    content_1 = "我在客服岗位，今天接听了二十余通客户电话，态度亲切，耐心解答疑问，收获好评。完成了上司安排的任务，学习了新沟通技巧，实习生活充实。"
    content_2 = "在这次客服实习中，我深刻体会到了耐心与沟通的重要性，成功帮助了许多客户解决问题，收获了满满的责任感和成就感。"
    content_3 = "今天遇到了客户投诉问题，感觉有点儿力不从心，希望能得到老师的指导，告诉我如何更有效地沟通解决问题，真的很需要帮助。"
    print(Xixunyun_report_qian(Token, school_id, business_type, word_name_guishu).get_report_qian(content_1,content_2,content_3))
