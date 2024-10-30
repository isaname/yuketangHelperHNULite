# -*- coding: utf-8 -*-
# version 5
# developed by 潇洒哥
import configparser

import cv2
import random
import time
import requests
import re
import json

config = configparser.ConfigParser()
config.read('config.ini',encoding='utf8')

urls = config['urls']
custom = config['custom']

csrftoken = custom.get('csrftoken')  

sessionid = custom.get('sessionid')  

learn_rate = int(custom.get('learn_rate'))


university_id = "2911" # 湖大id，不必改
base_url = urls.get('base_url')
url_root = base_url +'/' 


user_id = ""

heartbeat_url = urls.get('heartbeat_url').format(base_url=base_url)


headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36',
    'Content-Type': 'application/json',
    'Cookie': 'csrftoken=' + csrftoken + '; sessionid=' + sessionid + '; university_id=' + university_id + '; platform_id=3',
    'x-csrftoken': csrftoken,
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'university-id': university_id,
    'xtbz': 'cloud'
}

leaf_type = {
    "video": 0,
    "homework": 6,
    "exam": 5,
    "recommend": 3,
    "discussion": 4
}


def get_video_info(video_info_url):
    '''
    获取视频部分信息
    :param video_id: 视频 ID
    :return: 包含视频 SKU ID, ccid 和视频名称的元组
    '''
    video_info = requests.get(video_info_url, headers=headers)
    video_info.encoding = video_info.apparent_encoding
    data = json.loads(video_info.text)['data']
    sku_id = data['sku_id']
    cc = data['content_info']['media']['ccid']
    video_name = data['name']
    return sku_id, cc, video_name


def get_video_len(video_play_url):
    '''
    获取视频长度
    :param video_id: 视频 ID
    :return: 视频时长（以秒为单位）
    '''
    video_play = requests.get(video_play_url, headers=headers)
    video_play.encoding = video_play.apparent_encoding
    try:
        video_play = json.loads(video_play.text)['data']['playurl']['sources']['quality10'][0]
    except:
        video_play = json.loads(video_play.text)['data']['playurl']['sources']['quality20'][0]
    cap = cv2.VideoCapture(video_play)
    if cap.isOpened():
        fps = cap.get(5)
        framenum = cap.get(7)
        duration = int(framenum / fps)
        return duration
    else:
        return 0



