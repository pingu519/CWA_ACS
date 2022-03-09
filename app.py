# -*-coding=utf-8 -*-
import tkinter as tk
from tkinter.filedialog import (
        askdirectory, 
        asksaveasfile,
        asksaveasfilename,
        askopenfilename)
from tkinter import ttk
from tkinter import messagebox 
import threading
import os
import cv2
import numpy
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageColor
from pathlib import Path

import time
from datetime import datetime
import io
from cwa_functions import CWA

# flask
import threading
from flask import Flask, request, Response
from flask import jsonify
import base64
flaskThread = None
ipAdress = '192.168.68.122' #IP adress
flaskobj = Flask(__name__)
#123A
# AWS
import boto3
from botocore.exceptions import ClientError
from s3_controller import S3Controller
bucket_name = "cwaacs"

# log
import logging
logger = logging.getLogger(__name__)
FORMAT = '%(asctime)s %(levelname)s: %(message)s'
#save log file 
#logging.basicConfig(level=logging.INFO, filename='myLog.log', filemode='w', format=FORMAT)
logging.basicConfig(level=logging.INFO, format=FORMAT)

isSaveTestReport = False 

# recording
saveImgTimeInterval = 0.3  # 0.3 seconds...

# for recording image
recording_lock = threading.Lock()

# UI 
frame_window_width=380
frame_window_height=380
window_width= frame_window_width*2 #760
window__height = 680

 
def flaskStart():
    global flaskThread   
    if(flaskThread is None):
        #daemon thread will kill himself when system exits
        flaskThread = threading.Thread(target=flask_function, daemon=True)
        flaskThread.start() 
    
def flask_function():
    global ipAdress   
    flaskobj.run(ipAdress,debug=True,port=5000,use_reloader = False)

# flask hello world 
@flaskobj.route('/', methods=['GET'])
def helloTest():
    now = datetime.now()
    timeString = now.strftime("%Y-%m-%d %H:%M")
        
    response = {'message':f'hello world! {timeString}'}
    return jsonify(response)

# post params and image_list(base64)
@flaskobj.route('/PostImagePC', methods=['POST'])
def PostImagePC(): 
    payload = request.form.to_dict(flat=False)

    bw_shift = payload['bw_shift'][0]
    pix2mm_ratio = payload['pix2mm_ratio'][0]
    count_shift = payload['count_shift'][0]
    frame_num = payload['frame_num'][0]
    #for upload
    company_name = payload['company_name'][0]
    device_name = payload['device_name'][0]
    date = payload['date'][0]
    global bucket_name
    # bucket_name = payload['bucket_name'][0]


    #update UI
    global app
    app.cwa.bw_shift = float(bw_shift)
    app.cwa.pix2mm_ratio = float(pix2mm_ratio)
    app.cwa.count_shift = int(count_shift)
  
    s3controller = S3Controller()

    #image base64
    images_list = payload['img_list']
    if(int(frame_num) != len(images_list)):
        logger.info("frame number does not match !!!")

    time1 = datetime.fromtimestamp(time.time())
    logger.info("algorithm_and_draw start! ")
    for indext, im_b64 in enumerate(images_list):
        im_binary = base64.b64decode(im_b64)
        buf = io.BytesIO(im_binary)
        pilImg = Image.open(buf)
        numpyImg = numpy.asarray(pilImg)
        img = cv2.cvtColor(numpyImg,cv2.COLOR_RGB2BGR)  
        #app.algorithm_and_draw(True, img)
        res_image, count, length, time_stamp, out_img_list = app.algorithm_and_draw(True, img)
    
    logger.info("algorithm_and_draw end! ")

    
    count = int(count)
    logger.info("result  "+ "count: " + str(count) + ", length: " + str(length) + ", time_stamp: " + str(time_stamp) )
    #count, frame_num, lambda_res_img_list = app.cwa.get_results(localImgPathList, moving_avg=True) 
  
    time2 = datetime.fromtimestamp(time.time())
    diff = time2-time1
    compute_time= diff.total_seconds()
    logger.info("computeTime: " + str(compute_time))
  
    #DL_key_prefix = 'company/device_name/date/origin/'
    #UL_key_prefix = 'company/device_name/date/result/'
    UL_key_prefix = company_name + "/" + device_name + "/" + date + "/" + "result/"
    logger.info("UL_key_prefix: " + str(UL_key_prefix))
  
    value, result_img_URL = s3controller.upload2_bucket_from_tmpimage(bucket_name, res_image, UL_key_prefix)


    result = {
        "count_result": count,
        "avg_length": length,
        "compute_time": compute_time,
        "success": value,
        "result_img":result_img_URL        
    }
    
    logger.info("-----------END, success: " + str(value))
    return jsonify(result) 


