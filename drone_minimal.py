import socket
import time
import cv2
import numpy as np

# Tello側のローカルIPアドレス(デフォルト)、宛先ポート番号(コマンドモード用)
TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
TELLO_ADDRESS = (TELLO_IP, TELLO_PORT)
TELLO_CAMERA_ADDRESS = 'udp://@0.0.0.0:11111?overrun_nonfatal=1&fifo_size=50000000'

# 通信用のソケットを作成
# ※アドレスファミリ：AF_INET（IPv4）、ソケットタイプ：SOCK_DGRAM（UDP）
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 自ホストで使用するIPアドレスとポート番号を設定
# Telloからのステータス情報を受信するために必要
sock.bind(('', TELLO_PORT))

# 離陸
def takeoff():
    print("離陸コマンド送信中...")
    try:
        sent = sock.sendto('takeoff'.encode(encoding="utf-8"), TELLO_ADDRESS)
        print("離陸コマンド送信完了")
    except Exception as e:
        print(f"離陸コマンド送信エラー: {e}")

# 着陸
def land():
    print("着陸コマンド送信中...")
    try:
        sent = sock.sendto('land'.encode(encoding="utf-8"), TELLO_ADDRESS)
        print("着陸コマンド送信完了")
    except Exception as e:
        print(f"着陸コマンド送信エラー: {e}")

def udp_receiver():
    """Telloからの応答を受信して表示する（デバッグ用）"""
    while True:
        try:
            data, server = sock.recvfrom(1518)
            response = data.decode(encoding="utf-8").strip()
            print(f"Telloからの応答: {response}")
        except Exception as e:
            # print(f"受信エラー: {e}") # ループが多すぎるのでコメントアウト
            pass

# 受信用スレッドの作成と開始 (オプション)
# import threading
# recv_thread = threading.Thread(target=udp_receiver)
# recv_thread.daemon = True
# recv_thread.start()

print("Telloミニマル制御スクリプト")
print("-----------------------------")
print("TelloをSDKモードにします...")

try:
    # コマンドモード開始
    sock.sendto('command'.encode('utf-8'), TELLO_ADDRESS)
    print("SDKモード有効化コマンド送信完了。Telloからの 'ok' 応答を待っています...")
    # Telloからの応答を少し待つ
    time.sleep(1) # 'ok'応答やエラーメッセージを受信するための時間

    # カメラ映像のストリーミング開始
    sock.sendto('streamon'.encode('utf-8'), TELLO_ADDRESS)
    print("ストリームオンコマンド送信完了。")
    time.sleep(1) # ストリーミング開始の準備時間

except Exception as e:
    print(f"SDKモードまたはストリームオン有効化コマンド送信エラー: {e}")
    exit()

# カメラキャプチャの準備
cap = cv2.VideoCapture(TELLO_CAMERA_ADDRESS)
if not cap.isOpened():
    print("カメラストリームを開けませんでした。終了します。")
    sock.close()
    exit()

print("-----------------------------")
print("操作コマンド:")
print("  't'キー: 離陸")
print("  'l'キー: 着陸")
print("  'ESC'キー: 終了")
print("-----------------------------")

# ウィンドウの作成
WINDOW_NAME = "Tello Camera View"
cv2.namedWindow(WINDOW_NAME)

# FPS制御用
TARGET_FPS = 3 # 目標表示FPS
display_frame_interval = 1.0 / TARGET_FPS
last_display_time = 0

# カメラフレーム読み込みとバッファ管理用スレッド
import threading
from collections import deque # 最新フレームを保持するためのキュー

# OpenCVの内部バッファはデフォルトで数フレーム持つことがある。
# VideoCaptureのプロパティでバッファサイズを設定できる場合があるが、
# TelloのUDPストリームでは効果がない可能性が高い。
# cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # 効果があればラッキー程度

# 最新の1フレームだけを保持するキュー
frame_buffer = deque(maxlen=1) # maxlen=1 で常に最新の1フレームのみ保持
stop_camera_thread = threading.Event()
camera_thread_lock = threading.Lock() # latest_frameへのアクセスを保護

def camera_reader_thread_with_buffer_clearing():
    global frame_buffer
    print("カメラ読み込みスレッド（バッファクリアリング付き）開始")
    
    # 最初のフレーム取得を試みる
    if cap.isOpened():
        for _ in range(5): # 最初の数フレームを読み飛ばしてバッファをクリアしようと試みる
            cap.grab() # フレームをデコードせずに内部バッファから取得し破棄
            time.sleep(0.01) # 少し待つ

    while not stop_camera_thread.is_set():
        if cap.isOpened():
            # grab()でフレームを取得し、バッファを進める
            # retrieve()で実際のフレームデータを取得する
            # これにより、OpenCVの内部バッファに古いフレームが溜まるのを軽減する
            grabbed = cap.grab() 
            if grabbed:
                ret, frame = cap.retrieve()
                if ret:
                    with camera_thread_lock:
                        frame_buffer.append(frame) # 新しいフレームをキューに追加（古いのは自動で消える）
                # else:
                    # print("カメラ読み込みスレッド: フレームretrieve失敗")
            # else:
                # print("カメラ読み込みスレッド: フレームgrab失敗")
        
        # CPU負荷を少し下げるために短いスリープ
        # 読み込み頻度は表示FPSより高く保つ
        time.sleep(0.02) # 約50FPSで読み込み試行 (Telloの実際のフレームレートに依存)
    print("カメラ読み込みスレッド終了")

camera_thread = threading.Thread(target=camera_reader_thread_with_buffer_clearing)
camera_thread.daemon = True
camera_thread.start()


while True:
    current_display_time = time.time()
    key = -1 # キー未入力
    display_this_frame = None

    if (current_display_time - last_display_time) >= display_frame_interval:
        last_display_time = current_display_time
        with camera_thread_lock:
            if frame_buffer: # バッファにフレームがあれば
                display_this_frame = frame_buffer[0] # 最新のフレームを取得 (キューなので常に最新)
        
        if display_this_frame is not None:
            cv2.imshow(WINDOW_NAME, display_this_frame)
        else:
            # まだフレームがないか、読み込みに失敗した場合
            error_frame = np.zeros((300, 400, 3), dtype=np.uint8)
            cv2.putText(error_frame, "Waiting for frame...", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            cv2.imshow(WINDOW_NAME, error_frame)
    
    key = cv2.waitKey(1) & 0xFF


    if key == 27:  # ESCキー
        print("終了します...")
        break
    elif key == ord('t'):
        print("'t'キー入力: 離陸試行")
        takeoff()
    elif key == ord('l'):
        print("'l'キー入力: 着陸試行")
        land()
    # elif key != 255 and key != -1 : # 255 or -1 はキー入力なしを示す場合がある
        # print(f"未知のキー入力: {key}")


# ソケットを閉じる (通常、デーモンスレッドが終了するまで待つか、明示的に閉じる)
# このスクリプトではメインスレッド終了時に自動的に閉じられる
print("カメラ読み込みスレッドを停止します...")
stop_camera_thread.set()
camera_thread.join(timeout=2) # スレッドが終了するのを待つ（最大2秒）
if camera_thread.is_alive():
    print("カメラ読み込みスレッドが時間内に終了しませんでした。")

print("ストリームをオフにし、ソケットを閉じて終了します。")
sock.sendto('streamoff'.encode('utf-8'), TELLO_ADDRESS)
time.sleep(0.5) # streamoffコマンドの処理待ち
sock.close()
if 'cap' in locals() and cap.isOpened():
    cap.release()
cv2.destroyAllWindows() # OpenCVウィンドウを閉じる
