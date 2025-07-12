# Telloドローン制御スクリプト (QRコードリーダー付き) - `drone_qr.py`

## 概要

このPythonスクリプトは、Ryze Telloドローンを制御し、ドローンからのビデオストリームを表示し、ビデオ内のQRコードを検出し、ドローンのステータス情報（バッテリー残量、飛行時間など）を表示する機能を提供します。キーボード入力によりドローンを操作できます。

## 依存関係

このスクリプトを実行するには、以下のライブラリが必要です。

-   `socket`: ネットワーク通信（UDP）のために使用されます。
-   `threading`: バックグラウンドタスク（データ受信、情報問い合わせ）を並行して実行するために使用されます。
-   `cv2` (OpenCV): カメラ映像の処理、QRコードの検出、映像表示のために使用されます。
-   `time`: 遅延処理や定期的なタスク実行のために使用されます。
-   `numpy`: OpenCVで画像データを効率的に扱うために内部的に使用されることがあります。

これらのライブラリは、通常 `pip install opencv-python numpy` コマンドでインストールできます。`socket`, `threading`, `time` はPythonの標準ライブラリです。

## 主要な構成要素

### 1. グローバル変数と定数

-   `TELLO_IP`: TelloドローンのデフォルトIPアドレス (`'192.168.10.1'`)。
-   `TELLO_PORT`: Telloドローンとのコマンド送受信用ポート番号 (`8889`)。
-   `TELLO_ADDRESS`: `(TELLO_IP, TELLO_PORT)` のタプル。
-   `TELLO_CAMERA_ADDRESS`: Telloドローンからのビデオストリーム受信用のUDPアドレス (`'udp://@0.0.0.0:11111?overrun_nonfatal=1&fifo_size=50000000'`)。
-   `command_text`: 最後に送信されたコマンドを画面に表示するための文字列。初期値は `"None"`。
-   `battery_text`: バッテリー残量を表示するための文字列。初期値は `"Battery:"`。
-   `time_text`: 飛行時間を表示するための文字列。初期値は `"Time:"`。
-   `status_text`: ドローンからの一般的なステータスメッセージを表示するための文字列。初期値は `"Status:"`。
-   `cap`: `cv2.VideoCapture` オブジェクト。カメラ映像のキャプチャに使用。
-   `response`: データ受信用の変数（現在は直接使用されていない模様）。
-   `sock`: UDP通信用のソケットオブジェクト。
-   `qcd`: `cv2.QRCodeDetector` オブジェクト。QRコードの検出とデコードに使用。

### 2. UDPデータ受信関数 (`udp_receiver`)

-   この関数は独立したスレッドで実行され、TelloドローンからのUDPパケットを継続的に受信します。
-   受信したデータはUTF-8でデコードされ、内容に応じて以下のグローバル変数を更新します。
    -   数字のみの場合: `battery_text` (例: "Battery:80%")
    -   末尾が 's' の場合: `time_text` (例: "Time:120s")
    -   上記以外の場合: `status_text` (例: "Status:ok")
-   例外が発生した場合は無視します (`pass`)。

### 3. 情報問い合わせ関数 (`ask`)

-   この関数も独立したスレッドで実行され、0.5秒ごとにTelloドローンにバッテリー残量 (`battery?`) と飛行時間 (`time?`) を問い合わせるコマンドを送信します。
-   これにより、`udp_receiver` が定期的に最新の情報を取得できるようになります。
-   例外が発生した場合は無視します (`pass`)。

### 4. ドローン制御関数群

これらの関数は、特定のコマンド文字列をUTF-8でエンコードし、`TELLO_ADDRESS` 宛にUDPで送信します。

-   `takeoff()`: ドローンを離陸させます (`takeoff`)。
-   `land()`: ドローンを着陸させます (`land`)。
-   `up()`: ドローンを20cm上昇させます (`up 20`)。
-   `down()`: ドローンを20cm下降させます (`down 20`)。
-   `forward()`: ドローンを20cm前進させます (`forward 20`)。
-   `back()`: ドローンを20cm後進させます (`back 20`)。
-   `right()`: ドローンを20cm右に進ませます (`right 20`)。
-   `left()`: ドローンを20cm左に進ませます (`left 20`)。
-   `cw()`: ドローンを時計回りに30度回転させます (`cw 30`)。
-   `ccw()`: ドローンを反時計回りに30度回転させます (`ccw 30`)。
-   `set_speed(n=40)`: ドローンの速度を設定します（デフォルトは40cm/s）。コマンドは `speed {n}`。

### 5. 初期化処理

スクリプトのメイン部分が実行される前に、以下の初期化が行われます。

1.  **ソケットの作成とバインド**:
    -   `socket.socket(socket.AF_INET, socket.SOCK_DGRAM)` でUDPソケットを作成します。
    -   `sock.bind(('', TELLO_PORT))` で、ローカルの全IPアドレスの `TELLO_PORT` (8889) をリッスンするようにソケットをバインドします。これにより、Telloからの応答を受信できます。

2.  **スレッドの起動**:
    -   `ask_thread`: `ask` 関数をターゲットとするスレッドを作成し、デーモンスレッドとして起動します。
    -   `recv_thread`: `udp_receiver` 関数をターゲットとするスレッドを作成し、デーモンスレッドとして起動します。

3.  **Tello SDKモードとストリーミングの有効化**:
    -   `sock.sendto('command'.encode('utf-8'), TELLO_ADDRESS)`: TelloをSDKモードにします。
    -   `time.sleep(1)`: コマンド処理のための待機。
    -   `sock.sendto('streamon'.encode('utf-8'), TELLO_ADDRESS)`: Telloのビデオストリーミングを開始します。
    -   `time.sleep(1)`: ストリーミング開始のための待機。

