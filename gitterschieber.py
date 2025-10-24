import os, sys, time, threading, random
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')  # weiterhin Offscreen für Saves; QtCanvas rendert separat
import matplotlib.pyplot as plt
import serial
from PIL import Image
import pandas as pd
import seaborn as sns
import tifffile as tif

from tkinter import filedialog

from PyQt5 import uic  # bleibt importiert, wird aber nicht mehr genutzt
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QLabel, QWidget, QSlider,
    QScrollBar, QTextEdit, QHBoxLayout, QVBoxLayout,
    QMainWindow, QGraphicsView, QPushButton, QDockWidget,
    QSizePolicy, QFrame, QDial
)
from PyQt5.QtGui import QImage, QPixmap, QPalette, QColor, QFont
from PyQt5.QtCore import QTimer, Qt, QThread, QMetaObject, Q_ARG, QObject, pyqtSignal, pyqtSlot

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from collections import deque

from pipython import GCSDevice, pitools
import AngleAnalysisFunctions as AAF

# ----------------- KONSTANTEN -----------------
STAGE_WAIT_TIME = 1e-4
ser = serial.Serial('COM5', baudrate=9600, timeout=1)
volt_addr = 0xD0
volt_pltf = 0xC0

startpos_x = 8000
startpos_y = 97000
startpos_z = 3000
working_distance_dif = 32000
particle_count = 0
particle_diameters = []
particle_total = 0

THEORIE_WINKEL_DEG = 8.95
GRATING_ERROR_TOLERANCE_MRAD = 2

SIM7_centerpos = [118395, 154950]
SIM31_centerpos = [81525, 151110]
SIM31_SEcornerpos = [85620, 298950]
currentPosXYZ = [0, 0, 0]

maxVolt = 4.022 * 1e3
x_addr = 18
y_addr = 19
z_addr = 20
voltage_step = 0.166 * 1e3
OP_amp_factor = 2

piezoshift_angle_to_cam = 100
grating_angle_to_cam = 100
grating_angle_error = 100
angle_processing_active = False

# ----------------- Empfindlichkeit & letzte Frames -----------------
DETECTION_SENSITIVITY = 0.66  # 0.0 = low, 0.5 = mid, 1.0 = high
latest_frame = None           # letztes analysiertes Bild (wie an process_image übergeben)
latest_base_bgr = None        # Basismotiv (für Rücksprung nach Flash)

# ----------------- Overlay-Flash -----------------
overlay_flash_ms = 2500      # Dauer des Einblendens in Millisekunden

# ----------------- Globals (GUI etc.) -----------------
gui = None
bridge = None
timer = None
timer_camera = None
fig = None
axes = None
dino_lite = None
filedir = os.getcwd()

# ----------------- HILFSFUNKTIONEN HARDWARE -----------------
def SelectImgDir():
    global filedir
    pathselect = filedialog.askdirectory(initialdir=filedir, title="Select image directory")
    print(pathselect)
    if pathselect:
        filedir = pathselect

def wait_time(oldPos, newPos):
    stageDisplacement = abs(newPos - oldPos)
    sleepTime = stageDisplacement * STAGE_WAIT_TIME
    print("Will sleep for {} seconds.".format(round(sleepTime, 3)))
    return sleepTime

def move_to_pos(addr, pos):
    addrIndex = addr - x_addr
    pos_bytes = bytearray((pos >> i * 8) & 0xFF for i in range(4))
    data = bytearray([addr, 0]) + pos_bytes
    ser.write(data)
    oldPos = currentPosXYZ[addrIndex]
    currentPosXYZ[addrIndex] = pos
    # time.sleep(wait_time(oldPos, pos))

def set_analog_output(address, platform, value):
    value_lsb = value & 0xFF
    value_msb = (value >> 8) & 0xFF
    command = bytes([address, platform, value_lsb, value_msb])
    ser.write(command)

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
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 2592)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1944)
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
            w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            frame_res = cv2.resize(frame, (int(w/2), int(h/2)))
            cv2.imshow('Live Feed', frame_res)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.running = False
        cv2.destroyAllWindows()

    def release(self):
        self.cap.release()

# ----------------- RENDER-HILFE -----------------
def show_in_view(img_bgr: np.ndarray):
    """Zeigt ein BGR-Image im PyQt graphicsView skaliert an."""
    if gui is None or not hasattr(gui, "graphicsView"):
        return
    h, w = img_bgr.shape[:2]
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
    scene = QGraphicsScene()
    gui.graphicsView.setScene(scene)
    scene.clear()
    scene.addPixmap(QPixmap.fromImage(qimg).scaled(
        gui.graphicsView.width(), gui.graphicsView.height(), Qt.KeepAspectRatio))