# 1.post params and s3 bucket images path
# 2.DL S3 bucket image to memory
# 3.algorithm
# 4.UL to s3 bucket 
@flaskobj.route('/PostImageAWS', methods=['POST'])
def PostImageAWS(): 
    payload = request.form.to_dict(flat=False)
    bw_shift = payload['bw_shift'][0]
    pix2mm_ratio = payload['pix2mm_ratio'][0]
    count_shift = payload['count_shift'][0]
    frame_num = payload['frame_num'][0]
    company_name = payload['company_name'][0]
    device_name = payload['device_name'][0]
    date = payload['date'][0]
    global bucket_name
    #bucket_name = payload['bucket_name'][0]
    
    #update UI
    global app
    app.cwa.bw_shift = float(bw_shift)
    app.cwa.pix2mm_ratio = float(pix2mm_ratio)
    app.cwa.count_shift = int(count_shift)
  
    s3controller = S3Controller()
    #DL_key_prefix = 'company/device_name/date/origin/'
    DL_key_prefix = company_name + "/" + device_name + "/" + date + "/" + "original/"
    logger.info("DL_key_prefix: " + str(DL_key_prefix))
    
    
    #key = "itri/device1/202211112222/origin/"
    imgList = s3controller.get_imgList_from_s3(bucket_name, DL_key_prefix)
    logger.info("Aws_Read_S3 size: "+str(len(imgList)))
        
    time1 = datetime.fromtimestamp(time.time())
   
    count = 0
    length = 0
    global res_image
    if(int(frame_num) != len(imgList)):
         logger.info("frame number does not match !!!")
    
    logger.info("algorithm_and_draw start! ")
    for img in imgList: 
        #Algorithm!!!!!!
        res_image, count, length, time_stamp, out_img_list = app.algorithm_and_draw(True, img)
    logger.info("algorithm_and_draw end! ")
    
    count = int(count)
    logger.info("result  "+ "count: " + str(count) + ", length: " + str(length) + ", time_stamp: " + str(time_stamp) )
    #count, frame_num, lambda_res_img_list = app.cwa.get_results(localImgPathList, moving_avg=True) 
  
    time2 = datetime.fromtimestamp(time.time())
    diff = time2-time1
    compute_time= diff.total_seconds()
    logger.info("computeTime: " + str(compute_time))
  
    #DL_key_prefix = 'company/device_name/date/origin/'
    #UL_key_prefix = 'company/device_name/date/result/'
    strDL_key = DL_key_prefix.split('/original/')   #company/device_name/date
    UL_key_prefix = strDL_key[0] + '/result/'
    logger.info("UL_key_prefix: " + str(UL_key_prefix))
  
    value, result_img_URL = s3controller.upload2_bucket_from_tmpimage(bucket_name, res_image, UL_key_prefix)
    
    result = {
        "count_result": count,
        "avg_length": length,
        "compute_time": compute_time,
        "success": value,
        "result_img":result_img_URL        
    }

    
    logger.info("-----------END, success: " + str(value))
    return jsonify(result) 
    
