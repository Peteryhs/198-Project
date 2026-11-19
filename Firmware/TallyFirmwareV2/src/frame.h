#ifndef FRAME_H
#define FRAME_H

// ESP32-WIRE-V1 framing (app/docs/ESP32-WIRE-V1.md). Pure C, no ESP-IDF dependency,
// so firmware/tools/host_check.c compiles this exact file on a laptop.

#include <stddef.h>
#include <stdint.h>

#define FRAME_HEADER_BYTES 6
#define FRAME_CRC_BYTES 4
#define FRAME_MAX_PAYLOAD 512
#define FRAME_MAX_BYTES (FRAME_HEADER_BYTES + FRAME_MAX_PAYLOAD + FRAME_CRC_BYTES)

#define WIRE_SAMPLE_PERIOD_US 10000u
#define WIRE_CHANNELS 6
#define WIRE_SET_CAP 60000u
#define WIRE_RING_CAP 3000u
#define WIRE_SAMPLES_PER_FRAME 10

enum {
    FRAME_HELLO = 0x01,
    FRAME_SET_STARTED = 0x02,
    FRAME_SAMPLES = 0x03,
    FRAME_SET_END = 0x04,
    FRAME_HEARTBEAT = 0x05,
    FRAME_START = 0x81,
    FRAME_STOP = 0x82,
    FRAME_ABORT = 0x83,
    FRAME_RESUME = 0x84,
};

enum {
    END_DONE = 0,
    END_ABORTED = 1,
    END_OVERFLOW = 2,
    END_TIMING = 3,
    END_RING_OVERRUN = 4,
};

typedef struct {
    uint32_t t_us;
    uint16_t mv[WIRE_CHANNELS];
} wire_sample_t;

typedef struct {
    uint16_t fw_version;
    uint8_t mac[6];
    uint8_t reset_reason;
    uint8_t atten;
    uint32_t active_set_id;
    uint32_t active_next_seq;
} hello_t;

// Every encoder writes a complete frame into out (>= FRAME_MAX_BYTES) and returns its length.
size_t frame_hello(uint8_t *out, const hello_t *h);
size_t frame_set_started(uint8_t *out, uint32_t set_id, uint8_t side);
size_t frame_samples(uint8_t *out, uint32_t set_id, uint32_t first_seq,
                     const wire_sample_t *samples, uint8_t n);
size_t frame_set_end(uint8_t *out, uint32_t set_id, uint8_t reason, uint32_t sample_count);
size_t frame_heartbeat(uint8_t *out, uint32_t uptime_ms, uint16_t ring_fill, uint16_t min_free_heap_kb);
// Phone->device commands; the board never sends these, host_check uses them for the cross-check.
size_t frame_command(uint8_t *out, uint8_t type, uint32_t set_id, uint32_t arg);

typedef struct {
    uint8_t type;
    uint32_t set_id;
    uint8_t side;      // START only
    uint32_t next_seq; // RESUME only
} command_t;

// Parses one phone command from buf[0..len).
// Returns bytes consumed (> 0), 0 if more bytes are needed, or -1 if the input is malformed
// (bad magic/version/type/length/CRC, zero set id, bad side): the caller drops the connection.
int frame_parse_command(const uint8_t *buf, size_t len, command_t *cmd);

uint32_t frame_crc32(const uint8_t *data, size_t len);

#endif
