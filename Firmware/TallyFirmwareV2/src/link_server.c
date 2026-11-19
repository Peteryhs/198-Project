#include "link_server.h"

#include <errno.h>
#include <string.h>

#include "accelerometer.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "frame.h"
#include "lwip/sockets.h"
#include "sampler.h"

static const char *TAG = "LINK";
static uint8_t device_mac[6];

#define POLL_US 10000
#define SAMPLES_FLUSH_US 100000
#define HEARTBEAT_US 1000000
#define MAX_FRAMES_PER_POLL 30 // a RESUME replay of 3,000 samples drains in about 1 s

typedef struct {
    int fd;
    bool streaming; // set frames flow only after START, RESUME or ABORT on this connection
    uint8_t rx[FRAME_MAX_BYTES];
    size_t rx_len;
    int64_t last_samples_us;
    int64_t next_heartbeat_us;
} client_t;

static void drop_client(client_t *c, const char *why)
{
    if (c->fd < 0) return;
    ESP_LOGW(TAG, "dropping client: %s", why);
    close(c->fd);
    c->fd = -1;
}

// One send() per frame in the normal case; loops only if lwIP accepts a partial write.
static bool send_frame(client_t *c, const uint8_t *buf, size_t len)
{
    size_t off = 0;
    while (off < len) {
        int n = send(c->fd, buf + off, len - off, 0);
        if (n <= 0) {
            drop_client(c, "send failed");
            return false;
        }
        off += (size_t)n;
    }
    return true;
}

static void accept_client(int listen_fd, client_t *c)
{
    struct sockaddr_in peer;
    socklen_t peer_len = sizeof(peer);
    int fd = accept(listen_fd, (struct sockaddr *)&peer, &peer_len);
    if (fd < 0) return;
    // Newest client wins: after a phone-side Wi-Fi drop the old socket can look alive for minutes,
    // and the reconnecting phone must get its HELLO within 3 s.
    drop_client(c, "replaced by a new connection");

    int one = 1;
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
    setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, &one, sizeof(one));
    struct timeval send_timeout = {.tv_sec = 2, .tv_usec = 0};
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &send_timeout, sizeof(send_timeout));

    c->fd = fd;
    c->streaming = false;
    c->rx_len = 0;
    c->last_samples_us = esp_timer_get_time();
    c->next_heartbeat_us = c->last_samples_us + HEARTBEAT_US;

    hello_t hello = {
        .fw_version = TALLY_FW_VERSION,
        .reset_reason = (uint8_t)esp_reset_reason(),
        .atten = (uint8_t)ACCELEROMETER_ATTEN,
    };
    memcpy(hello.mac, device_mac, sizeof(hello.mac));
    session_t *s = sampler_lock();
    hello.active_set_id = session_active_set_id(s);
    hello.active_next_seq = session_next_seq(s);
    sampler_unlock();

    uint8_t out[FRAME_MAX_BYTES];
    ESP_LOGI(TAG, "client connected; active set %lu next seq %lu",
             (unsigned long)hello.active_set_id, (unsigned long)hello.active_next_seq);
    send_frame(c, out, frame_hello(out, &hello));
}

// Returns false if the connection must be dropped.
static bool handle_command(client_t *c, const command_t *cmd)
{
    session_t *s = sampler_lock();
    bool keep = true;
    switch (cmd->type) {
    case FRAME_START:
        if (session_start(s, cmd->set_id, cmd->side)) c->streaming = true;
        else ESP_LOGW(TAG, "START %lu ignored: a set is already active", (unsigned long)cmd->set_id);
        break;
    case FRAME_STOP:
        if (!session_stop(s, cmd->set_id)) ESP_LOGW(TAG, "STOP %lu ignored", (unsigned long)cmd->set_id);
        break;
    case FRAME_ABORT:
        if (session_abort(s, cmd->set_id)) c->streaming = true;
        else ESP_LOGW(TAG, "ABORT %lu ignored", (unsigned long)cmd->set_id);
        break;
    case FRAME_RESUME:
        switch (session_resume(s, cmd->set_id, cmd->next_seq)) {
        case RESUME_OK: c->streaming = true; break;
        case RESUME_OVERRUN: c->streaming = true; ESP_LOGW(TAG, "RESUME past the ring: ring_overrun"); break;
        case RESUME_INVALID: keep = false; break;
        }
        break;
    }
    sampler_unlock();
    return keep;
}

static void read_client(client_t *c)
{
    int n = recv(c->fd, c->rx + c->rx_len, sizeof(c->rx) - c->rx_len, 0);
    if (n <= 0) {
        drop_client(c, n == 0 ? "peer closed" : "recv failed");
        return;
    }
    c->rx_len += (size_t)n;
    while (c->fd >= 0) {
        command_t cmd;
        int used = frame_parse_command(c->rx, c->rx_len, &cmd);
        if (used < 0) {
            drop_client(c, "malformed inbound frame");
            return;
        }
        if (used == 0) break;
        memmove(c->rx, c->rx + used, c->rx_len - (size_t)used);
        c->rx_len -= (size_t)used;
        if (!handle_command(c, &cmd)) drop_client(c, "RESUME for a set or sequence this board does not have");
    }
}

