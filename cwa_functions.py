import cv2
import numpy as np
import yaml
import csv
from time import time
from datetime import datetime
from shrimpCounter import ShrimpCounter

class CWA(ShrimpCounter):
    data_dict = {'po_no': 'PO_NO',
            'item_id': 'ITEM_ID',
            'count': 'COUNT_RESULT',
            'length': 'AVG_BODY_LENGTH',
            'img_fname': 'RESULT_IMAGE_FILENAME',
            'date_time': 'MEASURE_TIME',
            }
    data = {'PO_NO': None,      # user input, str
            'ITEM_ID': None,    # user input, str
            'COUNT_RESULT': None,      # integer
            'AVG_BODY_LENGTH': None,     # mm
            'RESULT_IMAGE_FILENAME': None,
            'MEASURE_TIME': None,  # yyyy/mm/dd HH:MM:ss
            }

    def __init__(self):
        super().__init__()
        with open('config.yaml', encoding='utf-8', mode='r') as f:
            self.config = yaml.safe_load(f)
        #self.proj_path = self.config['proj_path']
        #self.img_path = self.config['img_path']
        self.test_with_img = self.config['test_with_img']
        self.log_raw_img_path = self.config['log_raw_img_path']
        #PINGU
        #self.test_img_path = self.config['test_img_path']
        self.test_img_path = None
        self.frame_num = self.config['frame_num']
        self.data_num = self.config['data_num']
        self.cam_ip = self.config['cam_ip']
        self.po_no = self.config['po_no']
        self.item_id = self.config['item_id']

        self.param = {}
        with open('param.csv', encoding='utf-8', mode='r') as f:
            reader = csv.reader(f)
            for k, v1, v2, v3 in reader:
                self.param[k] = (float(v1), float(v2), float(v3))

        # Data processing
        self.accumulated_num = 0
        self.counts_avg = [0, 0]
        self.length_avg = [0, 0]

    def reset_counting(self):
        self.accumulated_num = 0
        self.counts_avg = [0, 0]
        self.length_avg = [0, 0]

    #def image_process(self, frame):
    #    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #    edges = cv2.Canny(frame, 100, 200)
    #    return edges

    #def test(self, frame_list):
    #    for i, frame in enumerate(frame_list):
    #        print(i, frame.shape)

    # for GUI PC version
#    def get_results(self, frame_list, moving_avg=True):
#        counting_list = []
#        length_list = []
#        for frame in frame_list:
#            masked_gray, circle_mask = self.get_roi(
#                    input_file=None, input_img=frame)
#            masked_equ = self.get_equalization(masked_gray)
#            masked_thresh = self.get_bw(masked_equ, circle_mask)
#            cnts, hierarchy = cv2.findContours(
#                    masked_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
#
#            #List
#            #counting = self.get_number(cnts)
#            #PINGU
#            counting = self.get_number(cnts) + self.count_shift
#            counting_list.append(int(counting))
#
#            filtered_objects, px_length = self.get_px_length(masked_thresh)
#            length_list.append(int(px_length))
#
#        color_thresh = self.colorize_contours(masked_thresh)
#        color_thresh = self.draw_minAreaRect(color_thresh)
#
#        # Results
#        res_frame = color_thresh
#
#        counting = np.mean(counting_list)
#        length = np.mean(length_list)*self.pix2mm_ratio
#
#        if moving_avg:
#            self.accumulated_num += 1
#
#            self.counts_avg[0] = self.counts_avg[1]
#            self.counts_avg[1] = (self.counts_avg[0]*(self.accumulated_num-1)
#                + counting)/self.accumulated_num
#            counting = self.counts_avg[1]
#
#            self.length_avg[0] = self.length_avg[1]
#            self.length_avg[1] = (self.length_avg[0]*(self.accumulated_num-1)
#                + length)/self.accumulated_num
#            length = self.length_avg[1]
#
#        cv2.putText(res_frame, f'Count:{int(counting):3d}', 
#                (10,20), 1, 1.5, (255,255,0), 2)
#        cv2.putText(res_frame, f'Length:{int(length):3d}mm', 
#                (10,50), 1, 1.5, (255,255,0), 2)
#
#        time_stamp = str(datetime.fromtimestamp(time())).split('.')[0]
#
#        return res_frame, counting, length, \
#                time_stamp
#
#        