class App(tk.Tk):
    cwa = CWA()
    # Big delay value (e.g., 30) will hang the app when logging raw images.
    delay = 5
    ouput_path = None #cwa.proj_path
    img_path = None #cwa.img_path
    frame_num = cwa.frame_num
    data_num = cwa.data_num
    cam_ip = cwa.cam_ip
    po_no = cwa.po_no
    item_id = cwa.item_id
    data = cwa.data
    data_dict = cwa.data_dict
    log_raw_img_path = cwa.log_raw_img_path
    data2save = []
    # DEBUG
    test_with_img = cwa.test_with_img
    test_img_folder = None #cwa.test_img_folder
    test_images = None
    save_frame_count = 0

    #for recording image
    saveImgThread = None    
    recording_frame = None
    log_raw_img = False
    #log_path_exist_ok = False 
    ipcam = None
    userpanel = None

    def __init__(self):
        super().__init__()
        self.title("CWA Shrimp/Fish Counter")
        windowXpadding, windowYpadding = 0, 0
        self.geometry("%dx%d+%d+%d" % (window_width, window__height, windowXpadding, windowYpadding))
        
        # Create the menu
        menubar = AppMenu(self)
        self.config(menu=menubar)
        self.bind('<Control-o>', menubar.open_output_file)
        self.bind('<Control-s>', menubar.saveas_file)
        self.bind('<Control-q>', quit)
        
        # Disable resizing in a Tkinter Window
        #self.resizable(False, False) 
        # Canvas
        self.imagecanvas = ImageCanvas(self)
        self.imagecanvas.pack(side='top',fill='both',expand=False,
                padx=(5,0),pady=(5,0))

        # Status Bar
        self.statusbar = StatusBar(self)
        self.statusbar.pack(side='bottom',fill='x',expand=False) 

        # User Panel
        self.userpanel = UserPanel(self)
        self.userpanel.pack(side='left',fill='x',expand=True,
                padx=(5,5),pady=(5,5))

        # Video Stream
        # "rtsp://192.168.1.105:8554/unicast"
        self.vid_src = 0 
        self.vid = None

        # Data processing instance
        #self.frame_list = []
        self.res_image = None
        self.res_frame = None
        self.time_stamp = None
        self.csv_fname = None
        self.img_fname = None
             
        #set default spicie to 未知
        spicies = '未知'
        #print("self.cwa.param[spicies]: "+ str(self.cwa.param[spicies]) )
        self.cwa.bw_shift, self.cwa.pix2mm_ratio , self.cwa.count_shift =  self.cwa.param[spicies]
        self.userpanel.bw_shift_scale.set(self.cwa.bw_shift)
        self.userpanel.pix2mm_ratio_scale.set(self.cwa.pix2mm_ratio)
        self.userpanel.count_shift_scale.set(self.cwa.count_shift)
        
        self.run = False
        #self.pause = False
        self.input_ready = False
        self.userpanel.set_btn_state(state=tk.DISABLED)
        # TODO: call update_frame() here?
        #self.update_frame()


    def connect_camera(self, vid_src):
        self.statusbar.status_update(
                status_text=f"Connecting to camera at {vid_src}...")
        # https://stackoverflow.com/a/45648087/9721896
        self.statusbar.update()

        if len(vid_src.split('.')) == 4:
            self.vid_src = "".join(["rtsp://", vid_src, ":8554/unicast"])
            logging.debug(f'Cam IP: {self.vid_src}')
        elif len(vid_src.split('.')) == 1 and vid_src != '': #TODO
            self.vid_src = int(vid_src)
        else: 
            logging.error('Wrong IP camera format')
            return False
            
        if(self.ipcam is None):
            self.ipcam = IpcamCapture(self.vid_src)
            self.ipcam.start()

        self.input_ready = True
        return True
        
        #try:
        #    self.vid = Cv2VideoCapture(self.vid_src)
        #    ret, frame = self.vid.get_frame()
        #    if ret and (frame is not None): 
        #        self.input_ready = True
        #        return True
        #    else:
        #        return False
        #except:
        #    return False

    def disconnect_camera(self):
        #self.vid.close()
        self.input_ready = False
        self.ipcam.stop()
        self.ipcam = None
        #self.log_path_exist_ok = False

    def update_data(self):
        self.data[self.data_dict['po_no']] = self.userpanel.po_no_name.get()
        self.data[self.data_dict['item_id']] = self.userpanel.item_id_name.get()
        data = f"{self.data[self.data_dict['po_no']]}," \
                f"{self.data[self.data_dict['item_id']]}," \
                f"{int(self.data[self.data_dict['count']])}," \
                f"{int(self.data[self.data_dict['length']])}," \
                f"{self.data[self.data_dict['img_fname']]}," \
                f"{self.data[self.data_dict['date_time']]}"

        # update filenames to be saved
        time_str = self.data[self.data_dict['date_time']]
        #self.get_time_stamp(time_str)
        save_fname = f"C_{self.data[self.data_dict['po_no']]}" \
                       f"_{self.data[self.data_dict['item_id']]}" \
                       f"_{self.time_stamp}"
        if(self.ouput_path is not None):
            self.csv_fname = str(Path(self.ouput_path)/save_fname)+'.csv'
            self.img_fname = str(Path(self.ouput_path)/save_fname)+'.png'
            self.data[self.data_dict['img_fname']] = self.img_fname

        # updated data
        logging.debug(data)
        self.data2save.append(data)
        if len(self.data2save) > self.data_num:
            self.data2save.pop(0)

    def get_time_stamp(self, time_str=None):
        if not time_str:
            time_str = str(datetime.fromtimestamp(time())).split('.')[0]
        time_str = time_str.replace(' ','')
        time_str = time_str.replace('-','')
        self.time_stamp = time_str.replace(':','')

    def get_time_stamp_ms(self, short_format=False):
        if short_format:
            return time.strftime('%Y%m%d-%H%M%S',time.localtime())
        else:
            return time.strftime('%Y%m%d-%H%M%S',time.localtime()) \
                        + '-' + str(time.time()).split('.')[-1][:3]

    def do_counting_UI(self, frame):
        res_image, count, length, time_stamp, output_img_list = self.cwa.do_counting(frame)
        self.res_image = res_image
        self.data[self.data_dict['count']] = count
        self.data[self.data_dict['length']] = length
        self.data[self.data_dict['date_time']] = time_stamp
   
        self.update_data()
            
        #PINGU
        if(isSaveTestReport):
            result_pingu = "result_pingu"
            save_fname = str(Path(self.ouput_path)/result_pingu)+'.csv'
            self.userpanel.save_allData_to_csv(save_fname)

        origResizeFrame = cv2.resize(frame,(frame_window_width, frame_window_height),interpolation=cv2.INTER_CUBIC)
        if self.res_image is not None:   
            resResizeFrame = cv2.resize(self.res_image,(frame_window_width, frame_window_height),interpolation=cv2.INTER_CUBIC)
            self.res_frame = np.hstack((origResizeFrame, resResizeFrame))
        else:
            self.res_frame = origResizeFrame
        
        return res_image, count, length, time_stamp, output_img_list 
     
    def get_time_stamp_ms(self, short_format=False):
        if short_format:
            return time.strftime('%Y%m%d-%H%M%S',time.localtime())
        else:
            return time.strftime('%Y%m%d-%H%M%S',time.localtime()) \
                        + '-' + str(time.time()).split('.')[-1][:3]        

    def get_test_img(self):
        try:
            next_img = next(self.test_images)
            #frame = cv2.imread(str(next_img)) # okay for Linux

            # In Windows (sigh...), we need to use the following code to read 
            # images from unicode path.
            # ref: https://jdhao.github.io/2019/09/11/opencv_unicode_image_path/
            frame = cv2.imdecode(np.fromfile(next_img, dtype=np.uint8), 
                    cv2.IMREAD_UNCHANGED)
            #self.statusbar.status_update(status_text=
            #        f"{self.cwa.accumulated_num:5d}: {str(next_img)}")
            #PINGU
            self.userpanel.latest_test_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return (True, self.userpanel.latest_test_frame)
            #return (True, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        except:
            logging.error('get_test_img: Cannot get image...')
            messagebox.showerror("Image Loading Failed", 
                "Cannot load the test images.")
            return (False, None)
            
            
    def update_frame(self):
        if self.run:
            if self.input_ready:
                if self.test_with_img:
                    ret, frame = self.get_test_img()
                else:
                    ret, frame = self.ipcam.getframe() #read from IP camera
                
                #PINGU
                self.algorithm_and_draw(ret, frame)
                                    
            else:
               self.imagecanvas.clear_canvas()
                      
            self.after(self.delay, self.update_frame)
        

                                               
    def algorithm_and_draw(self, ret, frame):
        #print("algorithm_and_draw")
        if ret :
            self.userpanel.log_img_btn.config(state=tk.NORMAL)
            res_image, count, length, time_stamp, out_img_list = self.do_counting_UI(frame)
                       
            recording_lock.acquire() 
            self.recording_frame = frame.copy()
            recording_lock.release()
            
            _process_status = f'{self.cwa.accumulated_num:5d} '\
                    f'frames have been processed...'
            self.statusbar.status_update(status_text=_process_status)
                    
        #elif ret:
        #    try: # show realtime frame with final ressult image (res_image)
        #        self.res_frame = np.hstack((frame, self.res_image))
                
        #     except: # show only the realtime frame
        #        self.res_frame = frame
        else: # (possible) camera input error, reset the proccess...
            self.input_ready = False
            self.userpanel.disconnect_cam()
            self.userpanel.reset_process()
            logging.error('update_frame: No frame input...')
            messagebox.showerror("Frame update failed", 
                    "No frame input. Please check the network and reconnect the camera.")

        self.photo = ImageTk.PhotoImage(Image.fromarray(self.res_frame))
        self.imagecanvas.show_image(self.photo)
        
        return res_image, count, length, time_stamp, out_img_list

