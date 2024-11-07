from picamera2 import Picamera2, Preview
import serial
import RPi.GPIO as gp
import os
import matplotlib.pyplot as plt
import numpy as np
import time
from PIL import Image
import cv2
import scipy
from skimage import filters
import pandas as pd
#from sklearn.metrics import r2_score
#from mpl_toolkits.mplot3d import Axes3D
import tkinter as tk
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH")

#root.attributes("-fullscreen", True)

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration({'size': (1000, 1000)}))
#root = tk.Tk()
motorsteps = 0
pos, x_coord, y_coord, x_coord2, y_coord2 = [], [], [], [], []
count = 0
i = 1
max_steps = 320000 

ser = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)

adapter_info = {
    "A": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x04", "gpio_sta": [0, 0, 1]},
    "B": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x05", "gpio_sta": [1, 0, 1]},
    "C": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x06", "gpio_sta": [0, 1, 0]},
    "D": {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x07", "gpio_sta": [1, 1, 0]},
}

camera_dict = {
    'Y': {"camera": "A", "controls": {"AeEnable": False, "AnalogueGain": 1.0, "AwbEnable": False, "ColourGains": (1.0, 1.0), "ExposureTime": 1}},
    'Y1': {"camera": "D", "controls": {"AeEnable": False, "AnalogueGain": 1.0, "AwbEnable": False, "ColourGains": (1.0, 1.0), "ExposureTime": 1}},
    'Z': {"camera": "B", "controls": {"AeEnable": False, "AnalogueGain": 1.0, "AwbEnable": False, "ColourGains": (1.0, 1.0), "ExposureTime": 1}},
    'Z1': {"camera": "C", "controls": {"AeEnable": False, "AnalogueGain": 1.0, "AwbEnable": False, "ColourGains": (1.0, 1.0), "ExposureTime": 1000}},
}

def initialize_gpio():
    gp.setwarnings(False)
    gp.setmode(gp.BOARD)
    gp.setup(7, gp.OUT)
    gp.setup(11, gp.OUT)
    gp.setup(12, gp.OUT)

initialize_gpio()
    

def select_camera(index):
    channel_info = adapter_info.get(index)
    gpio_sta = channel_info["gpio_sta"]
    gp.output(7, gpio_sta[0])
    gp.output(11, gpio_sta[1])
    gp.output(12, gpio_sta[2])
    os.system(channel_info["i2c_cmd"])

def initialize_and_set_camera(axis):
    camera_info = camera_dict[axis]
    select_camera(camera_info["camera"])
    picam2.set_controls(camera_info["controls"])
    picam2.start()

def initialize_and_capture_images(camera1, camera2):
    global np_img, np_img2, count

    initialize_and_set_camera(camera1)
    time.sleep(0.2)
    np_img = picam2.capture_array()
    picam2.stop()
    initialize_and_set_camera(camera2)
    time.sleep(0.2)
    np_img2 = picam2.capture_array()
    picam2.stop()
    count += 1
    
    return np_img,np_img2

def process_image(motor, axis):
    global motorsteps

    if axis == 'Y':
        np_img,np_img2 = initialize_and_capture_images('Y1', 'Y')
    if axis == 'Z':
        np_img,np_img2 = initialize_and_capture_images('Z', 'Z1')

    gray_img = np_img[..., 1]
    gray_img2 = np_img2[..., 1]

    x, y, _ = calculate_centroid(gray_img)
    x2, y2, _ = calculate_centroid(gray_img2)
    
    append_to_coordinates(x_coord, y_coord, x, y)
    append_to_coordinates(x_coord2, y_coord2, x2, y2)
    pos.append(current_pos(motor))

    cv2.circle(np_img, (int(x),int(y)), 2, (255, 255, 255), -1)
    cv2.circle(np_img2, (int(x2), int(y2)), 2, (255, 255, 255), -1)
    
    #cv2.imwrite(f'cam1_{motorsteps}.tif',np_img)
    #cv2.imwrite(f'cam2_{motorsteps}.tif',np_img2)
    
    if axis == 'Y':
        motorsteps += 1000
    if axis == 'Z':
        motorsteps += 50
    
    move_to_pos(motor, motorsteps)
    #steps_label.config(text=f"Fortschritt: {motorsteps}/{max_steps}")
    #root.update()
    print(motorsteps)
    
    time.sleep(1)
    
    
def calculate_centroid(image):
    otsu_threashold = filters.threshold_otsu(image)
    norm = 127 / otsu_threashold
    _, binary_image = cv2.threshold((image * norm).astype('uint8'), 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest_contour = max(contours, key=cv2.contourArea)
    (cx, cy), radius = cv2.minEnclosingCircle(largest_contour)
    cx, cy = int(cx), int(cy)
    radius = int(radius)
    mask = np.zeros_like(binary_image)
    cv2.circle(mask, (cx, cy), radius, 255, -1)
    cy, cx = scipy.ndimage.center_of_mass(image, mask)
    cv2.circle(mask, (int(cx), int(cy)), radius, 255, -1)
    cy, cx = scipy.ndimage.center_of_mass(image, mask)

    return cx, cy, largest_contour
    
def append_to_coordinates(x_coord, y_coord, mean_x, mean_y):
    x_coord.append(mean_x)
    y_coord.append(mean_y)


def move_to_pos(addr, pos, ypos=0):
    data = bytearray([addr, 0]) + int_to_bytes(pos, 4)
    ser.write(data)

def current_pos(addr):
    ser.reset_input_buffer()
    query = bytearray([addr, 0xC1])
    ser.write(query)
    status = ser.read(9)
    actp = (status[4] << 24) | (status[3] << 16) | (status[2] << 8) | status[1]
    return actp

def startposition(start):
    move_to_pos(18, 97000)
    move_to_pos(19, 0)
    move_to_pos(20, 0)

    while current_pos(19) != 0 or current_pos(20) != 0:
        pass
    return True
    
def endposition():
    move_to_pos(18, 97000)
    move_to_pos(19, 321000)
    move_to_pos(20, 80000)
    
def position_y():
    move_to_pos(18, 97000)
    move_to_pos(19, 0)
    move_to_pos(20, 0)
    

def int_to_bytes(n, length):
    return bytearray((n >> i * 8) & 0xFF for i in range(length))

def showResults(axis):
    global pos

    x1, x_fit1,dis_x1,poly_x1,x1_derivative,x1_max_slope = berechne_ausgleichsgerade(pos, x_coord)
    x2, x_fit2,dis_x2,poly_x2,x2_derivative,x2_max_slope  = berechne_ausgleichsgerade(pos, x_coord2)
    y1, y_fit1,dis_y1,poly_y1,y1_derivative,y1_max_slope  = berechne_ausgleichsgerade(pos, y_coord)
    y2, y_fit2,dis_y2,poly_y2,y2_derivative,y2_max_slope = berechne_ausgleichsgerade(pos, y_coord2)

    sample_pos_x, cam1_x, cam2_x, fov_x = calculate_slide_of_view(x2, x1)
    sample_pos_y, cam1_y, cam2_y, fov_y= calculate_slide_of_view(y2, y1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    # Plot für die X-Richtung
    ax1.plot(pos, sample_pos_x, label="Sample Pos X",linewidth=1)
    ax1.plot(pos, cam1_x,linestyle='--', label="Cam 1 X",linewidth=1)
    ax1.plot(pos, cam2_x, linestyle='--', label="Cam 2 X",linewidth=1)
    ax1.plot(pos[1:-1], fov_x, label="FOV X", color='black',linewidth=1)
    ax1.set_title("Positions in X Direction")
    ax1.set_xlabel("Position")
    ax1.set_ylabel("X-Werte")
    ax1.legend()

    # Plot für die Y-Richtung
    ax2.plot(pos, sample_pos_y,label="Sample Pos Y",linewidth=1)
    ax2.plot(pos, cam1_y, linestyle='--', label="Cam 1 Y",linewidth=1)
    ax2.plot(pos, cam2_y,  linestyle='--', label="Cam 2 Y",linewidth=1)
    ax2.plot(pos[1:-1], fov_y, label="FOV Y", color='black',linewidth=1)
    ax2.set_title("Positions in Y Direction")
    ax2.set_xlabel("Position")
    ax2.set_ylabel("Y-Werte")
    ax2.legend()

    # Layout anpassen und speichern
    plt.tight_layout()
    plt.savefig('/home/pi/stage_test/auswertung_xy_directions.png')
    # plt.show()  # Zum Anzeigen, falls benötigt

    
    # ax1.plot(pos,slope_x, label='X', color='blue',linewidth=1)
    # ax1.plot(pos,slope_y, label='Y', color='blue',linewidth=1)
    # ax1.plot(pos,slope_y, label='Y', color='blue',linewidth=1)

    # #pos = np.array(pos)*(48000/321000)
    
    # fig, (ax1, ax2, ax3, ax4) = plt.subplots(1, 4, figsize=(15, 6))
    
    # x_fine = np.linspace(min(pos), max(pos), 100)
    # ax1.plot(pos, y1, label='Cam 1', color='blue',linewidth=1)
    # ax1.plot(pos, y2, label='Cam 2', color='red')
    # ax1.plot(x_fine, y_fit1, linestyle=':', color='blue', linewidth=1)
    # ax1.plot(x_fine, y_fit2, linestyle=':', color='red', linewidth=1)
    # ax1.text(20, 6.5, f'ΔGlobal Tilt: {round(poly_y1,2)} µm', fontsize=10, color='blue', ha='center', va='center')
    # ax1.text(20, 5.5, f'ΔGlobal Tilt: {round(poly_y2,2)} µm', fontsize=10, color='red', ha='center', va='center')
    
    # ax1.set_xlabel(f'Bewegung Stage in {axis}[µm]')
    # ax1.set_ylabel('Auslenkung in Z[µm]' if axis == 'Y' else 'Auslenkung in Y[µm]')

    # ax1.legend()
    
    # dataz = [dis_y1,dis_y2]  
    # bp=ax2.boxplot(dataz, patch_artist=True)
    # colors = ['blue', 'red']
    # for patch, color in zip(bp['boxes'], colors):
    #     patch.set_facecolor(color)
        
    # if axis=='Y':
    #     x1=x1*-1
    #     x_fit1=x_fit1*-1
    
    # ax3.plot(pos, x1, label='Cam 1', color='blue',linewidth=1)
    # ax3.plot(x_fine, x_fit1, linestyle=':', color='blue', linewidth=1)
    # ax3.plot(pos, x2, label='Cam 2', color='red')
    # ax3.plot(x_fine, x_fit2, linestyle=':', color='red', linewidth=1)
    # ax3.text(20, 6.5, f'ΔGlobal Tilt: {round(poly_x1,2)} µm', fontsize=10, color='blue', ha='center', va='center')
    # ax3.text(20, 5.5, f'ΔGlobal Tilt: {round(poly_x2,2)} µm', fontsize=10, color='red', ha='center', va='center')
    # ax3.set_xlabel(f'Bewegung Stage in {axis}[µm]')
    # ax3.set_ylabel('Auslenkung in X[µm]')
    # ax3.legend()
    
    
    # datax = [dis_x1,dis_x2]  
    # bp=ax4.boxplot(datax, patch_artist=True)
    # colors = ['blue', 'red']
    # for patch, color in zip(bp['boxes'], colors):
    #     patch.set_facecolor(color)
    # plt.savefig('/home/pi/stage_test/auswertung.png')
    # fig = plt.figure()
    # ax = fig.add_subplot(111, projection='3d')
    
    # if axis == 'Y':
    #     ax.plot(pos, x1 * -1, y1, label='Cam 1', color='blue')
    # else:
    #     ax.plot(pos, x1, y1, label='Cam 1', color='blue')


    # ax.plot(x_fine,[0] * len(y_fit1),y_fit1, linestyle=':', color='black', linewidth=1)
    # ax.plot(x_fine,x_fit1*-1,[0] * len(x_fit1*-1),linestyle=':', color='black', linewidth=1)

 
    # ax.set_xlabel(f'Bewegung Stage in {axis}[µm]')  
    # ax.set_ylabel('Auslenkung in X [µm]')
    # ax.set_zlabel('Auslenkung in Z[µm]')
    
    # df = pd.DataFrame({'Position': pos,'Z- Auslenkung_Cam1': y1,'X-Auslenkung_Cam1': x1,'Z- Auslenkung_Cam2': y2,'X-Auslenkung_Cam2': x2,'Tilt_Cam1_Z':poly_y1,'Tilt_Cam2_Z':poly_y2,'Tilt_Cam1_X':poly_x1,'Tilt_Cam2_X':poly_x2})
    # df.to_excel('/home/pi/stage_test/Rohdaten.xlsx')

    
    # plt.show()
    
    # plt.figure(figsize=(12, 6))
    # # Original-Polynom
    # plt.subplot(1, 2, 1)
    # plt.plot(x_fine, y_fit2, label='Polynom (Grad 10)', color='blue')
    # plt.xlabel('x')
    # plt.ylabel('y')
    # plt.title('Polynom Anpassung')
    # plt.legend()

    # # Ableitung des Polynoms
    
    # plt.subplot(1, 2, 2)
    # plt.plot(x_fine, y2_derivative, label="Ableitung des Polynoms", color='orange')
    # plt.xlabel('x')
    # plt.ylabel("Ableitung von y")
    # plt.title("Ableitung der Polynom-Anpassung")
    # plt.legend()
    # plt.text(0.05, 0.9, f"Maximale Steigung: {x1_max_slope :.5f}", transform=plt.gca().transAxes, fontsize=10, color="red")


    # plt.tight_layout()
    # plt.savefig(f"polynom_und_ableitung_cam{axis}.png", format='png', dpi=300)
    # plt.close()
    
 
    #clear_list()
    

def berechne_ausgleichsgerade(x_werte, y_werte):
    
    y_werte = np.array(y_werte) * 1.12
    
    steigung,_ = np.polyfit(x_werte, y_werte, 1)
    y_slope_korrigiert = y_werte - np.array(pos)*steigung
    y_baseline = y_slope_korrigiert - np.mean(y_slope_korrigiert)

    coefficients = np.polyfit(x_werte, y_baseline, 10)
    poly_function = np.poly1d(coefficients)
    x_fine = np.linspace(min(x_werte), max(x_werte), 100)
    y_fit_grob = poly_function(x_werte)
    y_fit = poly_function(x_fine)

    poly_derivative = poly_function.deriv()
    
    y_derivative = poly_derivative(x_fine)
    max_slope = np.max(np.abs(y_derivative))
    
    delta_y= abs(y_baseline- y_fit_grob)
    delta_poly= abs(max(y_fit)-min(y_fit))
    
    return y_baseline, y_fit,delta_y,delta_poly,y_derivative,max_slope

def calculate_slide_of_view(cam_1, cam_2):

    slope = (cam_1-cam_2)/(60-0)

    sample_pos = slope*70
    cam1 = slope*60 + cam_2
    cam2 = slope*0 + cam_2

    fov = []

    for i in range(len(sample_pos) - 2):
        three_values = sample_pos[i:i+3]
        delta = max(three_values) - min(three_values)
        fov.append(delta)

    return sample_pos, cam1, cam2, fov



def clear_list():
    pos.clear()
    y_coord.clear()
    y_coord2.clear()
    x_coord.clear()
    x_coord2.clear()

def measure_axis(axis):
    global motorsteps, i
    #321000
    if startposition(19 if axis == 'Y' else 20):
        while current_pos(19 if axis == 'Y' else 20) < (320000 if axis == 'Y' else 80000):
            process_image(19 if axis == 'Y' else 20, axis)

    
    showResults(axis)
    motorsteps = 0

current_camera = None

def testcameras(axis):
    global current_camera
    
    if current_camera:
        picam2.stop()
        
    camera_info = camera_dict[axis]
    select_camera(camera_info["camera"])
    picam2.set_controls(camera_info["controls"])
    picam2.start_preview(Preview.QT, x=100, y=200, width=800, height=600)
    picam2.start()
    current_camera = picam2
    
def exit_fullscreen(event=None):
    root.attributes("-fullscreen", False)
    

def test_y():
    move_to_pos(18, 97000)
    move_to_pos(19, 320000)
    move_to_pos(20, 0)
    time.sleep(20)
    move_to_pos(18, 97000)
    move_to_pos(19, 0)
    move_to_pos(20, 0)
    
def test_z():
    move_to_pos(18, 97000)
    move_to_pos(19, 0)
    move_to_pos(20, 82000)
    time.sleep(10)
    move_to_pos(18, 97000)
    move_to_pos(19, 0)
    move_to_pos(20, 0)
    
    
def loop():
    
    for i in range(1):
        measure_axis('Z')
        
def measure_all_axis():
    
    measure_axis('Y')
    measure_axis('Z')
    
        
def create_gui():
    global steps_label
    
    root.title("Laser-Messsystem")
    root.configure(bg="orange")

    position_button = tk.Button(root, text="1.Einrichtung Laseraufsatz", command=endposition, width=20, height=1, bg="#008C8C", fg="white")
    position_button_y = tk.Button(root, text="2.Mess Positionierung", command=position_y, width=20, height=1, bg="#008C8C", fg="white")
    test_button_y = tk.Button(root, text="2.Test Y", command=test_y, width=10, height=1, bg="#008C8C", fg="white")
    test_button_z = tk.Button(root, text="2. Test Z", command=test_z, width=10, height=1, bg="#008C8C", fg="white")

    setup_button_Y = tk.Button(root, text="3.CAM Y1", command=lambda: testcameras('Y'), width=10, height=1, bg="#008C8C", fg="white")
    setup_button_Y1 = tk.Button(root, text="4.CAM Y2", command=lambda: testcameras('Y1'), width=10, height=1, bg="#008C8C", fg="white")
    setup_button_Z = tk.Button(root, text="5.CAM Z1", command=lambda: testcameras('Z'), width=10, height=1, bg="#008C8C", fg="white")
    setup_button_Z1 = tk.Button(root, text="6.CAM Z2", command=lambda: testcameras('Z1'), width=10, height=1, bg="#008C8C", fg="white")
    steps_label = tk.Label(root, text=f"Fortschritt: {motorsteps}/{max_steps}", font=("Helvetica", 12))

    measurement_x_button = tk.Button(root, text="7.Messung starten Y", command=lambda: measure_axis('Y'), width=20, height=1, bg="#008C8C", fg="white")
    measurement_y_button = tk.Button(root, text="8.Messung starten Z", command=lambda: measure_axis('Z'), width=20, height=1, bg="#008C8C", fg="white")
    measurement_all_button = tk.Button(root, text="9.Messung starten YZ", command=lambda: measure_all_axis(), width=20, height=1, bg="#008C8C", fg="white")

    position_button.pack(pady=10)
    position_button_y.pack(pady=10)
    setup_button_Y.pack(side="top", padx=5, pady=10)
    setup_button_Y1.pack(side="top", padx=5, pady=10)
    setup_button_Z.pack(side="top", padx=5, pady=10)
    setup_button_Z1.pack(side="top", padx=5, pady=10)
    test_button_y.pack(pady=10)
    test_button_z.pack(pady=10)
    steps_label.pack(pady=10)

    measurement_x_button.pack(pady=5)
    measurement_y_button.pack(pady=5)
    measurement_all_button.pack(pady=5)

    seriennummer_label = tk.Label(root, text="Seriennummer eingeben:", font=("Helvetica", 10))
    seriennummer_entry = tk.Entry(root, font=("Helvetica", 12))
    seriennummer_label_result = tk.Label(root, text="", font=("Helvetica", 12))

    def speichern_seriennummer():
        global seriennummer
        seriennummer = seriennummer_entry.get()
        seriennummer_label_result.config(text=f"Gespeicherte Seriennummer: {seriennummer}")

    speichern_button = tk.Button(root, text="Seriennummer speichern", command=speichern_seriennummer, bg="#008C8C", fg="white")

    seriennummer_label.pack(pady=10)
    seriennummer_entry.pack(pady=10)
    speichern_button.pack(pady=10)
    seriennummer_label_result.pack(pady=10)

    root.mainloop()

#create_gui()

measure_axis('Y')