# --------- Overlay-Flash Helper ---------
def blend_overlay_and_annotate(base_bgr: np.ndarray,
                               overlay_bgr: np.ndarray,
                               count: int,
                               alpha: float = 0.55) -> np.ndarray:
    """
    Blendet Overlay halbtransparent auf das Basismotiv und zeichnet die Partikelanzahl ein.
    """
    if overlay_bgr.shape[:2] != base_bgr.shape[:2]:
        overlay_bgr = cv2.resize(overlay_bgr, (base_bgr.shape[1], base_bgr.shape[0]), interpolation=cv2.INTER_AREA)

    comp = cv2.addWeighted(overlay_bgr, alpha, base_bgr, 1.0 - alpha, 0.0)

    label = f"Particles: {count}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.9
    thickness = 2
    (tw, th), _ = cv2.getTextSize(label, font, scale, thickness)
    pad = 10
    x0, y0 = 15, 20

    # halbtransparenter Kasten
    box = comp.copy()
    cv2.rectangle(box, (x0 - pad, y0 - pad), (x0 + tw + pad, y0 + th + pad), (0, 0, 0), -1)
    comp = cv2.addWeighted(box, 0.35, comp, 0.65, 0.0)
    # Text mit Schatten
    cv2.putText(comp, label, (x0, y0 + th), font, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(comp, label, (x0, y0 + th), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return comp

# ---------- GUI-Bridge für thread-sichere Flash-Anzeige ----------
class GuiBridge(QObject):
    doFlash = pyqtSignal(object, object, int)  # base_bgr, overlay_bgr, count
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doFlash.connect(self.flash)  # Slot im GUI-Thread

    @pyqtSlot(object, object, int)
    def flash(self, base_bgr, overlay_bgr, count):
        flash = blend_overlay_and_annotate(base_bgr, overlay_bgr, count, alpha=0.55)
        show_in_view(flash)
        QTimer.singleShot(overlay_flash_ms, lambda: show_in_view(base_bgr))

# ----------------- PLOTTING -----------------
def init_plot():
    global fig, axes
    plt.ion()
    fig, axes = plt.subplots(1, 3, figsize=(14, 7))

def create_particle_plot(particle_diameters, focus_frame):
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

    ts = time.strftime("%Y%m%d_%H%M%S")
    outfile = os.path.join(filedir, f"particle_plot_{ts}.png")
    fig.savefig(outfile, dpi=300)

# ----------------- PARTICLE DETECTION -----------------
def particle_detection(
    image_or_path,
    sensitivity: float = 0.66,
    do_fft: bool = True,
    save_dir: str = "C:/Users/LVBT/Desktop"
):
    """
    Rückgabe: (overlay_bgr_uint8, mask_uint8, pandas.DataFrame)
    Erfordert: opencv-python, numpy, pandas
    """
    import cv2, numpy as np, pandas as pd
    from pathlib import Path

    # ---- Bild laden / Graustufe ----
    if isinstance(image_or_path, str):
        src = cv2.imread(image_or_path, cv2.IMREAD_UNCHANGED)
        if src is None:
            raise FileNotFoundError(f"Bild nicht gefunden: {image_or_path}")
    else:
        src = image_or_path
    if src.ndim == 3:
        gray_f32 = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        gray_f32 = src.astype(np.float32)

    # ---- FFT-Gitterentfernung ----
    def _fft_grid_remove(gf32: np.ndarray, sigma_k: float = 2.5, search_r_factor: float = 0.18) -> np.ndarray:
        h, w = gf32.shape; cy, cx = h//2, w//2
        inner_keep_r = max(4, int(min(h, w) * 0.006))
        notch_r      = max(3, int(min(h, w) * 0.008))
        search_r     = max(4, int(min(h, w) * search_r_factor))
        max_peaks    = 400
        fft = np.fft.fft2(gf32); fft_shift = np.fft.fftshift(fft)
        mag = np.log1p(np.abs(fft_shift))
        Y, X = np.ogrid[:h,:w]; d2 = (Y-cy)**2 + (X-cx)**2
        cand = (d2 > inner_keep_r**2) & (d2 < search_r**2) & (mag > float(mag.mean()+sigma_k*mag.std()))
        ys, xs = np.nonzero(cand)
        mask = np.ones((h,w), np.float32)

        def notch(m, y0, x0, r):
            y1=max(0,y0-r); y2=min(h,y0+r+1); x1=max(0,x0-r); x2=min(w,x0+r+1)
            yy,xx=np.ogrid[y1:y2,x1:x2]; sub=m[y1:y2,x1:x2]
            sub[(yy-y0)**2+(xx-x0)**2<=r*r]=0.0; m[y1:y2,x1:x2]=sub

        if ys.size:
            order = np.argsort(-mag[ys, xs])[:max_peaks]
            for y0, x0 in zip(ys[order], xs[order]):
                notch(mask, y0, x0, notch_r)
                ys2, xs2 = 2*cy - y0, 2*cx - x0
                if 0<=ys2<h and 0<=xs2<w:
                    notch(mask, ys2, xs2, notch_r)

        # DC erhalten
        y1=max(0,cy-inner_keep_r); y2=min(h,cy+inner_keep_r+1)
        x1=max(0,cx-inner_keep_r); x2=min(w,cx+inner_keep_r+1)
        yy,xx=np.ogrid[y1:y2,x1:x2]; sub=mask[y1:y2,x1:x2]
        sub[(yy-cy)**2+(xx-cx)**2<=inner_keep_r**2]=1.0; mask[y1:y2,x1:x2]=sub

        img_f = np.real(np.fft.ifft2(np.fft.ifftshift(fft_shift * mask)))
        mn, mx = float(img_f.min()), float(img_f.max())
        if not np.isfinite(mn) or not np.isfinite(mx) or mx-mn < 1e-12:
            return np.zeros_like(gf32, np.uint8)
        return (255*(img_f - mn)/max(1e-6,(mx-mn))).clip(0,255).astype(np.uint8)

    # ---- ggf. FFT anwenden, sonst auf 8-bit normalisieren ----
    if do_fft:
        gray_u8 = _fft_grid_remove(gray_f32)
    else:
        mn, mx = float(gray_f32.min()), float(gray_f32.max())
        gray_u8 = (255*(gray_f32 - mn)/max(1e-6,(mx-mn))).clip(0,255).astype(np.uint8)

    # ---- Empfindlichkeit → Parameter (low→high Interpolation) ----
    bg_sigma         = float(np.interp(sensitivity, [0,1], [23.0, 14.0]))
    dog_sigma_small  = float(np.interp(sensitivity, [0,1], [1.0,  1.3]))
    dog_sigma_large  = float(np.interp(sensitivity, [0,1], [3.6,  3.0]))
    min_circularity  = float(np.interp(sensitivity, [0,1], [0.70, 0.55]))
    min_contrast_rel = float(np.interp(sensitivity, [0,1], [0.20, 0.10]))
    min_diam_px, max_diam_px = 8, 60
    border_exclude, min_dist_px = 10, 9

    # ---- Vorverarbeitung, DoG, Otsu-Binarisierung ----
    g = gray_u8.astype(np.float32)
    bg = cv2.GaussianBlur(g, (0,0), bg_sigma)
    g_corr = cv2.subtract(g, bg)
    g_corr = cv2.normalize(g_corr, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    g_corr = cv2.bilateralFilter(g_corr, d=5, sigmaColor=10, sigmaSpace=6)
    small = cv2.GaussianBlur(g_corr, (0,0), dog_sigma_small)
    large = cv2.GaussianBlur(g_corr, (0,0), dog_sigma_large)
    dog = cv2.subtract(small, large)
    dog = cv2.normalize(dog, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, th = cv2.threshold(dog, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3,3), np.uint8), 1)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8), 1)
    b = border_exclude
    th[:b,:] = 0; th[-b:,:] = 0; th[:,:b] = 0; th[:,-b:] = 0

    # ---- Konturen filtern (Größe, Rundheit, Kontrast, Mindestabstand) ----
    cnts,_ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = np.pi*(min_diam_px/2)**2; max_area = np.pi*(max_diam_px/2)**2
    centers=[]; kept=[]; rows=[]
    h,w = g.shape
    for c in cnts:
        area = cv2.contourArea(c)
        if not (min_area <= area <= max_area): continue
        per = cv2.arcLength(c, True)
        if per <= 1e-6: continue
        circ = 4.0*np.pi*area/(per*per)
        if circ < min_circularity: continue
        x,y,cw,ch = cv2.boundingRect(c)
        x1,y1 = max(0,x-5), max(0,y-5)
        x2,y2 = min(w,x+cw+5), min(h,y+ch+5)
        roi = g_corr[y:y+ch, x:x+cw]; rim = g_corr[y1:y2, x1:x2]
        obj = float(np.mean(roi)) if roi.size else 0.0
        sur = float(np.mean(rim)) if rim.size else 1.0
        rel = abs(obj - sur) / max(1.0, sur)
        if rel < min_contrast_rel: continue
        M = cv2.moments(c)
        cx = M["m10"]/M["m00"] if M["m00"] else x + cw/2
        cy = M["m01"]/M["m00"] if M["m00"] else y + ch/2
        if any((cx-px)**2 + (cy-py)**2 < (min_dist_px**2) for px,py in centers): continue
        centers.append((cx,cy)); kept.append(c)
        rows.append({"cx":cx,"cy":cy,"area_px":area,"circularity":circ,"equiv_diam_px":2.0*np.sqrt(area/np.pi)})

    # ---- Overlay/Mask & DataFrame ----
    overlay = cv2.cvtColor(g_corr, cv2.COLOR_GRAY2BGR)
    mask = np.zeros_like(g_corr, np.uint8)
    cv2.drawContours(mask, kept, -1, 255, -1)
    cv2.drawContours(overlay, kept, -1, (255, 0, 0), 2)  # Blau (BGR)
    df = pd.DataFrame(rows)

    # ---- Optional speichern ----
    if save_dir:
        from pathlib import Path
        out = Path(save_dir); out.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out / "filtered.tif"), gray_u8)
        cv2.imwrite(str(out / "overlay.tif"), overlay)
        cv2.imwrite(str(out / "mask.tif"), mask)
        df.to_csv(str(out / "particles.csv"), index=False)

    return overlay, mask, df

