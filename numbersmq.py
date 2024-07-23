import hashlib
import json
import os
import sys
import time
import urllib
from datetime import datetime
from urllib.error import URLError, HTTPError
import os
import glob
# from _paths import nomeroff_net_dir


import pika
from matplotlib import pyplot as plt
import numpy as np
import cv2
import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()

os.environ["CUDA_VISIBLE_DEVICES"] = "1"
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"

current_dir = os.path.dirname(os.path.abspath(__file__))
nomeroff_net_dir = os.path.join(current_dir, "../../../")
sys.path.append(nomeroff_net_dir)

from nomeroff_net import pipeline
from nomeroff_net.tools import unzip

# # NomeroffNet path
# NOMEROFF_NET_DIR = "/var/www/cameras-master/"
# # NOMEROFF_NET_DIR = os.path.abspath('../')
# sys.path.append(NOMEROFF_NET_DIR)


number_plate_detection_and_reading = pipeline("number_plate_detection_and_reading", image_loader="opencv")


def imgprocess(img):
    img_path = '/var/www/nomeroff/tmp/' + img
    result = number_plate_detection_and_reading(glob.glob(
        os.path.join(nomeroff_net_dir, img_path)))

    (images, images_bboxs,
     images_points, images_zones, region_ids,
     region_names, count_lines,
     confidences, texts) = unzip(result)

    return texts[0]


credentials = pika.PlainCredentials('username', 'password')
connection = pika.BlockingConnection(pika.ConnectionParameters('host', 5672, '/', credentials))
channel = connection.channel()
channel_numbers = connection.channel()
channel_numbers.queue_declare(queue='queue')
channel.basic_qos(prefetch_count=2)

channel.queue_declare(queue='numbers_queue')
i = 0


def callback(ch, method, properties, body):
    start_timer = time.time()
    global i
    # print(">>> %r" % body)
    data = json.loads(body)
    try:
        date = datetime.strptime(data['datetime'], '%d %b %Y %H:%M:%S')
        dateurl = date.strftime("%Y-%m/%d")
        link = "{}/{}/{}".format(data['cam'], dateurl, data['screen'])
        linktomd5 = str(link + "hash")
        md5 = hashlib.md5(linktomd5.encode('utf-8')).hexdigest()
        imgpath = "https://queue_url/{}/{}/{}".format(data['type'], md5, link)
        # print(imgpath)
        if data['cam'] == "whitelist_camera_ip":
            return True
        try:
            urllib.request.urlretrieve(imgpath, "/var/www/nomeroff/tmp/" + imgpath.split('/')[-1])
        except HTTPError as e:
            print('Error code: ', e.code)
        except URLError as e:
            print('Reason: ', e.reason)
        else:
            if os.path.isfile('/var/www/nomeroff/tmp/' + data['screen']):
                number = imgprocess(data['screen'])
                # print(number)
                # print(type(number))
                os.remove('/var/www/nomeroff/tmp/' + data['screen'])
                if len(number) != 0:
                    to_json = {'timestamp': int(float(date.timestamp()) * 1000), 'usetime': True, 'number': number,
                               'cam': data['cam'], 'key': 0, 'pic': imgpath}
                    # print("<<< " + json.dumps(to_json))
                    channel_numbers.basic_publish(exchange='',
                                                  routing_key='numbers',
                                                  body=json.dumps(to_json))
                    i = i + 1
                    print(i)
    except Exception as e:
        print('datetime error')
        print(e)

    ch.basic_ack(delivery_tag=method.delivery_tag)
    print(f'Total time: {time.time() - start_timer}')


channel.basic_consume('numbers_queue', callback)
print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()