def send_heartbeat_packet(video_id, course_id, user_id, classroom_id, sku_id,d,cc,begin):    
    # 心跳包模板，包含通用的信息
    template = {
        'c': course_id,  # 课程ID
        'cards_ed': 0,  # 固定设置为0
        'cc': cc,  # 每个视频的特定参数
        'classroomid': classroom_id,  # 教室ID
        'cp': begin,  # 当前播放时长
        'd': d,  # 总时长
        'et': '',  # 心跳包类型
        'fp': 0,  # !视频起始播放位置
        'i': 5,  # 固定设置为5
        'lob': 'cloud4',  # 固定设置为”cloud4“
        'n': 'ali-cdn.xuetangx.com',  # 固定设置为”ali-cdn.xuetangx.com“
        'p': 'web',  # 固定设置为”web“
        'pg': video_id + '_' +''.join(random.sample('zyxwvutsrqponmlkjihgfedcba1234567890', 4)),  # 视频id_随机字符串
        'skuid': sku_id,  # SKU ID
        'slide': 0,  # 固定设置为0
        'sp': 2,  # 播放速度
        'sq': 0,  # 心跳包序列号
        't': 'video',  # 固定设置为”video“
        'tp': 0,  # !上一次看视频的播放位置
        'ts': int(time.time() * 1000),  # 时间戳，标识事件发生的时间戳
        'u': user_id,  # 用户ID
        'uip': '',  # 固定设置为”“
        'v': video_id,  # 视频ID
        'v_url': ''  # 固定设置为”“
    }


    # 设置各种url
    rate_url = urls.get('rate_url').format(base_url=base_url,
                                           course_id=course_id,
                                           user_id=user_id,
                                           classroom_id=classroom_id,
                                           video_id=video_id,
                                           university_id=university_id)
    '''
    loadstart --> seeking --> loadeddata --> play --> playing --> heartbeat --> ... ---> heartbeat  (size(heartbeat)=10) [发送]
    --> heartbeat --> heartbeat --> ... ---> heartbeat  (size(heartdata)=10) [发送]
    --> heartbeat --> heartbeat --> ... ---> heartbeat  (size(heartdata)=10) [发送]
    --> heartbeat --> heartbeat --> ... ---> heartbeat  (size(heartdata)=10) [发送]
    ...
    --> pause --> videoend [发送]
    '''

    # 构建新的心跳包
    heart_data = []
    # 添加初始心跳包数据
    init_pkg = [('loadstart', 1), ('seeking', 2), ('loadeddata', 3), ('play', 4), ('playing', 5)]
    sq = 6
    if begin > 20:
        sq = int(begin/4)
        init_pkg =  [('play', sq), ('playing', sq+1)]
        sq += 2


    for etype, sq in init_pkg:
        data = template.copy()
        data['et'] = etype
        data['sq'] = sq
        data['cp'] = begin
        begin+=10
        heart_data.append(data)
    begin = int(begin)
    # 生成心跳包序列并发送
    for i in range(begin, d, 10):
        # 迭代生成心跳包
        hb = template.copy()
        hb['et'] = 'heartbeat'
        hb['cp'] = i
        hb['sq'] = sq
        heart_data.append(hb)
        sq += 1
        if len(heart_data) == 6:  # 累积了一定数量的心跳包（10）
            # 发送心跳包
            requests.post(heartbeat_url, headers=headers, data=json.dumps({'heart_data': heart_data}))
            
            try:
                rate = requests.get(rate_url, headers=headers)
                rate = json.loads(rate.text)['data']
                percentage = float(rate[video_id]['rate']) * 100
                print('Video {} 观看进度:{}%'.format(video_id, percentage))
            except:
                print("wrong, no process")
                pass
            # 清空心跳包列表
            heart_data.clear()
            time.sleep(10/learn_rate)
    # 添加结束心跳包数据
    for etype in ['heartbeat', 'pause', 'videoend']:
        data = template.copy()
        data['et'] = etype
        data['cp'] = d
        data['sq'] = sq
        heart_data.append(data)
    requests.post(heartbeat_url, headers=headers, data=json.dumps({'heart_data': heart_data}))



def one_video_watcher(video_id, video_name, cid, user_id, classroomid, skuid,sign):
    video_id = str(video_id)
    classroomid = str(classroomid)

    rate_url = urls.get('rate_url').format(base_url=base_url,
                                           course_id=cid,
                                           user_id=user_id,
                                           classroom_id=classroomid,
                                           video_id=video_id,
                                           university_id=university_id)
    progress = requests.get(url=rate_url, headers=headers)


    video_info_url = urls.get('video_info_url').format(base_url=base_url,
                                                    classroom_id=classroomid,
                                                    video_id=video_id,
                                                    sign=sign, term='latest',
                                                    university_id=university_id)

    video_play_url = urls.get('video_play_url').format(base_url=base_url,
                                                    _date=str(int(time.time() * 1000)),
                                                    video_id=get_video_info(video_info_url=video_info_url)[1])

    if_completed = '0'

    try:
        if_completed_ = re.search(r'"completed":(.+?),', progress.text)
        if if_completed_:
            if_completed = if_completed_.group(1)
        else:
            print("wrong,no if_completed")
    except:
        pass


    if if_completed == '1':
        print(video_id + "已经学习完毕，跳过")
        return 1
    else:
        print(video_id + "，尚未学习，即将开始自动学习")
        time.sleep(2)

    skuid,cc,video_name = get_video_info(video_info_url=video_info_url)
    d = get_video_len(video_play_url=video_play_url)
    # 获取已有进度
    res_rate = json.loads(progress.text)
    if res_rate['data']:
        begin = float(res_rate["data"][video_id]["watch_length"])
    else:
        begin = 0

    
    # 发送心跳包
    send_heartbeat_packet(video_id,cid,user_id,classroomid,skuid,d,cc,begin)

    
    print("视频" + video_id + " " + video_name + "学习完成！")
    return 1


