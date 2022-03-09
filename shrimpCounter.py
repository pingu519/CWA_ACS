import cv2
import re
import os
import numpy as np
import statistics
from datetime import datetime
import time
from pathlib import Path
# log
import logging
logger = logging.getLogger(__name__)
FORMAT = '%(asctime)s %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)

class ShrimpCounter():
    def __init__(self):
        self.contours = []
        self.freq = []
        self.boundary = []
        self.cnts_area = []
        self.contours_single = []
        self.cnts_indv_area = []
        self.cnts_area_single = []
        
        self.frame_num = 5
        self.frame_list = []
        # Data processing
        self.accumulated_num = 0
        self.counts_avg = [0, 0]
        self.length_avg = [0, 0]

        # Adjustable parameters
        self.bw_shift = None
        self.pix2mm_ratio = None
        self.count_shift = 0
        self.aspect_ratio = 1.5
        self.contour_area_upper_ratio = 1.5
        self.contour_area_lower_ratio = 0.5
        
        
    def get_download_img_list(self, s3_contents):
        r = re.compile('.*[jpg|jpeg]$')
        tmp_list = []
        for content in s3_contents['Contents']:
            if 'res/' not in content['Key']:
                tmp_list.append(content['Key'])
        s3_img_list = list(filter(r.match, tmp_list))
        lambda_img_list = [os.path.join('/tmp',os.path.basename(f))
                for f in s3_img_list]
        return list(zip(s3_img_list, lambda_img_list))


    def get_upload_img_list(self, lambda_res_img_list, s3_res_path):
        s3_res_img_list = []
        for f in lambda_res_img_list:
            s3_res_img_list.append(
                    os.path.join(s3_res_path, os.path.basename(f)))
      
        return list(zip(lambda_res_img_list, s3_res_img_list))

    def reset_counting(self):
        self.accumulated_num = 0
        self.counts_avg = [0, 0]
        self.length_avg = [0, 0]
    #
    #def get_roi(input_file):
    #    img = cv2.imread(input_file, 1)
    #    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    #    h, w, c = img.shape
        
        # Get ROI
    #    circle_mask = np.zeros((h,w), np.uint8)
    #    cv2.circle(circle_mask, (int(w/2),int(h/2)), int(h/2), 1, -1)
    #    masked_gray = cv2.bitwise_and(gray, gray, mask=circle_mask)

    #    return masked_gray, circle_mask


    def get_roi(self, input):
        #print("type: ",type(input))
        img = None
        if isinstance(input, np.ndarray):
            #print("input is ndarray: ",type(input))
            img = cv2.cvtColor(input, cv2.COLOR_RGB2BGR)  
        else:
            if os.path.exists(input):
                #print("input_path: " + input)
                frame = cv2.imdecode(np.fromfile(input, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  

            
        #img = cv2.imread(input_path, 1)
        h, w, c = img.shape

        # Crop image from (h,w) to (h,h) square
        dw = int((w-h)/2)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = gray[:, dw:dw+h]
        
        # Get ROI
        #circle_mask = np.zeros((h,h), np.uint8)
        #cv2.circle(circle_mask, (int(h/2),int(h/2)), int(h/2), 1, -1) 
        #masked_gray = cv2.bitwise_and(gray, gray, mask=circle_mask)
        
        # Get ROI
        circle_mask = np.zeros((h,h), np.uint8)
        cv2.circle(circle_mask, (int(h/2),int(h/2)), int(h/2), 1, -1)
        masked_gray = cv2.bitwise_and(gray, gray, mask=circle_mask)

        return masked_gray, circle_mask
        
        


    def get_equalization(self, masked_gray):
        tile_grid_size = 16
        clip_limit = 2.0
        clahe = cv2.createCLAHE(
                clipLimit=clip_limit, tileGridSize=(tile_grid_size,tile_grid_size))
        #equ = clahe.apply(gray)
        masked_equ = clahe.apply(masked_gray)
        
        return masked_equ

    def get_bw(self, masked_equ, mask):
        ret, _ = cv2.threshold(masked_equ,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        
        thld_low = ret + self.bw_shift
        thld_high = 255
        _, thresh = cv2.threshold(masked_equ,thld_low,thld_high,cv2.THRESH_BINARY_INV)
        masked_thresh = cv2.bitwise_and(thresh, thresh, mask=mask)
        # Removing noise (TODO)
        kernel = np.ones((3,3),np.uint8)
        masked_thresh = cv2.erode(masked_thresh, kernel, iterations=1)
        masked_thresh = cv2.dilate(masked_thresh, kernel, iterations=3)

        return masked_thresh

    def colorize_contours(self, cnts, canvas):
        if len(canvas.shape) < 3: # 1-channel image
            canvas = cv2.merge((canvas,canvas,canvas))
        for c in self.contours:
            COLORS = (
                    np.random.randint(0,255), 
                    np.random.randint(0,255), 
                    np.random.randint(0,255))
            cv2.drawContours(canvas, [c], -1, COLORS, -1)
        return canvas
    

    def draw_minAreaRect(self, canvas):
        # A temp function for report
        # Crop orig image from (h,w) to (h,h) square
        h, w, c = canvas.shape
        dw = int((w-h)/2)
        canvas = canvas[:, dw:dw+h]
        if len(canvas.shape) < 3: # 1-channel image
            canvas = cv2.merge((canvas,canvas,canvas))
        for cnt in self.contours_single:
            rect = cv2.minAreaRect(cnt)
            (_,_),(_w,_h),_ = rect
            if (_w/_h) > self.aspect_ratio:
                box = np.int0(cv2.boxPoints(rect))
                COLORS = (np.random.randint(0,255), np.random.randint(0,255), np.random.randint(0,255))
                cv2.drawContours(canvas, [box], -1, COLORS, 2)
        return canvas
        
    def get_px_length(self, canvas):
        length = []
        avg_length = 0.0
        if len(canvas.shape) < 3: # 1-channel image
            canvas = cv2.merge((canvas,canvas,canvas))
        for cnt in self.contours_single:
            rect = cv2.minAreaRect(cnt)
            (_,_),(_w,_h),_ = rect
            if (_w/_h) > self.aspect_ratio:
                length.append(_w)
                box = np.int0(cv2.boxPoints(rect))
                COLORS = (np.random.randint(0,255), 
                        np.random.randint(0,255), 
                        np.random.randint(0,255))
                cv2.drawContours(canvas, [box], -1, COLORS, 2)
        try:
            avg_length = np.mean(length)
        except:
            avg_length = 0.0
        if np.isnan(avg_length):
            avg_length = 0.0

        return canvas, avg_length


#    def get_hist(self):
#        #cnts_area = sorted([cv2.contourArea(c) for c in self.contours])
#        self.cnts_area = [cv2.contourArea(c) for c in self.contours]
#        num_bins = len(self.cnts_area)
#        self.freq, self.boundary = np.histogram(self.cnts_area, bins=num_bins)
#        return self.cnts_area, self.freq, self.boundary
        
    def ref_contours(self):
        self.cnts_area = [cv2.contourArea(c) for c in self.contours]
        cnts_area_median = statistics.median(self.cnts_area)
        upper_limit = cnts_area_median * self.contour_area_upper_ratio
        lower_limit = cnts_area_median * self.contour_area_lower_ratio
        self.contours_single = [cnt for cnt in self.contours if cv2.contourArea(cnt) < upper_limit
                and cv2.contourArea(cnt) > lower_limit]
        self.cnts_area_single = [cv2.contourArea(c) for c in self.contours_single]
        
    def get_number(self,cnts):
        self.contours = cnts
        try:
            self.ref_contours()
            ref_area = np.mean(self.cnts_area_single)
            number = np.sum(self.cnts_area)/ref_area
        except:
            number = 0
        if np.isnan(number):
            number = 0
        return number
           
    def do_counting(self, frame):
        self.frame_list.append(frame)
        res_frame = None 
        count = 0
        length = 0
        time_stamp = None
        out_img_list = None
        
        if len(self.frame_list) >= self.frame_num:
            res_frame, count, length, time_stamp, out_img_list = self.get_results(self.frame_list, moving_avg=True)
            self.frame_list.pop(0) #this is better (smoother)        
        
        return res_frame, count, length, time_stamp, out_img_list

    #for AWS
    def get_results(self, frame_list, moving_avg=True, dir ="" ):
        counting_list = []
        length_list = []
        output_img_list = []
        
        #PINGU??
        processed_num = 0
        #counting = 0
        #print("~~~~frame_list" + str(len(frame_list)))
        
        for i_frame, img in enumerate(frame_list):
            #print("~~~~get_results" + img)
            #gray = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
            #img_base, img_ext = os.path.splitext(img)
            #output_img = img_base + '_result' + img_ext
            #output_img_list.append(output_img)
            #cv2.imwrite(output_img, gray)

            masked_gray, circle_mask = self.get_roi(img) #image path or 
            masked_equ = self.get_equalization(masked_gray)
            masked_thresh = self.get_bw(masked_equ, circle_mask)
            cnts, hierarchy = cv2.findContours(
                    masked_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            #List
            count = self.get_number(cnts) + self.count_shift
            counting_list.append(int(count))
            
            filtered_objects, px_length = self.get_px_length(masked_thresh)
            length_list.append(int(px_length))
            
            color_thresh = self.colorize_contours(cnts, masked_thresh)
            color_thresh = self.draw_minAreaRect(color_thresh)
            
            # Results
            res_frame = color_thresh

            counting = np.mean(counting_list)
            length = np.mean(length_list)*self.pix2mm_ratio

        if moving_avg:
            self.accumulated_num += 1

            self.counts_avg[0] = self.counts_avg[1]
            self.counts_avg[1] = (self.counts_avg[0]*(self.accumulated_num-1)
                + counting)/self.accumulated_num
            #if moving_avg on ,then use moving average counting
            counting = self.counts_avg[1]

            self.length_avg[0] = self.length_avg[1]
            self.length_avg[1] = (self.length_avg[0]*(self.accumulated_num-1)
                + length)/self.accumulated_num
            
            #if moving_avg on ,then use moving average length
            length = self.length_avg[1]


        cv2.putText(color_thresh, f'Count:{int(counting):3d}', 
                (10,20), 1, 1.5, (255,255,0), 2)
        cv2.putText(color_thresh, f'Length:{int(length):3d}mm', 
                (10,50), 1, 1.5, (255,255,0), 2)
        
        res_frame = np.hstack(
                (cv2.merge((masked_equ,masked_equ,masked_equ)), color_thresh))
        #cv2.putText(res_frame, '{:3d}'.format(
        #    int(counting)), (700,50), 1, 3, (0,255,255), 2)
        
        #output_img_file = os.path.join(output_path, 'frame_{:06d}.jpeg'.format(i))
        
        #D:\Fish\Fish_counting\fish_counting_system\TempDownloadFile\20200921-113814-889.png

        resultDir = os.path.join(dir , "result\\")

        #make local result dir 
        if not os.path.exists(resultDir):
            os.makedirs(resultDir)
            print("makedirs result directory!!!!!!") 
        
  
        rstImgName = 'result_' + str(processed_num) + ".png"#os.path.basename(img)  
        output_img = resultDir + rstImgName
      
        '''TOOD: maybe add some condition to pick the best output image'''
        if i_frame == (len(frame_list)-1):
            cv2.imwrite(output_img, res_frame)
            output_img_list.append(output_img)
        processed_num += 1
       
       
        current_date = datetime.fromtimestamp(time.time());
        #print("current_date =", current_date)
        time_stamp = str(current_date).split('.')[0]

        return res_frame, counting, length, time_stamp, output_img_list
