#include <Arduino.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_wpa2.h"

// ===================
// WiFi Credentials (WPA2-Enterprise)
// ===================

// ===================
// ESP32-CAM AI-Thinker Pin Definitions
// ===================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define LED_GPIO_NUM       4  // Flash LED

httpd_handle_t stream_httpd = NULL;
httpd_handle_t camera_httpd = NULL;

// MJPEG stream boundary
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// basic HTML page for the webserver for debug
static const char PROGMEM INDEX_HTML[] = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <title>ESP32-CAM Stream</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #181818;
            color: #EFEFEF;
            text-align: center;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #03A9F4;
        }
        img {
            max-width: 100%;
            height: auto;
            border: 2px solid #03A9F4;
            border-radius: 10px;
        }
        .button {
            background-color: #03A9F4;
            border: none;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            font-size: 16px;
            margin: 10px;
            cursor: pointer;
            border-radius: 5px;
        }
        .button:hover {
            background-color: #0288D1;
        }
        .controls {
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>ESP32-CAM Web Server</h1>
    <img src="/stream" id="stream">
    <div class="controls">
        <button class="button" onclick="toggleFlash()">Toggle Flash</button>
        <button class="button" onclick="capturePhoto()">Capture Photo</button>
    </div>
    <script>
        function toggleFlash() {
            fetch('/flash');
        }
        function capturePhoto() {
            window.open('/capture', '_blank');
        }
    </script>
</body>
</html>
)rawliteral";

bool flashState = false;

// Handler for the root page
static esp_err_t index_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, INDEX_HTML, strlen(INDEX_HTML));
}

// Handler for capturing a single photo
static esp_err_t capture_handler(httpd_req_t *req) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("Camera capture failed");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    return res;
}

// Handler for MJPEG stream
static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t *fb = NULL;
    esp_err_t res = ESP_OK;
    char *part_buf[64];

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if (res != ESP_OK) {
        return res;
    }

    while (true) {
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Camera capture failed");
            res = ESP_FAIL;
        } else {
            size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, fb->len);
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            if (res == ESP_OK) {
                res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
            }
            if (res == ESP_OK) {
                res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
            }
            esp_camera_fb_return(fb);
        }
        if (res != ESP_OK) {
            break;
        }
    }
    return res;
}

// Handler for flash toggle
static esp_err_t flash_handler(httpd_req_t *req) {
    flashState = !flashState;
    digitalWrite(LED_GPIO_NUM, flashState);
    
    httpd_resp_set_type(req, "text/plain");
    return httpd_resp_send(req, flashState ? "Flash ON" : "Flash OFF", HTTPD_RESP_USE_STRLEN);
}

void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;

    httpd_uri_t index_uri = {
        .uri       = "/",
        .method    = HTTP_GET,
        .handler   = index_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t capture_uri = {
        .uri       = "/capture",
        .method    = HTTP_GET,
        .handler   = capture_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t flash_uri = {
        .uri       = "/flash",
        .method    = HTTP_GET,
        .handler   = flash_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t stream_uri = {
        .uri       = "/stream",
        .method    = HTTP_GET,
        .handler   = stream_handler,
        .user_ctx  = NULL
    };

    Serial.printf("Starting web server on port: '%d'\n", config.server_port);
    if (httpd_start(&camera_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(camera_httpd, &index_uri);
        httpd_register_uri_handler(camera_httpd, &capture_uri);
        httpd_register_uri_handler(camera_httpd, &flash_uri);
    }

    config.server_port += 1;
    config.ctrl_port += 1;
    Serial.printf("Starting stream server on port: '%d'\n", config.server_port);
    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
    }
}

void setup() {
    Serial.begin(115200);
    Serial.setDebugOutput(true);
    delay(1000);
    
    Serial.println();
    Serial.println("*********************************");
    Serial.println("ESP32-CAM Web Server Starting...");
    Serial.println("*********************************");

    // setup LED flash 
    pinMode(LED_GPIO_NUM, OUTPUT);
    digitalWrite(LED_GPIO_NUM, LOW);

    // camera config
    Serial.println("Configuring camera...");
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.frame_size = FRAMESIZE_UXGA;
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_LATEST;

    // frame settings
        if (psramFound()) {
        config.jpeg_quality = 15; // gotta fiddle with this, lower number = higher quality
        config.fb_count = 2;
        Serial.println("PSRAM found - using higher quality settings");
    } else {
        config.jpeg_quality = 12;
        config.fb_count = 1;
        Serial.println("No PSRAM - using lower quality settings");
    }

    // initialize cam
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x\n", err);
        return;
    }
    Serial.println("Camera initialized successfully");

    // sensor settings
    sensor_t *s = esp_camera_sensor_get();
    if (s) {
        s->set_brightness(s, 0);
        s->set_contrast(s, 0);
        s->set_saturation(s, 0);
        s->set_special_effect(s, 0);
        s->set_whitebal(s, 1);
        s->set_awb_gain(s, 1);
        s->set_wb_mode(s, 0);
        s->set_exposure_ctrl(s, 1);
        s->set_aec2(s, 0);
        s->set_gain_ctrl(s, 1);
        s->set_agc_gain(s, 0);
        s->set_gainceiling(s, (gainceiling_t)0);
        s->set_bpc(s, 0);
        s->set_wpc(s, 1);
        s->set_raw_gma(s, 1);
        s->set_lenc(s, 1);
        s->set_hmirror(s, 0);
        s->set_vflip(s, 1); // vertical flip enabled for correct input orientation
        s->set_dcw(s, 1);
        s->set_colorbar(s, 0);
    }

    // connect to wifi (WPA2-Enterprise for UofT)
    Serial.println("connecting to wifi...");
    WiFi.disconnect(true);
    WiFi.mode(WIFI_STA);
    
    esp_wifi_sta_wpa2_ent_set_identity((uint8_t *)username, strlen(username));
    esp_wifi_sta_wpa2_ent_set_username((uint8_t *)username, strlen(username));
    esp_wifi_sta_wpa2_ent_set_password((uint8_t *)password, strlen(password));
    esp_wifi_sta_wpa2_ent_enable();
    
    WiFi.begin(ssid);
    WiFi.setSleep(false);

    Serial.print("connecting to wifi (WPA2-Enterprise)");
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 60) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nwifi connected!");
        Serial.print("camera ready Go to: http://");
        Serial.println(WiFi.localIP());
        
        startCameraServer();
    } else {
        Serial.println("\nfailed to connect to wifi");
        Serial.println("please check credentials and restart");
    }
}

void loop() {
    delay(10000);
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("wifi connected, IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("wifi disconnected - attempting reconnect...");
        WiFi.reconnect();
    }
}