class AppMenu(tk.Menu):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        # File menu bar
        filemenu = tk.Menu(self, tearoff=True)
        self.add_cascade(label='File', 
                underline=0,
                menu=filemenu)
        filemenu.add_command(label='Set output result folder', 
                underline=0,
                command=self.open_output_file,
                accelerator='Ctrl+O')
        filemenu.add_command(label='Save as', 
                underline=1,
                command=self.saveas_file,
                accelerator='Ctrl+S')
        filemenu.add_separator()
                
        #PINGU
        if(self.root.test_with_img):
            filemenu.add_command(label='Open test image file', 
                    underline=0,
                    command=self.open_test_image_file)
        
        filemenu.add_command(label='Exit', 
                underline=1,
                command=quit,
                accelerator='Ctrl+Q')
                                
    #PINGU
    def open_test_image_file(self, event='open_test_image_file'):
        dir_path = askdirectory(title='Select test image folder',
            initialdir=Path.cwd())
        if dir_path:
            if Path(dir_path).is_dir():
                self.root.test_img_folder = dir_path
                if self.root.test_with_img and (self.root.test_img_folder is not None):
                    self.root.userpanel.load_test_img_btn.config(state=tk.NORMAL)
        logger.info(f'Set test image folder to {self.root.test_img_folder}')


    def open_output_file(self, event='open_output_file'):
        ouput_path = askdirectory(title='Select output folder',
                initialdir=Path.cwd())
        if ouput_path is not None:
            if Path(ouput_path).is_dir():
                self.root.ouput_path = ouput_path
        logger.info(f'Set output path to {self.root.ouput_path}')

    def saveas_file(self, event='saveas_file'):
        saveas_log = asksaveasfilename(title='Save result as',
                initialdir=self.root.ouput_path,
                filetypes = (
                    ("csv files","*.csv"),
                    ("txt files","*.txt"),
                    ("xls files","*.xls"),
                    ("all files","*.*"))
                )
        self.root.userpanel.save_result(filename=saveas_log)


