import serial
import tkinter as tk
from tkinter import Scale, Canvas, Button, Entry, Label
from PIL import Image, ImageTk, ImageDraw
import time
from picamera2 import Picamera2, Preview
from picamera.array import PiRGBArray
import matplotlib as plt
import numpy as np
import RPi.GPIO as gp
import os
from threading import Thread

ser = None
current_x = 0
current_y = 0
current_z = 0
max_limit = 150  # Maximaler Grenzwert für X und Y
min_z_limit = 0  # Minimaler Grenzwert für die Z-Achse
z_scale = None  # Z-Achsen-Slider hinzugefügt
canvas = None  # Initialisieren Sie canvas außerhalb der Funktion
tk_image=None
image=1
sample_rate=1
sum_x = 0
sum_y = 0
image = 1
is_active = False
bild_pfad = "/home/pi/Logo_MiltenyiBiotec.jpg"

adapter_info = {"A": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x04", "gpio_sta": [0, 0, 1],}, 
                "B": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x05","gpio_sta": [1, 0, 1],},
                "C": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x06","gpio_sta": [0, 1, 0],},
                "D": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x07","gpio_sta": [1, 1, 0],}
                }
                
gp.setwarnings(False)
gp.setmode(gp.BOARD)
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)



def select_camera(index):
    channel_info = adapter_info.get(index)
    gpio_sta = channel_info["gpio_sta"]  # gpio write
    gp.output(7, gpio_sta[0])
    gp.output(11, gpio_sta[1])
    gp.output(12, gpio_sta[2])
    os.system(channel_info["i2c_cmd"])  # i2c write

def open_serial_connection():
    global ser
    ser = serial.Serial(
        port='/dev/ttyUSB0',
        baudrate=250000,
        bytesize=8,
        timeout=2,
        stopbits=serial.STOPBITS_ONE
    )

def exit_program():
        root.destroy()

def send_cmd(command):
    formatted_command = f"{command}\r\n".upper()
    ser.write(formatted_command.encode())

def move_xyz(x, y, z):
    global current_x, current_y, current_z
    current_x, current_y, current_z = x, y, z
    send_cmd(f"G1 X{x} Y{y} Z{z}")


def reference_position():
    send_cmd("G28")
    #Positionierung
    move_xyz(160, 0, 150)
    move_xyz(160, 127, 150)
    

def workflow(x, y, z, width, height, speed, radius):

    move_xyz(x, y, z + 12)

    #Kleben 1
    send_cmd(f"M0 S1")
    send_cmd(f"M104 S100")
    move_xyz(x+radius, y, z)
    send_cmd(f"G1 F{speed}")
    
    move_xyz(x + width - radius, y, z)
    send_cmd(f"G3 X{x+width} Y{y + radius} I{0} J{radius}")
    move_xyz(x + width, y + height- radius, z)
    send_cmd(f"G3 X{x+width-radius} Y{y + height} I{-radius} J{0}")
    move_xyz(x + radius, y + height, z)
    send_cmd(f"G3 X{x} Y{y + height-radius} I{0} J{-radius}")
    move_xyz(x, y+radius, z)
    send_cmd(f"G3 X{x+radius} Y{y} I{radius} J{0}")
    send_cmd(f'M0 P100')
    send_cmd(f'M104 S0')
    send_cmd(f'G1 F1000')
    move_xyz(x, y, z+30)
    move_xyz(x, y+60, z+30)

    time.sleep(2)
    
    

def fenster(x, y, z, width, height, speed, radius):
    move_xyz(x-22, y, z+10)
    move_xyz(x-22, y+183, z+10)
    move_xyz(x-22, y+183, 1)
    send_cmd(f"M106")
    move_xyz(x-18.55, y+183, z+10)
    move_xyz(x-18.55, y-6.8, z+10)
    move_xyz(x-18.55, y-6.8, z-16)
    send_cmd(f"M107")
    move_xyz(x-18.55, y-7.0, z+10)
    move_xyz(x-18.55, y+75, z+10)
    

def workflow2(x, y, z, width, height, slope_size, speed):
    nx=x-87.3
    ny=y-1.7
    nz=z+6
    i=0
    nwidth=width+5.6
    nheight=height+11.4
 
    move_xyz(nx, ny, nz+7)
    move_xyz(nx+ slope_size, ny, nz+7)
    move_xyz(nx + slope_size, ny, nz+i)
    send_cmd(f"G1 F{speed}")
    send_cmd(f"M0 S1")
    send_cmd(f"M140 S100")
    move_xyz(nx + nwidth - slope_size, ny, nz+i)
    move_xyz(nx + nwidth, ny + slope_size, nz+i)
    move_xyz(nx + nwidth, ny + nheight - slope_size, nz+i)
    move_xyz(nx + nwidth - slope_size, ny + nheight, nz+i)
    move_xyz(nx + slope_size, ny + nheight, nz+i)
    move_xyz(nx, ny + nheight - slope_size, nz+i)
    move_xyz(nx, ny + slope_size, nz+i)
    move_xyz(nx + slope_size, ny, nz+i)
    send_cmd(f"M0 P100")
    send_cmd(f"M140 S0")
    time.sleep(170)
    send_cmd(f"G1 F{1000}")
    move_xyz(nx + slope_size, ny, nz+15)
    
def update_image():
    _,_,tk_image = process_image()  
    label.config(image=tk_image)  
    label.image = tk_image  
    root.after(1, update_image)  
    
