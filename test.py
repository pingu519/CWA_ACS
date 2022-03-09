import cv2
import numpy as np
import os
from pathlib import Path 
from pathlib import PureWindowsPath
import time
import datetime
from datetime import datetime
#imgPath = "4.jpg"
'''
imgPath = PureWindowsPath("D:\Fish\Fish_counting\fish_counting_system\TempDownloadFile\20200921-113814-889.png")

print("~~~~~"+str(imgPath))
frame = cv2.imdecode(np.fromfile(imgPath, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  



print("test.py", type(img))
print("test.py", img.shape)
cv2.imshow("img", img)
cv2.waitKey(0)
cv2.destroyAllWindows()
'''
cv2.imshow()
time1 = datetime.fromtimestamp(time.time());
print("time1" + str(time1))
#count, frame_num, lambda_res_img_list = app.cwa.get_results(localImgPathList, moving_avg=True)    
# algorithm
time.sleep(2)

time2 = datetime.fromtimestamp(time.time());
print("time2" + str(time2))
diff = time2-time1
compute_time= diff.total_seconds()
print(f'computeTime: {compute_time} s')