class ImageCanvas(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        global frame_window_width, frame_window_height
        self.root = root
        self.canvas = tk.Canvas(self, background='black',width=frame_window_width, height=frame_window_height)
        w = int((window_width-frame_window_width*2)/2) 
        #self.img_on_canvas = self.canvas.create_image(
        #        0,0,image=None,anchor='nw')#, state=tk.DISABLED)
        self.img_on_canvas = self.canvas.create_image(
                w,0,image=None,anchor='nw')#, state=tk.DISABLED)
        self.canvas.pack(side='left', fill='both', expand=True)

    def show_image(self, img):
        self.canvas.itemconfig(self.img_on_canvas, image=img, state='normal')

    def clear_canvas(self):
        self.canvas.itemconfig('all', state='hidden')


class UserPanel(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root

        self.input_group = tk.Frame(self, border=0, relief=tk.GROOVE,
                padx=5, pady=5)
        self.input_group.pack(side='left')

        # Input Entries
        textLength = 18
        rowIndex = 0
        mpadx = 5
        mpady = 1
        # connect cam
        if (self.root.test_with_img):
            self.load_test_img_btn = ttk.Button(self.input_group,
                    text='Load images', command=self.load_test_img, 
                    state=tk.DISABLED)
            self.load_test_img_btn.grid(row=rowIndex,column=0,columnspan=2,padx=mpadx,pady=mpady,sticky=tk.W)            
            self.stop_load_test_img_btn = ttk.Button(self.input_group,
                    text='Stop loading', command=self.stop_load_test_img)
            self.stop_load_test_img_btn.grid(row=rowIndex,column=0,columnspan=2,padx=mpadx,pady=mpady,sticky=tk.W)
            self.stop_load_test_img_btn.grid_remove()  
            rowIndex = rowIndex + 1
        else:           
            self.cam_ip_label = ttk.Label(self.input_group, text='Camera IP')
            self.cam_ip_label.grid(row=rowIndex,column=0,sticky=tk.W,padx=mpadx,pady=mpady)
            self.cam_ip = tk.StringVar(self, value=self.root.cam_ip)
            self.cam_ip_entry = tk.Entry(
                    self.input_group, textvariable = self.cam_ip,width=textLength)
            self.cam_ip_entry.grid(row=rowIndex,column=1,sticky=tk.W)     
            rowIndex = rowIndex + 1
            
            self.cam_btn = ttk.Button(self.input_group, text='Connect', 
                    command=self.connect_cam, state=tk.NORMAL)
            self.cam_btn.grid(row=rowIndex,column=0,sticky=tk.EW,padx=mpadx,pady=0)
            self.discam_btn = ttk.Button(self.input_group, text='Disconnect', 
                    command=self.disconnect_cam)
            self.discam_btn.grid(row=rowIndex,column=0,sticky=tk.EW,padx=mpadx,pady=0)
            self.discam_btn.grid_remove()
            rowIndex = rowIndex + 1
        
       
        mpadx = 5
        mpady = 0
        self.po_no_label = ttk.Label(self.input_group, text='PO No.')
        self.po_no_label.grid(row=rowIndex,column=0,sticky=tk.W,padx=mpadx,pady=mpady)
        self.po_no_name = tk.StringVar(self, value=self.root.po_no)
        self.po_no_entry = tk.Entry(
                self.input_group, textvariable=self.po_no_name,width=textLength)
        self.po_no_entry.grid(row=rowIndex,column=1,sticky=tk.W,padx=mpadx,pady=mpady)
        rowIndex = rowIndex + 1

        self.item_id_label = ttk.Label(self.input_group, text='Item ID')
        self.item_id_label.grid(row=rowIndex,column=0,sticky=tk.W,padx=mpadx,pady=mpady)
        self.item_id_name = tk.StringVar(self, value=self.root.item_id)
        self.item_id_entry = tk.Entry(
                self.input_group, textvariable = self.item_id_name,width=textLength)
        self.item_id_entry.grid(row=rowIndex,column=1,sticky=tk.W,padx=mpadx,pady=mpady)
        rowIndex = rowIndex + 1
        # Item Selection Menu
        #--- tk/ttk OptionMenu version ---
        #spicies = tk.StringVar(self)
        ##spicies.set(self.root.item_spicies[0]) # for tk.OptionMenu
        ## For ttk OptionMenu, we have to put the default value in the 
        ## arguments, or the first item will disappear.
        ## https://stackoverflow.com/a/25217981/9721896
        #self.item_spicies_menu = ttk.OptionMenu(self.input_group,
        #        spicies, 
        #        self.root.item_spicies[0],
        #        *(self.root.item_spicies),
        #        command=self.set_spicies)
        #self.item_spicies_menu.grid(row=1,column=2)
        #--- ttk Combobox version ---
        self.item_spicies_label = ttk.Label(self.input_group, text='Spicies')
        self.item_spicies_label.grid(row=rowIndex,column=0,sticky=tk.W,padx=mpadx,pady=mpady+2)
        self.item_spicies_menu = ttk.Combobox(self.input_group,
                #value=self.root.item_spicies,
                value=list(self.root.cwa.param.keys()),
                width=textLength-2)
        self.item_spicies_menu.current(0)
        self.item_spicies_menu.bind('<<ComboboxSelected>>', self.set_spicies)
        self.item_spicies_menu.grid(row=rowIndex,column=1,sticky=tk.W,padx=mpadx,pady=mpady+2)
        rowIndex = rowIndex + 1

        # Input Buttons
        #PINGU
        self.latest_test_frame = None
        mpadx = 10
        mpady = 1
        #PINGU bw_shift scale
        self.bw_shift_label = ttk.Label(self.input_group, text = "bw_shift: " + str(self.root.cwa.bw_shift))
        self.bw_shift_label.grid(row=0,column=3,padx=mpadx,pady=mpady,sticky=tk.SW)
       
        self.bw_shift_scale = tk.Scale(self.input_group, orient=tk.HORIZONTAL, \
        from_=0.0, to=50.0, tickinterval=10, resolution=.1, width=10, length=180, command = self.toggle_bw_shift_scale)
        self.bw_shift_scale.grid(row=1,column=3,padx=mpadx,pady=mpady,sticky=tk.W)

        #PINGU pix2mm_ratio scale
        self.pix2mm_ratio_label = ttk.Label(self.input_group, text = "pix2mm_ratio: " + str(self.root.cwa.pix2mm_ratio)) #,background ='#FFFAFA'
        self.pix2mm_ratio_label.grid(row=2,column=3,padx=mpadx,pady=mpady,sticky=tk.SW)
       
        self.pix2mm_ratio_scale = tk.Scale(self.input_group, orient=tk.HORIZONTAL, \
        from_=0.0, to=5.0, tickinterval=1, resolution=.1, width=10, length=180, command = self.toggle_pix2mm_ratio_scale)
        self.pix2mm_ratio_scale.grid(row=3,column=3,padx=mpadx,pady=mpady,sticky=tk.W)
        self.root.pause = False
        

        #PINGU test image file name
        self.test_img_folder_label = ttk.Label(self.input_group, text = "test_img_folder: " + str(self.root.test_img_folder))
        self.test_img_folder_label.grid(row=0,column=4,padx=mpadx,pady=mpady,sticky=tk.W)
        self.test_img_folder_label.grid_remove()
        
        
        #PINGU count_shift
        self.count_shift_label = ttk.Label(self.input_group, text = "count shift: " + str(self.root.cwa.count_shift))
        self.count_shift_label.grid(row=1,column=4,padx=mpadx,pady=mpady,sticky=tk.SW)
       
        self.count_shift_scale = tk.Scale(self.input_group, orient=tk.HORIZONTAL, \
        from_=-30.0, to=30.0, tickinterval=10, resolution=1, width=10, length=160, command = self.toggle_count_shift_scale)
        self.count_shift_scale.grid(row=2,column=4,padx=mpadx,pady=mpady,sticky=tk.W)
              

        # Output Buttons
        self.output_group = tk.Frame(self, border=0, relief=tk.GROOVE,
                padx=1, pady=5)
        self.output_group.pack(side='right', anchor=tk.SE)

        self.run_btn = ttk.Button(self.output_group, text='Run', 
                command=self.do_processing, state=tk.DISABLED)
        self.run_btn.grid(row=0,column=3,sticky=tk.E,ipadx=1,ipady=1,padx=1,pady=1)
        
        self.pause_btn = ttk.Button(self.output_group, text='Pause', 
                command=self.pause_processing)
        self.pause_btn.grid(row=0,column=3,sticky=tk.E,ipadx=1,ipady=1,padx=1,pady=1)
        self.pause_btn.grid_remove()
        
        #PINGU
        #self.pause_btn = ttk.Button(self.output_group, text='Pause', 
        #        command=self.toggle_pause)
       
        #self.pause_btn.grid(row=0,column=2,sticky=tk.E)
        
        self.save_btn = ttk.Button(self.output_group, text='Save', 
                command=self.save_result, state=tk.DISABLED)
        self.save_btn.grid(row=1,column=3,sticky=tk.E,ipadx=1,ipady=1,padx=1,pady=1)

        self.reset_btn = ttk.Button(self.output_group, text='Reset', 
                command=self.reset_process, state=tk.DISABLED)
        self.reset_btn.grid(row=2,column=3,sticky=tk.E,ipadx=1,ipady=1,padx=1,pady=1)
        #self.root.pause = False
        # DEBUG: for saving raw images
    
        #self.run_btn.grid_remove()
        self.log_img_btn = ttk.Button(self.output_group, 
                text='Log Image', command=self.save_raw_img,
                state=tk.DISABLED)
        self.log_img_btn.grid(row=3,column=3,sticky=tk.E,ipadx=1,ipady=1,padx=1,pady=1)
        
        self.stop_log_img_btn = ttk.Button(self.output_group, 
                text='Stop Log', command=self.stop_save_raw_img)
        self.stop_log_img_btn.grid(row=3,column=3,sticky=tk.E,ipadx=1,ipady=1,padx=1,pady=1)
        self.stop_log_img_btn.grid_remove()

      
        
    #Pingu
    def toggle_bw_shift_scale(self, v):
        self.root.cwa.bw_shift = self.bw_shift_scale.get()
        self.bw_shift_label.config(text = "bw_shift: " + str(self.root.cwa.bw_shift))
        if(self.latest_test_frame is not None):
            self.root.algorithm_and_draw(True, self.latest_test_frame)
    #Pingu
    def toggle_pix2mm_ratio_scale(self, v):
        self.root.cwa.pix2mm_ratio = self.pix2mm_ratio_scale.get()
        self.pix2mm_ratio_label.config(text = "pix2mm_ratio: " + str(self.root.cwa.pix2mm_ratio))
        if(self.latest_test_frame is not None):
            self.root.algorithm_and_draw(True, self.latest_test_frame)
            
    #Pingu
    def toggle_count_shift_scale(self, v):
        self.root.cwa.count_shift = self.count_shift_scale.get()
        self.count_shift_label.config(text = "count_shift: " + str(self.root.cwa.count_shift))

              
        
    def set_spicies(self, event='set_spicies'):
        spicies = self.item_spicies_menu.get()
        self.root.cwa.bw_shift, self.root.cwa.pix2mm_ratio, self.root.cwa.count_shift = \
                self.root.cwa.param[spicies]

        _status_str = f'set_spicies: Set parameters as:'\
                f'bw_shift = {self.root.cwa.bw_shift}, '\
                f'pix2mm_ratio = {self.root.cwa.pix2mm_ratio}, ' \
                f'count_shift = {self.root.cwa.count_shift}'
        self.root.statusbar.status_update(status_text=_status_str)
        logger.info(_status_str)

        if self.root.test_with_img and (self.root.test_img_folder is not None):
            self.load_test_img_btn.config(state=tk.NORMAL)
        else:
            if hasattr(self,'cam_btn'):
                self.cam_btn.config(state=tk.NORMAL)
        #update param UI
        self.bw_shift_scale.set(self.root.cwa.bw_shift)
        self.pix2mm_ratio_scale.set(self.root.cwa.pix2mm_ratio)
        self.count_shift_scale.set(self.root.cwa.count_shift)
        
    def set_btn_state(self, state=tk.NORMAL):
        #self.pause_btn.config(state=state)
        self.log_img_btn.config(state=state)
        self.run_btn.config(state=state)
        self.save_btn.config(state=state)
        self.reset_btn.config(state=state)
        
        #self.load_test_img_btn.grid_remove()
        #self.stop_load_test_img_btn.grid()

    #def set_btn_state(self, state=tk.NORMAL):
        #FIX: bad control flow here...
        #self.run_btn.config(state=state)
        #self.save_btn.config(state=state)
        #self.reset_btn.config(state=state)
        
    #def toggle_btn_state(self, state=tk.NORMAL): #pause(run), log image(run) ,run,save,reset
    #    #FIX: bad control flow here...
    #    #self.run_btn.config(state=tk.NORMAL)
    #    self.pause_btn.config(state=state)
    #    self.log_img_btn.config(state=state)
    #    
    #    self.run_btn.config(state=state)
    #    self.save_btn.config(state=state)
    #    self.run_btn.config(state=state)
    #    
    #    if(state=tk.NORMAL):
    #    
        #if self.root.log_raw_img:
        #    self.log_img_btn.config(state=state)
        #    self.stop_log_img_btn.config(state=state)
        #
        #if state == tk.DISABLED: #revert to default buttons
        #    if self.root.log_raw_img:
        #        self.stop_log_img_btn.grid_remove()
        #        self.log_img_btn.grid()
        #    else:
        #        self.save_btn.grid_remove()
        #        self.run_btn.grid()

    def connect_cam(self):
        self.cam_btn.grid_remove()
        self.discam_btn.grid()

        self.cam_ip = self.cam_ip_entry.get()
        cam_state = self.root.connect_camera(self.cam_ip)
        if cam_state:
            self.root.statusbar.status_update(
                status_text=f"Camera connected at {self.cam_ip}.")
            self.run_btn.config(state=tk.NORMAL)
            self.set_btn_state(state=tk.NORMAL)
        else:
            messagebox.showerror("Camera Connection Failed", 
                "Make sure you are in the same domain of the camera "
                "and have the right IP address.")

   
    def disconnect_cam(self):
        self.set_btn_state(state=tk.DISABLED)
        self.discam_btn.grid_remove()
        self.cam_btn.grid()
        self.pause_processing()
        self.root.disconnect_camera()
        self.set_btn_state(state=tk.DISABLED)

    def load_test_img(self):
        _p = Path(self.root.test_img_folder)
        if _p.is_dir():
            self.root.statusbar.status_update(
                    status_text=f"Open test image folder: {_p}...")
        else:
            self.root.test_img_folder = askdirectory(
                    title='Select image folder', initialdir=Path.cwd())
        
        if(self.root.test_img_folder is not None):
            self.root.test_images = Path(self.root.test_img_folder).glob('*.*')
            self.root.input_ready = True

        #self.run_btn.config(state=tk.NORMAL)
        #?
        self.load_test_img_btn.grid_remove()
        self.stop_load_test_img_btn.grid()
        
        #PINGU
        self.set_btn_state(state=tk.NORMAL)
        logger.info("PINGU_test_img_folder:" + str(self.root.test_img_folder))
        #-----------------------
        head, tail = head, tail = os.path.split(self.root.test_img_folder)
        self.test_img_folder_label.config(text = "test file: " + str(tail))
        self.test_img_folder_label.grid()
        self.do_processing()

    def stop_load_test_img(self):
        self.set_btn_state(state=tk.DISABLED)
        self.stop_load_test_img_btn.grid_remove()
        self.load_test_img_btn.grid()
        self.pause_processing()
        self.root.input_ready = False
        self.set_btn_state(state=tk.DISABLED)

    def do_processing(self):
        self.run_btn.grid_remove()
        self.pause_btn.grid()
        #self.save_btn.config(state=tk.DISABLED)
        self.root.run = True
        self.root.after(self.root.delay, self.root.update_frame)


    def pause_processing(self):
        self.pause_btn.grid_remove()
        self.set_btn_state(state=tk.NORMAL)
        self.run_btn.grid()
        self.root.statusbar.status_update(status_text="Process pause...")
        self.root.run = False
        
    def save_result(self, filename=None):
        self.root.update_data()

        if filename:
            self.csv_fname = filename
        else:
            self.csv_fname = self.root.csv_fname

        if(self.root.csv_fname is not None):
            with open(self.csv_fname, 'w') as f:
                f.write(','.join(list(self.root.data)))
                f.write('\n')
                for data in self.root.data2save:
                    f.write(f"{data}\n")     
                logger.info(f'Result csv file has been saved to {self.root.img_fname} ...')
        
        if(self.root.img_fname is not None):
            Image.fromarray(self.root.res_frame).save(self.root.img_fname)
            logger.info(f'Result frame has been saved to {self.root.img_fname} ...')
        
        if(self.root.img_fname is None or self.root.csv_fname is None):
            messagebox.showinfo("Result NOT Saved", "Please set the output file path")
        else:
            messagebox.showinfo("Result Saved", 
                    f"Results has been saved to {self.csv_fname}, "\
                    f"and the image has been saved to {self.root.img_fname} ...")
    
    def save_raw_img(self):
        p = Path(self.root.log_raw_img_path)
        
        try:
            p.mkdir(parents=True, exist_ok=True)
            #self.root.log_path_exist_ok = True
            #self.root.run = True
        except:
            ret = messagebox.askyesno("Folder exist", 
                "Save the images in existing folder?"
                + "(Press 'No' to set new path)")
            if ret is True:
                #self.root.log_path_exist_ok = True
                p.mkdir(parents=True, exist_ok=True)
                logging.debug('Use existing folder to save the images...')
                #self.root.do_recording()
                #self.root.run = True
            else:
                self.stop_save_raw_img()
                logging.debug('Back to set image folder path...')

        self.log_img_btn.grid_remove()
        self.stop_log_img_btn.grid()
        
        #Save image data
        #p = Path(self.root.img_path)/ \
        #        self.po_no_name.get()/ \
        #        self.item_id_name.get()
        #self.root.log_raw_img_path = p

        # Call work function
        self.root.log_raw_img = True
        #self.root.log_raw_img_path = Path("E://test//fish")   
        if(self.root.saveImgThread is None):
            self.root.saveImgThread = threading.Thread(target = self.saveIamgeWork)
            self.root.saveImgThread.start()
     
    def saveIamgeWork(self):
        if Path(self.root.log_raw_img_path).is_dir():
            while(self.root.log_raw_img):
                logger.info("I am in saveIamgeWork!!!")
                recording_lock.acquire() 
                time_stamp = self.root.get_time_stamp_ms()
                img_f = f'frame_{time_stamp}.png'
                img_file_name = str(Path(self.root.log_raw_img_path)/img_f)
                logger.info(str(img_file_name))
                logging.debug(f'Saving {img_file_name}')
                Image.fromarray(self.root.recording_frame).save(img_file_name)
                recording_lock.release() 
                logger.info("before saveImgTimeInterval: " + f'{time_stamp}')
                time.sleep(saveImgTimeInterval) 
                time_stamp = self.root.get_time_stamp_ms()                
                logger.info("after saveImgTimeInterval: " + f'{time_stamp}')
        else:
            logging.error('log_raw_img_path does not exit')
            
    def stop_save_raw_img(self):
        self.root.log_raw_img = False
        if self.root.saveImgThread is not None:
            self.root.saveImgThread.join()
            self.root.saveImgThread = None
        self.stop_log_img_btn.grid_remove()
        self.log_img_btn.grid()
        #self.root.log_path_exist_ok = False
        #self.root.run = False
    

    def save_allData_to_csv(self, filename=None):
        self.root.update_data()
        
        with open(filename, 'a') as f:
            for data in self.root.data2save:
                self.root.save_frame_count = self.root.save_frame_count + 1 
                f.write(f"{self.root.save_frame_count}")
                f.write(',')
                f.write(f"{data}\n")
               

    def reset_process(self):
        #PINGU
        #self.root.res_image = None
        self.root.cwa.reset_counting()
        _status_str = 'Reset the counting process ...'
        self.root.statusbar.status_update(status_text=_status_str)
        logger.info(_status_str)


class StatusBar(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root

        self.show_process = ttk.Label(self, 
                background='#333333', foreground='#cccccc',
                text='Status information')
        self.show_process.pack(side='left',fill='x',expand=True)

    def status_update(self, status_text):
        self.show_process.config(text=status_text)


class Cv2VideoCapture:
    #https://solarianprogrammer.com/2018/04/21/python-opencv-show-video-tkinter-window/
    def __init__(self, video_source=0):
        # Open the video source
        self.vid = cv2.VideoCapture(video_source)
        if not self.vid.isOpened():
            raise ValueError("Unable to open video source", video_source)
        # Get video source width and height
        self.width = self.vid.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT)
 
    def get_frame(self):
        if self.vid.isOpened():
            ret, frame = self.vid.read()
            if ret:
                return (ret, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            else:
                return (ret, None)
        else:
            #return (ret, None)
            return (None, None)
 
    # Release the video source when the object is destroyed
    def __del__(self):
        if self.vid.isOpened():
            self.vid.release()

    def close(self):
        if self.vid.isOpened():
            self.vid.release()
            
# IP camera
class IpcamCapture:
    def __init__(self, URL):
        self.Frame = None
        self.status = False
        self.isstop = False
		
        #camera connect
        self.capture = cv2.VideoCapture(URL)
        logger.info(f'URL: {URL}')
        if not self.capture.isOpened():
            raise ValueError("Unable to open camera", video_source)
        
        self.width = self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def start(self):
        #thread daemon will close itself when main procssing close
        logger.info('ipcam started!')
        threading.Thread(target=self.queryframe, daemon=True, args=()).start()

    def stop(self):
        self.isstop = True
        logger.info('ipcam stopped!')
   
    def getframe(self):
        #print('IpcamCapture getframe: ')
        colorImg =  cv2.cvtColor(self.Frame.copy(), cv2.COLOR_BGR2RGB)
        #resize
        img_frame_width = 480
        img_frame_height = 480
        colorImg = cv2.resize(colorImg, (img_frame_width, img_frame_height), interpolation=cv2.INTER_CUBIC)
        height = colorImg.shape[0]
        width = colorImg.shape[1]
        channels = colorImg.shape[2]
        return (self.status, colorImg)
        
    def queryframe(self):
        while (not self.isstop):
            self.status, self.Frame = self.capture.read()
        
        self.capture.release()
        
    
if __name__ == '__main__':
    #flask first
    flaskStart()
    
    #global app
    app = App()
    app.mainloop()