def process_image():
    global sum_x, sum_y, image
    
    img = picam2.capture_array()
    pil_image = Image.fromarray(img)
    
    gray_img = np.sum(img, axis=2, dtype='uint16')
    x = np.argmax(np.sum(gray_img, axis=0))
    y = np.argmax(np.sum(gray_img, axis=1))

    sum_x += x
    sum_y += y
    
    if image == sample_rate:
          mean_x = sum_x / sample_rate
          mean_y = sum_y / sample_rate
          sum_x = 0
          sum_y = 0
          image = 0
          
          draw = ImageDraw.Draw(pil_image)
          cross_size = 10
          #1px/1.12µm*570µm=509px
          draw.line((mean_x - cross_size, mean_y - cross_size, mean_x + cross_size, mean_y + cross_size), fill=(255, 0, 0), width=2)
          draw.line((mean_x - cross_size, mean_y + cross_size, mean_x + cross_size, mean_y - cross_size), fill=(255, 0, 0), width=2)
          for x in range(0, draw.im.size[0], 509):
            draw.line((x, 0, x, draw.im.size[1]), fill="white", width=2)
          for y in range(0, draw.im.size[1], 509):
            draw.line((0, y, draw.im.size[0], y), fill="white", width=2)
    image += 1
    
    scale_img=pil_image.resize((328,246))
    tk_image = ImageTk.PhotoImage(scale_img)
    
    
    return x,y, tk_image
    

def verkippung():
    global sum_x, sum_y, image
    
    
    while image <= sample_rate:
        x1, y1, _ = process_image()
        sum_x += x1
        sum_y += y1
        
        if image == sample_rate:
          mean_x1 = sum_x / sample_rate
          mean_y1 = sum_y / sample_rate
          
          sum_x = 0
          sum_y = 0
          image = 0
        image += 1
    
    #time.sleep(10)
    
    # while image <= sample_rate:
        # x1, y1, _ = process_image()
        # sum_x += x1
        # sum_y += y1
        
        # if image == sample_rate:
          # mean_x2 = sum_x / sample_rate
          # mean_y2 = sum_y / sample_rate
          
          # sum_x = 0
          # sum_y = 0
          # image = 0
          # Messwert=yes
        # image += 1
    
    distance_x = mean_x2 - mean_x1
    distance_y = mean_y2 - mean_y1
    
    label_x.config(text=f"Distance X: {distance_x}")
    label_y.config(text=f"Distance Y: {distance_y}")

def initialize_camera():
     global picam2
     picam2=Picamera2()
     select_camera('C')
     picam2.configure(picam2.create_preview_configuration({'size': (3280,2464)}))
     #picam2.set_controls({"ExposureTime": 1,"ExposureValue":-8,"Brightness": 0, "Saturation":0})
     picam2.start()
     


def notbutton():
    send_cmd("M112")
    
    
def prime1():
    global is_active
    
    is_active = not is_active
    
    if is_active:
        send_cmd(f"M0 S1")
        send_cmd(f"M104 S100")
    else:
        send_cmd(f'M0 P100')
        send_cmd(f'M104 S0')
        
def prime2():
    global is_active
    
    is_active = not is_active
    
    if is_active:
        send_cmd(f"M0 S1")
        send_cmd(f"M140 S100")
    else:
        send_cmd(f"M0 P100")
        send_cmd(f"M140 S0")
    
     
    

if __name__ == '__main__':
    
        
        open_serial_connection()
        #initialize_camera()
        root = tk.Tk()
        root.title("3D-Druckersteuerung")
        root.attributes('-fullscreen', True)
        root.configure(bg="orange")
        
        
        
        
        label = tk.Label(root, image=tk_image)
        label.grid(row=0, column=1, rowspan=7, padx=10, pady=10)
        
        reference_button = Button(root, text="1.Reference Position",  bg="#2E8B57", width=20, height=2, command=reference_position)
        reference_button.grid(row=1, column=0, padx=10, pady=10)
        
        prime1_button = Button(root, text="2.Kleber 1",  bg="#2E8B57", width=20, height=1, command=prime1)
        prime1_button.grid(row=2, column=0)
        
        prime2_button = Button(root, text="2.Kleber 2",  bg="#2E8B57", width=20, height=1, command=prime2)
        prime2_button.grid(row=3, column=0)
       
        workflow_button = Button(root, text="3.Kleben", bg="#2E8B57", width=20, height=2, command=lambda: workflow(161.4, 126.5, 104, 26.0, 49.9, 200,8))
        workflow_button.grid(row=4, column=0, padx=10, pady=10)
        
        fenster_button = Button(root, text="4.Fenster", bg="#2E8B57", width=20, height=2, command=lambda:fenster(161.4, 126.5, 110, 25.5, 49.4, 200,5))
        fenster_button.grid(row=5, column=0, padx=10, pady=10) 
    
        workflow2_button = Button(root, text="5.Verfüllen", bg="#2E8B57", width=20, height=2, command=lambda: Thread(target=workflow2, args=(161.0, 126.5, 104, 24.4, 44, 7, 6)).start())
        workflow2_button.grid(row=6, column=0, padx=10, pady=10)
        
        #laser_button = tk.Button(root, text="5. Verkippung Messen",  bg="#2E8B57", width=20, height=2, command=verkippung)
        #laser_button.grid(row=6, column=0, padx=10, pady=10)
        
        not_button = tk.Button(root, text="Not",  bg="#FF0000", width=20, height=2, command=notbutton)
        not_button.grid(row=7, column=0, padx=10, pady=10)
        
        
        #camera_button = tk.Button(root, text="Kamera",  bg="#2E8B57", width=20, height=2, command=update_image)
        #scamera_button.grid(row=8, column=0, padx=10, pady=10)
        
        exit_button = tk.Button(root, text="Exit", command=exit_program)
        exit_button.grid(row=8, column=0, padx=10, pady=10)
        

        root.mainloop()
        #picam2.stop()
