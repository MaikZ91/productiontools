from __future__ import print_function
#import cv2
#import numpy as np
#import matplotlib.pyplot as plt
import serial
#from tkinter import Tk, Scale, HORIZONTAL, Label, Button
#import threading
#import time
#from PIL import Image, ImageEnhance, ImageFilter
#import pandas as pd
#from mayavi import mlab
#lsuimport seaborn as sns
import sys
import os
import time

ser = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)

def move_to_pos(addr, pos, ypos=0):
    pos_bytes = bytearray((pos >> i * 8) & 0xFF for i in range(4))
    data = bytearray([addr, 0]) + pos_bytes
    ser.write(data)
    
def current_pos(addr):
    ser.reset_input_buffer()
    query = bytearray([addr, 0xC1])
    ser.write(query)
    status = ser.read(9)
    actp = (status[4] << 24) | (status[3] << 16) | (status[2] << 8) | status[1]
    return actp


class DinoLiteController:
    def __init__(self, device_index=0):
        self.cap = cv2.VideoCapture(device_index)
        self.running = False

        if not self.cap.isOpened():
            raise ValueError("Kamera konnte nicht geöffnet werden")

    def capture_image(self):
        ret, frame = self.cap.read()
        if not ret:
            raise ValueError("Bild konnte nicht aufgenommen werden")
        return frame

    def show_live_feed(self):
        self.running = True
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            cv2.imshow('Live Feed', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.running = False

        cv2.destroyAllWindows()


    def release(self):
        self.cap.release()


def update_position(val):
    global pos
    pos = int(val)
    move_to_pos(19, pos)
    position_label.config(text=f"Position: {pos}")

def start_live_feed():
    live_feed_thread = threading.Thread(target=dino_lite.show_live_feed)
    live_feed_thread.start()

def process_image(stitched_image):
    focus_frame = stitched_image
    #focus_frame = autofocus()
    cv2.imwrite('focused_image.tif', focus_frame)
    fourier_img = fourier(focus_frame)
    Image.fromarray(fourier_img).save('fourier_square.tif')
    thresh_image, detected_particles = count_particles(fourier_img,focus_frame)
    cv2.imwrite('tresh.tif', thresh_image)
    Image.fromarray(cv2.cvtColor(detected_particles, cv2.COLOR_BGR2RGB)).save('detected.tif')
    
    return focus_frame  

def count_particles(fourier_frame, focus_frame):
    thresh_image = (fourier_frame > 90).astype(np.uint8) * 255
    contours, _ = cv2.findContours(thresh_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    particle_count = 0
    particle_diameters = []
  
    for contour in contours:
        particle_count += 1
        (x, y), radius = cv2.minEnclosingCircle(contour)
        diameter_um = 2 * radius * 2.6
        particle_diameters.append(diameter_um)
        cv2.circle(focus_frame, (int(x), int(y)), int(radius), (0, 255, 0), 2)
        if diameter_um >= 5:
            cv2.circle(focus_frame, (int(x), int(y)), int(radius), (0, 0, 255), 2)
    
    update_plot(particle_diameters,focus_frame)

    return thresh_image, focus_frame

fig = None
axes = None

def init_plot():
    global fig, axes
    plt.ion()
    fig, axes = plt.subplots(1, 3, figsize=(14, 7))
    plt.show()

def update_plot(particle_diameters, focus_frame):
    global fig, axes

    threshold_um = 5
    small_particles = [d for d in particle_diameters if d < threshold_um]
    large_particles = [d for d in particle_diameters if d >= threshold_um]
    total_particles = len(particle_diameters)
    small_count = len(small_particles)
    large_count = len(large_particles)

    axes[0].clear()
    sns.histplot(particle_diameters, bins=20, kde=False, color="blue", ax=axes[0])
    axes[0].axvline(x=threshold_um, color='red', linestyle='--', label=f'Grenzwert: {threshold_um} µm')
    axes[0].set_title(f'Histogramm der Partikeldurchmesser\n'
                      f'Insgesamt: {total_particles}, < {threshold_um} µm: {small_count}, ≥ {threshold_um} µm: {large_count}')
    axes[0].set_xlabel('Durchmesser (µm)')
    axes[0].set_ylabel('Anzahl der Partikel')
    axes[0].legend()
    axes[1].clear()
    sns.boxplot(particle_diameters, color="lightblue", ax=axes[1])
    axes[1].axvline(x=threshold_um, color='red', linestyle='--', label=f'Grenzwert: {threshold_um} µm')
    axes[1].set_title(f'Boxplot der Partikeldurchmesser\n'
                      f'Insgesamt: {total_particles}, < {threshold_um} µm: {small_count}, ≥ {threshold_um} µm: {large_count}')
    axes[1].set_xlabel('Durchmesser (µm)')
    
    axes[2].clear()
    axes[2].imshow(cv2.cvtColor(focus_frame, cv2.COLOR_BGR2RGB))
    axes[2].axis('off')
    axes[2].set_title('Detected Particles')
    
    plt.tight_layout()
    plt.draw()
    plt.pause(0.1)

#init_plot()
    

def fourier(frame):
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    f = np.fft.fft2(frame_gray)
    fshift = np.fft.fftshift(f)
    rows, cols = frame_gray.shape
    crow, ccol = rows // 2, cols // 2
    mask_size = 10
    mask = np.ones((rows, cols), np.uint8)
    mask[crow-mask_size:crow+mask_size, ccol-mask_size:ccol+mask_size] = 0
    fshift_filtered = fshift * mask
    f_ishift = np.fft.ifftshift(fshift_filtered)
    img_back = np.fft.ifft2(f_ishift)
    img_back = np.abs(img_back)
    img_back_normalized = np.uint8(255 * img_back / np.max(img_back))

    return img_back_normalized

def autofocus():

    global z_slices 
    z_slices = []
    
    beste_fokus_bewertung = -1
    
    focus_range = 2000
    focus_position = current_pos(20)
    startpos = int(current_pos(20) - focus_range / 2)
    endpos = int(current_pos(20) + focus_range / 2)
    focus_frame = None

    move_to_pos(20, int(startpos))
    time.sleep(0.5)

    for pos in range(startpos, endpos+40, 25):
        
        frame = dino_lite.capture_image()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        z_slices.append(frame)

        fokus_bewertung = cv2.Laplacian(frame, cv2.CV_64F).var()
        
        if fokus_bewertung > beste_fokus_bewertung:
            beste_fokus_bewertung = fokus_bewertung
            focus_position = current_pos(20)
            focus_frame = frame

        move_to_pos(20, pos)
    
    move_to_pos(20, focus_position)
    time.sleep(1)
    focus_frame = dino_lite.capture_image()
    

    return focus_frame


points = []

def click_event(event, x, y, flags, params):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        cv2.circle(img, (x, y), 5, (0, 255, 0), -1)
        cv2.imshow("Bild", img)
        
        if len(points) == 2:
            dist = ((points[0][0] - points[1][0]) ** 2 + (points[0][1] - points[1][1]) ** 2) ** 0.5
            print(f"Abstand zwischen den Punkten in Pixeln: {dist} Pixel")

def measure_distance():
    global img
    img = cv2.imread("detected.tif")
    cv2.imshow("Bild", img) 
    cv2.setMouseCallback("Bild", click_event)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    

def stitch():
    imagesy = []
    imagesx = []

    start_y, end_y = 215000, 110000

    for posx in range(0, 120000, 13500):
        move_to_pos(18, posx)
        time.sleep(1)
    
        for posy in range(start_y, end_y, -9000 if start_y > end_y else 9000):
            move_to_pos(19, posy)
            frame = autofocus()

            if start_y < end_y:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            imagesy.append(frame)

        y_image = cv2.vconcat(imagesy)
        y_image = cv2.rotate(y_image, cv2.ROTATE_180)
        imagesx.append(y_image)
        imagesy.clear()
        start_y, end_y = end_y, start_y
        
    stitched_image = cv2.hconcat(imagesx)
    process_image(stitched_image)
    combined_image_rgb = cv2.cvtColor(stitched_image, cv2.COLOR_BGR2RGB)
    Image.fromarray(combined_image_rgb).save("Combined_Image.tif", format='TIFF', compression='none')
    

def createGUI():
    root = Tk()
    root.title("DinoLite Controller")

    position_scale = Scale(root, from_=0, to=300000, orient=HORIZONTAL, command=update_position)
    position_scale.set(pos)
    position_scale.pack()

    position_label = Label(root, text=f"Position: {pos}")
    position_label.pack

    process_button = Button(root, text="Process Image", command=process_image)
    process_button.pack()

    stitch_button = Button(root, text="Stitch", command=stitch)
    stitch_button.pack()

    autofocus_button = Button(root, text="Autofocus", command=autofocus)
    autofocus_button.pack()

    start_live_feed()

    root.mainloop()

    dino_lite.release()

def startpos():
    move_to_pos(18, 0)
    move_to_pos(19, 215000)
    move_to_pos(20, 60000)
    #time.sleep(5)
    #move_to_pos(18, 40000)
    #move_to_pos(19, 175000)
    #move_to_pos(20, 60000) 
    
    
#measure_distance()
#dino_lite = DinoLiteController()
pos = 0
startpos()
#createGUI()

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from DFRobot_GP8403 import *

DAC = DFRobot_GP8403(0x5f)  
while DAC.begin() != 0:
    print("init error")
    time.sleep(1)
print("init succeed")
  
#Set output range  
DAC.set_DAC_outrange(OUTPUT_RANGE_10V)

while True:
    DAC.set_DAC_out_voltage(0, 1)     # Setzt die Spannung auf 0 V
    time.sleep(1)                     # Wartet 2 Sekunden
    DAC.set_DAC_out_voltage(10000, 1) # Setzt die Spannung auf 10 V
    time.sleep(1)


    

    
   