# ----------------- AUTOFOKUS / WORKFLOWS -----------------
def autofocus():
    global z_slices
    z_slices = []
    beste_fokus_bewertung = -1
    focus_range = 2000
    focus_position = current_pos(20)
    startpos = int(current_pos(20) - focus_range / 2)
    endpos = int(current_pos(20) + focus_range / 2)
    focus_frame = None

    move_to_pos(z_addr, int(startpos))
    time.sleep(0.5)

    for pos in range(startpos, endpos + 40, 100):
        frame = dino_lite.capture_image()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        z_slices.append(frame)
        fokus_bewertung = cv2.Laplacian(frame, cv2.CV_64F).var()
        if fokus_bewertung > beste_fokus_bewertung:
            beste_fokus_bewertung = fokus_bewertung
            focus_position = current_pos(20)
            focus_frame = frame
        move_to_pos(z_addr, pos)

    move_to_pos(z_addr, focus_position)
    time.sleep(1)
    focus_frame = dino_lite.capture_image()
    return focus_frame

def autofocusblocked():
    print("Autofocus is currently blocked. Z motor cannot be used!")

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

def process_image(stitched_image):
    global latest_frame, particle_total, latest_base_bgr

    focus_frame = stitched_image
    latest_frame = focus_frame  # für Slider-Updates

    # Basismotiv (BGR) – Rücksprungziel nach Flash
    if focus_frame.ndim == 2:
        base_bgr = cv2.cvtColor(focus_frame, cv2.COLOR_GRAY2BGR)
    else:
        base_bgr = focus_frame.copy()
    latest_base_bgr = base_bgr.copy()

    cv2.imwrite('focused_image.tif', focus_frame)

    # Detection
    overlay, mask, df = particle_detection(
        focus_frame,
        sensitivity=DETECTION_SENSITIVITY,
        do_fft=True,
        save_dir=filedir
    )

    total = int(len(df))
    QMetaObject.invokeMethod(gui.particle_count, "setPlainText",
                             Qt.QueuedConnection, Q_ARG(str, str(total)))

    particle_total += total
    QMetaObject.invokeMethod(gui.particle_count_2, "setPlainText",
                             Qt.QueuedConnection, Q_ARG(str, str(particle_total)))

    threshold = 5
    gui.particle_count.setStyleSheet("background-color: rgb(130,0,0);" if total > threshold else "")

    # 1) Overlay + Count im GUI-Thread kurz einblenden (Signal)
    bridge.doFlash.emit(base_bgr, overlay, total)

    # 2) Live-Chart aktualisieren
    gui.livechart.addValue.emit(total)

    # detected.tif für spätere Messung
    cv2.imwrite(os.path.join(filedir, "detected.tif"), overlay)

    return focus_frame