4.  **ビデオキャプチャの初期化**:
    -   `cap = cv2.VideoCapture(TELLO_CAMERA_ADDRESS)`: Telloのカメラストリームを開くための `VideoCapture` オブジェクトを作成します。
    -   `if not cap.isOpened(): cap.open(TELLO_CAMERA_ADDRESS)`: もし開いていなければ再度開こうとします。
    -   `time.sleep(1)`: カメラ初期化のための待機。

5.  **QRコード検出器の初期化**:
    -   `qcd = cv2.QRCodeDetector()`: QRコード検出用のインスタンスを作成します。

### 6. メインループ (`while True`)

このループは、スクリプトの主要な処理を実行し続けます。

1.  **フレームの読み込みとリサイズ**:
    -   `ret, frame = cap.read()`: カメラから1フレームを読み込みます。
    -   `cnt_frame += 1`: フレームカウンターをインクリメントします。
    -   フレームが空の場合はスキップします。
    -   `frame_resized = cv2.resize(frame, (frame_width//3, frame_height//3))`: 処理負荷軽減のため、フレームサイズを縦横それぞれ1/3にリサイズします。
    -   `frame_output = frame_resized`: 表示用のフレームを準備します。

2.  **QRコードの検出 (5フレームごと)**:
    -   `if cnt_frame % 5 == 0:`: 処理負荷を考慮し、5フレームに1回の頻度でQRコード検出を行います。
    -   `retval, decoded_info, points, straight_qrcode = qcd.detectAndDecodeMulti(frame_resized)`: リサイズされたフレームから複数のQRコードを検出し、デコードします。
        -   `retval`: 検出に成功したかどうか。
        -   `decoded_info`: デコードされた情報（文字列のリスト）。
        -   `points`: 検出されたQRコードの各頂点の座標。
        -   `straight_qrcode`: 補正されたQRコード画像。
    -   QRコードが検出された場合 (`retval` が真):
        -   `frame_qrdet = cv2.polylines(frame_resized, points.astype(int), True, (0, 255, 0), 3)`: 検出されたQRコードを緑色の線で囲みます。
        -   `frame_output = frame_qrdet`: 表示用フレームを更新します。
    -   デコードされた情報がある場合 (`len(decoded_info) != 0`):
        -   `print(f"読み取り結果(result)：{decoded_info}")`: デコードされた情報をコンソールに出力します。

3.  **情報表示のオーバーレイ**:
    -   `cv2.putText()` を使用して、以下の情報を `frame_output` に描画します。
        -   送信コマンド (`command_text`)
        -   バッテリー残量 (`battery_text`)
        -   飛行時間 (`time_text`)
        -   ステータス (`status_text`)
    -   これらのテキストは緑色で、左上に表示されます。

4.  **映像表示**:
    -   `cv2.imshow('Tello Camera View', frame_output)`: 加工されたフレームを 'Tello Camera View' という名前のウィンドウに表示します。

5.  **キー入力処理**:
    -   `key = cv2.waitKey(1)`: 1ミリ秒間キー入力を待ちます。
    -   キー入力に応じて以下の処理を実行します。
        -   `ESC` (キーコード 27): ループを終了します。
        -   `w`: 前進 (`forward()`)、`command_text` を "Forward" に更新。
        -   `s`: 後進 (`back()`)、`command_text` を "Back" に更新。
        -   `a`: 左進 (`left()`)、`command_text` を "Left" に更新。
        -   `d`: 右進 (`right()`)、`command_text` を "Right" に更新。
        -   `t`: 離陸 (`takeoff()`)、`command_text` を "Take off" に更新。
        -   `l`: 着陸 (`land()`)、`command_text` を "Land" に更新。
        -   `r`: 上昇 (`up()`)、`command_text` を "Up" に更新。
        -   `c`: 下降 (`down()`)、`command_text` を "Down" に更新。
        -   `q`: 左回転 (`ccw()`)、`command_text` を "Ccw" に更新。
        -   `e`: 右回転 (`cw()`)、`command_text` を "Cw" に更新。
        -   `m`: 速度変更 (`set_speed()`)、`command_text` を "Changed speed" に更新。

### 7. クリーンアップ処理

メインループが終了した後（ESCキーが押された後）、以下の処理が行われます。

1.  `cap.release()`: ビデオキャプチャリソースを解放します。
2.  `cv2.destroyAllWindows()`: OpenCVで開かれた全てのウィンドウを閉じます。
3.  `sock.sendto('streamoff'.encode('utf-8'), TELLO_ADDRESS)`: Telloのビデオストリーミングを停止します。

## 実行方法

1.  PCをTelloドローンのWi-Fiネットワークに接続します。
2.  ターミナルまたはコマンドプロンプトで、このスクリプト (`drone_qr.py`) があるディレクトリに移動します。
3.  `python drone_qr.py` コマンドを実行します。
4.  'Tello Camera View' というウィンドウが表示され、ドローンのカメラ映像と各種情報が表示されます。
5.  キーボードの各キーを押してドローンを操作します。
6.  ESCキーを押すとプログラムが終了します。

## 注意点

-   ドローンとの通信はUDPで行われるため、コマンドの到達や応答の受信が保証されるわけではありません。スクリプト内では、コマンド送信時のエラーハンドリングは `try-except` ブロックで行っていますが、応答がない場合の処理は限定的です。
-   QRコードの検出精度は、カメラの品質、照明条件、QRコードのサイズや状態に依存します。
-   ドローンの飛行には十分注意し、安全な場所で操作してください。