def get_videos_ids(course_name, classroom_id, course_sign):
    get_homework_ids = urls['chapter_url'].format(base_url=base_url,
                                                  classroom_id=classroom_id,
                                                  university_id=university_id,
                                                  sign=course_sign)
    
    homework_ids_response = requests.get(url=get_homework_ids, headers=headers)
    homework_json = json.loads(homework_ids_response.text)
    homework_dic = {}

    try:
        for i in homework_json["data"]["course_chapter"]:
            for j in i["section_leaf_list"]:
                if "leaf_list" in j:
                    for z in j["leaf_list"]:
                        if z['leaf_type'] == leaf_type["video"]:
                            homework_dic[z["id"]] = z["name"]
                else:
                    if j['leaf_type'] == leaf_type["video"]:
                        homework_dic[j["id"]] = j["name"]
        print(course_name + "共有" + str(len(homework_dic)) + "个作业")
        return homework_dic
    except:
        print("fail while getting homework_ids!!! please re-run this program!")
        raise Exception("fail while getting homework_ids!!! please re-run this program!")



if __name__ == "__main__":
    your_courses = []

    # 首先要获取用户的个人ID，即user_id,该值在查询用户的视频进度时需要使用
    user_id_url = url_root + "edu_admin/check_user_session/"
    id_response = requests.get(url=user_id_url, headers=headers)

    try:
        user_id_ = re.search(r'"user_id":(.+?)}', id_response.text)
        if user_id_:
            user_id = user_id_.group(1).strip()
        else:
            print("wrong,no user_id")
    except:
        print("也许是网路问题，获取不了user_id,请试着重新运行")
        raise Exception("也许是网路问题，获取不了user_id,请试着重新运行!!! please re-run this program!")

    # 然后要获取教室id
    get_classroom_id = url_root + "mooc-api/v1/lms/user/user-courses/?status=1&page=1&no_page=1&term=latest&uv_id=" + university_id + ""
    submit_url = url_root + "mooc-api/v1/lms/exercise/problem_apply/?term=latest&uv_id=" + university_id + ""
    classroom_id_response = requests.get(url=get_classroom_id, headers=headers)
    try:
        for ins in json.loads(classroom_id_response.text)["data"]["product_list"]:
            your_courses.append({
                "course_name": ins["course_name"],
                "classroom_id": ins["classroom_id"],
                "course_sign": ins["course_sign"],
                "sku_id": ins["sku_id"],
                "course_id": ins["course_id"]
            })
    except Exception as e:
        print("fail while getting classroom_id!!! please re-run this program!")
        raise Exception("fail while getting classroom_id!!! please re-run this program!")

    # 显示用户提示
    for index, value in enumerate(your_courses):
        print("编号：" + str(index + 1) + " 课名：" + str(value["course_name"]))

    flag = True
    while(flag):
        number = input("你想刷哪门课呢？请输入编号。输入0表示全部课程都刷一遍\n")
        # 输入不合法则重新输入
        if not (number.isdigit()) or int(number) > len(your_courses):
            print("输入不合法！")
            continue
        elif int(number) == 0:
            flag = False    # 输入合法则不需要循环
            # 0 表示全部刷一遍
            for ins in your_courses:
                homework_dic = get_videos_ids(ins["course_name"], ins["classroom_id"], ins["course_sign"])
                for one_video in homework_dic.items():
                    one_video_watcher(one_video[0], one_video[1], ins["course_id"], user_id, ins["classroom_id"],
                                      ins["sku_id"],ins["course_sign"])
        else:
            flag = False    # 输入合法则不需要循环
            # 指定序号的课程刷一遍
            number = int(number) - 1
            
            homework_dic = get_videos_ids(your_courses[number]["course_name"], your_courses[number]["classroom_id"],
                                          your_courses[number]["course_sign"])
            
            for one_video in homework_dic.items():
                one_video_watcher(one_video[0], one_video[1], your_courses[number]["course_id"], user_id,
                                  your_courses[number]["classroom_id"],
                                  your_courses[number]["sku_id"],your_courses[number]["course_sign"])
        print("搞定啦")