def stitch():
    imagesy = []
    imagesx = []

    start_y, end_y = startpos_y, 224620

    for posx in range(startpos_x, startpos_x + 100000, 13500):
        move_to_pos(x_addr, posx)
        time.sleep(1)

        for posy in range(start_y, end_y, -9000 if start_y > end_y else 9000):
            move_to_pos(y_addr, posy)
            frame = autofocus()
            time.sleep(1)

            if start_y < end_y:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            imagesy.append(frame)
            process_image(frame)

        y_image = cv2.vconcat(imagesy)
        y_image = cv2.rotate(y_image, cv2.ROTATE_180)
        imagesx.append(y_image)
        imagesy.clear()
        start_y, end_y = end_y, start_y

    stitched_image = cv2.hconcat(imagesx)
    combined_image_rgb = cv2.cvtColor(stitched_image, cv2.COLOR_BGR2RGB)
    Image.fromarray(combined_image_rgb).save("C:/Users/LVBT/Desktop/Combined_Image.png")
    create_particle_plot(particle_diameters, stitched_image)

def start_particle_thread():
    global thread
    thread = QThread()
    thread.run = stitch
    thread.start()

# ----------------- ANGLE / PIEZO WORKFLOWS -----------------
def startpos():
    move_to_pos(x_addr, startpos_x)
    time.sleep(2)
    move_to_pos(y_addr, startpos_y)
    time.sleep(2)
    move_to_pos(z_addr, startpos_z)

