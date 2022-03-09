from datetime import datetime
import time
import boto3
import os
from botocore.exceptions import ClientError
from pathlib import Path
from PIL import Image
from io import BytesIO
import numpy as np
import cv2
# log
import logging
logger = logging.getLogger(__name__)
FORMAT = '%(asctime)s %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)

access_key = 'AKIAS2OTXTXV32WRBZ4P'
access_secret = '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'

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class S3Controller():
    s3_client = None
    s3 = None
    def __init__(self):
        #SSL failed, use verify=False 
        self.s3_client = boto3.client('s3', verify=False ,aws_access_key_id = access_key, aws_secret_access_key = access_secret)
        
        self.s3 = boto3.resource('s3', region_name='ap-southeast-1')

        
    def bucketList(self):
        s3_client = self.s3_client
        response = s3_client.list_buckets()
        bucketsList= response['Buckets']
        # Output the bucket names
        logger.info('Existing buckets:')
        for bucket in bucketsList:
            bucketName = bucket["Name"]
            logger.info(f'{bucketname}')

    
    def get_img_from_s3(self, bucketName, key):       
        response = self.s3_client.get_object(Bucket= bucketName, Key=key)   
        file_stream = response['Body']
        im_fs = Image.open(file_stream)
        img = cv2.cvtColor(np.array(im_fs), cv2.COLOR_RGB2BGR)
        return img


    def get_imgList_from_s3(self, bucketName, preFixKeyName):
        #list bucket object 
        s3_contents = self.s3_client.list_objects_v2(Bucket=bucketName, Prefix=preFixKeyName)
        tmp_key_list = []
        for content in s3_contents['Contents']:
            awsFileKey = content['Key']
            if preFixKeyName in awsFileKey:
                if (".png" in  awsFileKey or ".jpg" in  awsFileKey or ".jpeg" in  awsFileKey):
                    tmp_key_list.append(content['Key'])

        
        #logger.info("s3 image key list:" + str(len(tmp_key_list)))
        #if(len(tmp_key_list)!=0):
        #    logger.info(tmp_key_list[0])

        tmp_img_list = []
        for key in tmp_key_list:
            img = self.get_img_from_s3(bucketName, key)
            tmp_img_list.append(img)
        
        return tmp_img_list

    def download_bucket_image(self,bucket_name, localTempDir, key_Prefix):
        #GET bucket content
        #using DL_key_prefix = 'company/device_name/date/origin/'
        s3_client = self.s3_client
        reponse = s3_client.list_objects_v2(Bucket=bucket_name, Prefix = key_Prefix)
        logger.info("download_bucket_image, from s3 bucket: " + bucket_name)           
        logger.info("reponse: ", reponse)
        #find all jpg or png file in the buckt (origin subfolder)
        contentList = reponse['Contents']
        localImgPathList = []
        for content in contentList:
            key = content['Key'] #file name  
            if not(".png" in  key or ".jpg" in  key or ".jpeg" in  key):
                continue
            
            #local saving folder structure
            keyDirPath = os.path.dirname(key) 
            keyFileName = os.path.basename(key)              
            directory = os.path.join(localTempDir, keyDirPath)
            
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info("makedirs directory: " + str(directory))  
            #local saving image path
            localFileName = os.path.join(directory, keyFileName)
            logger.info("localFileName: "+ localFileName)
            s3_client.download_file(bucket_name, Key = key, Filename = localFileName)
            localImgPathList.append(localFileName)
        
        return localImgPathList
    
    #upload image from local dir
    def upload2_bucket_from_dir(self, bucket_name, localUploadDir, key_prefix):
        s3_client = self.s3_client
        logger.info("upload2_bucket_image, from local dir: " + localUploadDir)
        value = False

        location_info = s3_client.get_bucket_location(Bucket=bucket_name)
        bucket_location = location_info['LocationConstraint']
        #logger.info("bucket_location:" + str(bucket_location))
       
        img_url_list = []
        for file in os.listdir(localUploadDir):
            try:
                #print(f"upload file:{file}")
                file_key = key_prefix + str(file)
                s3_client.upload_file(os.path.join(localUploadDir, file), bucket_name, file_key, ExtraArgs={'ACL': 'public-read'})
                #object s3 URL
                object_url = "https://{0}.s3.{1}.amazonaws.com/{2}".format( \
                bucket_name, \
                bucket_location, \
                file_key)
                
                img_url_list.append(object_url)
                logger.info("result_URL: "+ str(object_url))
                value = True
            except ClientError as e:
                logger.error("credential is incorrect!!!!")
                logger.error(e)
            except Exception as e:
                logger.error(e)
        return value, img_url_list

    #upload image from local memory
    def upload2_bucket_from_tmpimage(self, bucket_name, img_arr, key_prefix):
        s3_client = self.s3_client
        value = False
        #save image to binary
        img = Image.fromarray(img_arr)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        hex_data = buffer.getvalue()
         
        img_url_list=[]
        time_stamp = self.get_time_stamp_ms()
        file_key = key_prefix + f'result_{time_stamp}.png'

        try:            
            sent_data = s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=hex_data,  ACL="public-read")
            #s3_client.upload_file(os.path.join(localUploadDir, file), bucket_name, file_key,)
            if sent_data['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise S3ImagesUploadFailed('Failed to upload image {} to bucket {}'.format(file_key, bucket_name))
            #object s3 URL
            
            #upload URL
            location_info = s3_client.get_bucket_location(Bucket=bucket_name)
            bucket_location = location_info['LocationConstraint']
            #logger.info("bucket_location:" + str(bucket_location))
            object_url = "https://{0}.s3.{1}.amazonaws.com/{2}".format( \
            bucket_name, \
            bucket_location, \
            file_key)
            
            img_url_list.append(object_url)
            logger.info("fileURL: " +str (object_url))
            value = True
        except ClientError as e:
            logger.error("credential is incorrect!!!!")
            logger.error(e)
        except Exception as e:
            logger.error(e)
        return value, img_url_list

    def get_safe_ext(self, key):
        ext = os.path.splitext(key)[-1].strip('.').upper()
        if ext in ['JPG', 'JPEG']:
            return 'JPEG' 
        elif ext in ['PNG']:
            return 'PNG' 
        else:
            raise S3ImagesInvalidExtension('Extension is invalid') 


    def get_time_stamp_ms(self, short_format=False):
        if short_format:
            return time.strftime('%Y%m%d-%H%M%S',time.localtime())
        else:
            return time.strftime('%Y%m%d-%H%M%S',time.localtime()) \
                    + '-' + str(time.time()).split('.')[-1][:3]
class S3ImagesInvalidExtension(Exception):
    pass

class S3ImagesUploadFailed(Exception):
    pass

#s3obj = S3Controller()
#key = "itri/device1/202211112222/origin/20200921-113814-889.png"
#img = s3obj.read_img_from_s3("2022-cwa-app-bucket", key)
#key = "itri/device1/202211112222/origin/"
#s3obj.read_imgList_from_s3("2022-cwa-app-bucket", key)
#imgList = s3obj.read_imgList_from_s3("2022-cwa-app-bucket", key)

#for img in imgList:
#    cv2.imshow("img", img)
#    cv2.waitKey(0)