static void send_set_frames(client_t *c, int64_t now_us)
{
    uint8_t out[FRAME_MAX_BYTES];
    for (int frames = 0; frames < MAX_FRAMES_PER_POLL && c->fd >= 0; frames++) {
        session_t *s = sampler_lock();
        size_t len = 0;
        enum { NONE, STARTED, SAMPLES, END } kind = NONE;
        uint32_t set_id = s->set_id, first_seq = 0, count = 0;
        uint8_t n = 0, reason = 0;
        if (s->state != SESSION_IDLE && s->started_pending) {
            len = frame_set_started(out, s->set_id, s->side);
            kind = STARTED;
        } else {
            wire_sample_t batch[WIRE_SAMPLES_PER_FRAME];
            n = session_peek(s, &first_seq, batch);
            bool full = n == WIRE_SAMPLES_PER_FRAME;
            bool flush = n > 0 && (s->state == SESSION_ENDING || now_us - c->last_samples_us >= SAMPLES_FLUSH_US);
            if (full || flush) {
                len = frame_samples(out, s->set_id, first_seq, batch, n);
                kind = SAMPLES;
            } else if (n == 0 && session_end_due(s, &set_id, &reason, &count)) {
                len = frame_set_end(out, set_id, reason, count);
                kind = END;
            }
        }
        sampler_unlock();
        if (kind == NONE || !send_frame(c, out, len)) return;

        s = sampler_lock();
        if (kind == STARTED && s->set_id == set_id) s->started_pending = false;
        if (kind == SAMPLES) session_commit(s, first_seq, n);
        if (kind == END) session_end_delivered(s, set_id);
        sampler_unlock();
        if (kind == SAMPLES) c->last_samples_us = now_us;
        if (kind == END) {
            ESP_LOGI(TAG, "SET_END %lu reason %u count %lu", (unsigned long)set_id, reason, (unsigned long)count);
            c->streaming = false;
            return;
        }
    }
}

static void send_heartbeat(client_t *c)
{
    session_t *s = sampler_lock();
    uint16_t fill = session_ring_fill(s);
    sampler_unlock();
    uint32_t heap_kb = esp_get_minimum_free_heap_size() / 1024;
    uint8_t out[FRAME_MAX_BYTES];
    size_t len = frame_heartbeat(out, (uint32_t)(esp_timer_get_time() / 1000), fill,
                                 (uint16_t)(heap_kb > 0xFFFF ? 0xFFFF : heap_kb));
    send_frame(c, out, len);
}

static void link_task(void *arg)
{
    (void)arg;
    int listen_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    configASSERT(listen_fd >= 0);
    int one = 1;
    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port = htons(TALLY_TCP_PORT),
        .sin_addr.s_addr = htonl(INADDR_ANY), // the SoftAP is the only interface: 192.168.4.1
    };
    ESP_ERROR_CHECK(bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr)) == 0 ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(listen(listen_fd, 1) == 0 ? ESP_OK : ESP_FAIL);
    ESP_LOGI(TAG, "listening on TCP %d", TALLY_TCP_PORT);

    client_t client = {.fd = -1};
    while (true) {
        fd_set readable;
        FD_ZERO(&readable);
        FD_SET(listen_fd, &readable);
        int max_fd = listen_fd;
        if (client.fd >= 0) {
            FD_SET(client.fd, &readable);
            if (client.fd > max_fd) max_fd = client.fd;
        }
        struct timeval timeout = {.tv_sec = 0, .tv_usec = POLL_US};
        int ready = select(max_fd + 1, &readable, NULL, NULL, &timeout);
        if (ready < 0 && errno != EINTR) {
            ESP_LOGE(TAG, "select failed: errno %d", errno);
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        if (ready > 0 && FD_ISSET(listen_fd, &readable)) accept_client(listen_fd, &client);
        else if (ready > 0 && client.fd >= 0 && FD_ISSET(client.fd, &readable)) read_client(&client);
        if (client.fd < 0) continue;

        int64_t now_us = esp_timer_get_time();
        if (client.streaming) send_set_frames(&client, now_us);
        if (client.fd >= 0 && now_us >= client.next_heartbeat_us) {
            client.next_heartbeat_us += HEARTBEAT_US;
            if (client.next_heartbeat_us <= now_us) client.next_heartbeat_us = now_us + HEARTBEAT_US;
            send_heartbeat(&client);
        }
    }
}

void link_server_start(const uint8_t mac[6])
{
    memcpy(device_mac, mac, sizeof(device_mac));
    BaseType_t created = xTaskCreatePinnedToCore(link_task, "link", 6144, NULL, 5, NULL, 0);
    configASSERT(created == pdPASS);
}