def angle():
    move_to_pos(19, 210000)
    time.sleep(6)
    image_start = dino_lite.capture_image()
    least_squares_sums = []
    positions = list(range(0, 5000, 100))
    for posy in positions:
        image_pos = dino_lite.capture_image()
        cv2.imwrite(f'C:/Users/Lvbttest/Desktop/Angle/angle_{posy}.tif', image_pos)
        difference = image_start.astype(np.float32) - image_pos.astype(np.float32)
        squared_difference = np.square(difference)
        least_squares_sum = np.sum(squared_difference)
        print(f"Position {posy}, Least Squares Sum: {least_squares_sum}")
        least_squares_sums.append(least_squares_sum)
        set_analog_output(0xD7, 0xC0, posy)
        time.sleep(1)

    min_index = np.argmin(least_squares_sums)
    min_value = least_squares_sums[min_index]

    df = pd.DataFrame({'Position': positions, 'LeastSqaure': least_squares_sums})
    df.to_excel('Rohdaten.xlsx')
    plt.plot(positions, least_squares_sums, marker='o', linewidth=0.1)

    plt.title('Least Squares Summen für verschiedene Positionen')
    plt.xlabel('Position')
    plt.ylabel('Least Squares Summe')
    plt.grid(True)
    plt.scatter(positions[min_index], min_value, color='red', zorder=5)
    plt.annotate(f'Min: {min_value:.2f}', (positions[min_index], min_value), textcoords="offset points", xytext=(0,10), ha='center', color='red')
    plt.show()

def GratingShiftwSave():
    print("Starting an angle measurement!")
    dirname = "/piezo_angle_meas"
    move_to_pos(x_addr, SIM31_SEcornerpos[0])
    move_to_pos(y_addr, SIM31_SEcornerpos[1])
    time.sleep(3)
    voltage_range = np.arange(0, maxVolt*OP_amp_factor, step=voltage_step*OP_amp_factor, dtype=int)
    os.mkdir(filedir + dirname)
    for i in range(len(voltage_range)):
        print("New voltage: {} V".format(voltage_range[i]))
        set_analog_output(volt_addr, volt_pltf, int(voltage_range[i]/OP_amp_factor))
        time.sleep(0.5)
        new_image = dino_lite.capture_image()
        cv2.imwrite(filedir + dirname + f"\\Voltage_{voltage_range[i]}mV.tif", new_image)

    print("Finished acquiring voltage steps!")
    set_analog_output(volt_addr, volt_pltf, 0)

def acquire_single_frame():
    """Acquire single frame for grating angle measurement"""
    new_image = dino_lite.capture_image()
    res_frame = np.zeros((new_image.shape[0], new_image.shape[1]), dtype="uint16")
    for z in range(3):
        res_frame += new_image[:,:,z]
    return res_frame

def acquire_shiftstack(voltage_range):
    """ Acquisition function for piezo grating shift angle measurements"""
    new_image = dino_lite.capture_image()
    print("Captured test image, shape is:", new_image.shape)
    pxly, pxlx, pxlz  = new_image.shape
    shiftstack = np.zeros((len(voltage_range), pxly, pxlx), dtype="uint16")
    print("Shape of stack is:", shiftstack.shape)

    for i in range(len(voltage_range)):
        print("New voltage: {} V".format(voltage_range[i]))
        set_analog_output(volt_addr, volt_pltf, int(voltage_range[i]/OP_amp_factor))
        time.sleep(0.5)
        new_image = dino_lite.capture_image()
        for z in range(3):
            shiftstack[i] += new_image[:,:,z]

    print("Finished acquiring voltage steps!")
    set_analog_output(volt_addr, volt_pltf, 0)
    return shiftstack

def MeasureShiftFFT():
    print("Starting piezo angle measurement based on grating displacement and FFT")
    move_to_pos(z_addr, startpos_z + working_distance_dif)
    move_to_pos(x_addr, SIM31_centerpos[0])
    move_to_pos(y_addr, SIM31_centerpos[1])
    autofocus()
    time.sleep(2.5)

    voltage_range = np.arange(0, maxVolt*OP_amp_factor, step=voltage_step*OP_amp_factor, dtype=int)
    shiftstack = acquire_shiftstack(voltage_range)

    print("Got stack! Proceeding with analysis. Using FFT")
    shiftstack = np.fliplr(shiftstack)
    piezo_angle, grating_angle = AAF.AnalysePiezoAngleFFT(shiftstack)
    print("Piezo angle is: {} degrees.".format(piezo_angle))
    update_grating_angle_error(grating_angle, piezo_angle)
    print("Finished Shift measurement and analysis using FFT.")

def save_shiftstack(shiftstack, dirname="/Testmeasurement"):
    shiftstack_rot90CCW = np.rot90(shiftstack, k=1, axes=(1,2))
    os.mkdir(filedir + dirname)
    tif.imwrite(filedir + dirname + "/BWstack_rotated.tif", shiftstack_rot90CCW.astype('uint16'), photometric='minisblack')
    print("Saved stack!")
    print(filedir + dirname + "/BWstack_rotated.tif")

def MeasureShiftGratingEdge():
    print("Starting piezo angle measurement based on grating edge displacement")
    move_to_pos(x_addr, SIM31_SEcornerpos[0])
    time.sleep(2.5)
    move_to_pos(y_addr, SIM31_SEcornerpos[1])
    time.sleep(5)

    voltage_range = np.arange(0, maxVolt*OP_amp_factor, step=voltage_step*OP_amp_factor*2, dtype=int)
    shiftstack = acquire_shiftstack(voltage_range)
    print("Got stack! Proceeding with analysis. Using error function of grating edge drop")

    shiftDy = -150
    shiftDx = -200
    piezo_angle, grating_angle = AAF.AnalysePiezoAngleGratingEdge(shiftstack, shiftDy, shiftDx)
    print("Piezo angle is: {} degrees.".format(piezo_angle))
    update_grating_angle_error(grating_angle, piezo_angle)

def MeasureSingleImageGratingAngle():
    global piezoshift_angle_to_cam, grating_angle
    print("Measuring grating angle from single SIM 31 grating image.")
    move_to_pos(y_addr, SIM31_centerpos[1])
    time.sleep(1)
    move_to_pos(x_addr, SIM31_centerpos[0])
    time.sleep(1)

    single_frame = acquire_single_frame()
    grating_angle  = AAF.SingleImageGratingAngle(single_frame)
    print("Grating angle is {} degrees.".format(grating_angle))
    update_grating_angle_error(grating_angle, piezoshift_angle_to_cam)

def liveAngle():
    global piezoshift_angle_to_cam, grating_angle
    single_frame = acquire_single_frame()
    single_frame = np.fliplr(single_frame)
    grating_angle  = AAF.SingleImageGratingAngle(single_frame)
    angle = update_grating_angle_error(grating_angle, piezoshift_angle_to_cam)
    gui.label.setText(f"{angle}")
    gui.angle_dial.setValue(int(angle))

def angle_processing():
    global angle_processing_active
    MeasureShiftFFT()
    gui.pushButton.setStyleSheet("background-color: red; color: white;")
    gui.pushButton.setText("Winkel Justage stoppen")
    while angle_processing_active:
        liveAngle()
        fft_thread.msleep(100)

def start_angle_processing_thread():
    global fft_thread, angle_processing_active
    fft_thread = QThread()
    fft_thread.run = angle_processing
    fft_thread.start()
    angle_processing_active = True
    gui.pushButton.setText("Kalibrierung läuft...")
    gui.pushButton.setStyleSheet("background-color: green; color: white;")

def stop_angle_processing_thread():
    global angle_processing_active
    angle_processing_active = False
    fft_thread.quit()
    fft_thread.wait()
    gui.pushButton.setText("Winkel Justage starten")
    gui.pushButton.setStyleSheet("")

def toggle_angle_processing():
    if angle_processing_active:
        stop_angle_processing_thread()
    else:
        start_angle_processing_thread()

def update_grating_angle_error(grating_angle, shift_angle):
    """Function to update piezo and grating angles and their errors"""
    global grating_angle_error
    global piezoshift_angle_to_cam
    global grating_angle_to_cam

    piezoshift_angle_to_cam = shift_angle
    grating_angle_to_cam = grating_angle

    grating_angle_error = -1*(grating_angle_to_cam - THEORIE_WINKEL_DEG - piezoshift_angle_to_cam) # degrees
    grating_angle_error_mrad = grating_angle_error * np.pi / 0.18
    print(f"New grating angle error is {round(grating_angle_error, 3)} degrees, or {round(grating_angle_error_mrad, 2)} mrad.")
    if (abs(grating_angle_error_mrad) < GRATING_ERROR_TOLERANCE_MRAD):
        print("Grating angle error is within tolerance of {} mrad!".format(GRATING_ERROR_TOLERANCE_MRAD))
    else:
        print("Tolerance not yet reached. Please adjust grating.")
        if grating_angle_error > 0:
            print("Adjust grating angle by turning grating in clockwise direction.")
        else:
            print("Adjust grating by turning grating in a counter-clockwise direction.")
    return grating_angle_error

def connect_DPC():
    dev = GCSDevice()
    devices = dev.EnumerateUSB()
    dev.ConnectUSB(devices[0])
    print("IDN:", dev.qIDN())
    ax = dev.qSAI()[0]
    dev.SVO(ax, True)
    pitools.startup(dev)
    dev.MOV(ax, 300.0)
    pitools.waitontarget(dev, [ax])
    print("POS:", dev.qPOS()[ax])
    dev.CloseConnection()

# ----------------- QT LIVE-VIEW -----------------
def update_frame():
    frame = dino_lite.capture_image()
    h, w, ch = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    qt_image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
    scene = QGraphicsScene()
    gui.graphicsView.setScene(scene)
    scene.clear()
    scene.addPixmap(QPixmap.fromImage(qt_image).scaled(gui.graphicsView.width(),
                                                       gui.graphicsView.height(),
                                                       Qt.KeepAspectRatio))

# ----------------- MODERNE DARK-GUI (code-only) -----------------
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(4, 2.2), tight_layout=True)
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Frame")
        self.ax.set_ylabel("Particles")
        self.ax.grid(True, alpha=0.25)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(170)

class LiveChart(QWidget):
    addValue = pyqtSignal(int)   # thread-safe updater
    def __init__(self, parent=None, max_points=300):
        super().__init__(parent)
        self.canvas = MplCanvas(self)
        self.values = deque(maxlen=max_points)
        self.x = deque(maxlen=max_points)
        self.counter = 0

        lay = QVBoxLayout(self)
        title = QLabel("Live: Particles / Frame", self)
        title.setStyleSheet("font-weight: 600;")
        lay.addWidget(title)
        lay.addWidget(self.canvas)

        self.line, = self.canvas.ax.plot([], [], linewidth=1.8)
        self.addValue.connect(self._on_add)

    @pyqtSlot(int)
    def _on_add(self, val:int):
        self.counter += 1
        self.values.append(val)
        self.x.append(self.counter)
        self.line.set_data(self.x, self.values)
        # autoscale
        if len(self.x) == 1:
            self.canvas.ax.set_xlim(0, 10)
            self.canvas.ax.set_ylim(0, max(5, val+5))
        else:
            self.canvas.ax.set_xlim(max(0, self.counter-300), self.counter+5)
            ymax = max(5, max(self.values)*1.25)
            self.canvas.ax.set_ylim(0, ymax)
        self.canvas.draw_idle()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Particle Analyzer & Angle Toolkit")
        self._apply_dark_theme()

        # ==== Center layout ====
        central = QWidget(self); self.setCentralWidget(central)
        root = QHBoxLayout(central); root.setContentsMargins(12,12,12,12); root.setSpacing(12)

        # --- Left: Image view ---
        left = QVBoxLayout(); left.setSpacing(8)
        self.graphicsView = QGraphicsView(self)
        self.graphicsView.setFrameShape(QFrame.NoFrame)
        left.addWidget(self.graphicsView, 1)

        # Status row (angle + counts)
        statusRow = QHBoxLayout()
        self.label = QLabel("0.0°")
        self.label.setToolTip("Aktueller Grating-Winkel (berechnet)")
        self.label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        statusRow.addWidget(QLabel("Angle:", self))
        statusRow.addWidget(self.label)
        statusRow.addStretch(1)

        self.particle_count = QTextEdit(self);  self.particle_count.setFixedHeight(36)
        self.particle_count.setReadOnly(True)
        self.particle_count.setPlaceholderText("Frame Count")
        self.particle_count_2 = QTextEdit(self); self.particle_count_2.setFixedHeight(36)
        self.particle_count_2.setReadOnly(True)
        self.particle_count_2.setPlaceholderText("Total Count")
        for w in (self.particle_count, self.particle_count_2):
            w.setStyleSheet("QTextEdit{border-radius:10px;padding:6px 10px;}")

        statusRow.addWidget(QLabel("Frame:", self))
        statusRow.addWidget(self.particle_count, 1)
        statusRow.addWidget(QLabel("Total:", self))
        statusRow.addWidget(self.particle_count_2, 1)
        left.addLayout(statusRow)

        # Live chart under image
        self.livechart = LiveChart(self)
        left.addWidget(self.livechart)

        # --- Right: Controls ---
        right = QVBoxLayout(); right.setSpacing(10)

        self.angle_dial = QDial(self); self.angle_dial.setNotchesVisible(True)
        self.angle_dial.setRange(-180, 180); self.angle_dial.setValue(0)
        self.angle_dial.setToolTip("Winkelanzeige (read-only)")
        self.angle_dial.setEnabled(False)
        right.addWidget(self._wrap("Angle Dial", self.angle_dial))

        self.pushButton   = QPushButton("Winkel Justage starten")
        self.pushButton_2 = QPushButton("Scan starten")
        self.pushButton_3 = QPushButton("Autofokus")
        for b in (self.pushButton, self.pushButton_2, self.pushButton_3):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(42)
            b.setStyleSheet("QPushButton{border-radius:12px;font-weight:600;}")

        right.addWidget(self.pushButton)
        right.addWidget(self.pushButton_2)
        right.addWidget(self.pushButton_3)
        right.addStretch(1)

        # assemble split
        root.addLayout(left, 3)
        root.addLayout(right, 1)

        # ==== Sensitivity Dock ====
        dock = QDockWidget("Empfindlichkeit", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dockw = QWidget(dock); dlay = QHBoxLayout(dockw)
        self.sensLabel = QLabel("balanced_high", dockw)
        self.sensSlider = QSlider(Qt.Horizontal, dockw); self.sensSlider.setRange(0,100)
        self.sensSlider.setValue(int(DETECTION_SENSITIVITY*100))
        dlay.addWidget(QLabel("Empfindlichkeit:"))
        dlay.addWidget(self.sensSlider, 1)
        dlay.addWidget(self.sensLabel)
        dock.setWidget(dockw)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        # ==== Wire up external callbacks (deine Funktionsnamen!) ====
        self.pushButton.clicked.connect(toggle_angle_processing)
        self.pushButton_2.clicked.connect(start_particle_thread)
        self.pushButton_3.clicked.connect(autofocus)

    def _wrap(self, title:str, widget:QWidget) -> QWidget:
        box = QWidget(self); lay = QVBoxLayout(box); lay.setContentsMargins(0,0,0,0)
        lab = QLabel(title, box); lab.setStyleSheet("font-weight:600;")
        lay.addWidget(lab); lay.addWidget(widget)
        return box

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background:#0f1115; }
            QWidget { color:#e6e6e6; font-family:'Segoe UI', Arial, sans-serif; font-size:12pt; }
            QGraphicsView { background:#151820; border-radius:14px; }
            QDockWidget { titlebar-close-icon: url(none); titlebar-normal-icon:url(none); }
            QDockWidget::title { background:#12151c; padding:8px 10px; border-bottom:1px solid #1e2230; }
            QLabel { color:#eaeaea; }
            QSlider::groove:horizontal { height:6px; background:#202433; border-radius:3px; }
            QSlider::handle:horizontal { width:18px; background:#3a7bfd; border-radius:9px; margin:-6px 0; }
            QDial { background:#12151c; }
            QTextEdit { background:#12151c; border:1px solid #222638; }
            QPushButton { background:#1b2030; border:1px solid #222638; }
            QPushButton:hover { background:#242b3f; }
            QPushButton:pressed { background:#29314a; }
        """)
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#0f1115"))
        pal.setColor(QPalette.Base, QColor("#12151c"))
        pal.setColor(QPalette.AlternateBase, QColor("#151820"))
        pal.setColor(QPalette.Text, QColor("#e6e6e6"))
        pal.setColor(QPalette.ButtonText, QColor("#f0f0f0"))
        pal.setColor(QPalette.Button, QColor("#1b2030"))
        pal.setColor(QPalette.Highlight, QColor("#3a7bfd"))
        pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)

# ======= GUI-Factory ersetzt .ui =======
def create_GUI2():
    global gui, timer_camera, bridge

    app = QApplication(sys.argv)
    gui = MainWindow()

    # Bridge im GUI-Thread
    global bridge
    bridge = GuiBridge(gui)

    # Empfindlichkeits-Slider Callback (Live-Rerun)
    def on_sensitivity_changed(val):
        global DETECTION_SENSITIVITY, latest_frame, latest_base_bgr
        DETECTION_SENSITIVITY = float(val) / 100.0
        lvl = "balanced_low" if DETECTION_SENSITIVITY < 0.33 else ("balanced_mid" if DETECTION_SENSITIVITY < 0.66 else "balanced_high")
        gui.sensLabel.setText(lvl)

        if latest_frame is not None:
            overlay, mask, df = particle_detection(
                latest_frame,
                sensitivity=DETECTION_SENSITIVITY,
                do_fft=True,
                save_dir=None
            )
            total = int(len(df))
            QMetaObject.invokeMethod(gui.particle_count, "setPlainText",
                                     Qt.QueuedConnection, Q_ARG(str, str(total)))
            threshold = 5
            gui.particle_count.setStyleSheet("background-color: rgb(130,0,0);" if total > threshold else "")

            base = latest_base_bgr if latest_base_bgr is not None else (
                cv2.cvtColor(latest_frame, cv2.COLOR_GRAY2BGR) if latest_frame.ndim == 2 else latest_frame
            )
            bridge.doFlash.emit(base, overlay, total)
            gui.livechart.addValue.emit(total)

    gui.sensSlider.valueChanged.connect(on_sensitivity_changed)

    # Kamera-Update (wie zuvor)
    timer_camera = QTimer()
    timer_camera.timeout.connect(update_frame)
    timer_camera.start(30)

    gui.resize(1320, 820)
    gui.show()
    sys.exit(app.exec_())

# ----------------- MAIN -----------------
if __name__ == "__main__":
    init_plot()
    dino_lite = DinoLiteController()
    pos = 0
    filedir = os.getcwd()
    create_GUI2()
