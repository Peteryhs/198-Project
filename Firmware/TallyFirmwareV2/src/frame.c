#include "frame.h"

static uint8_t *put_u8(uint8_t *p, uint8_t v)
{
    *p++ = v;
    return p;
}

static uint8_t *put_u16(uint8_t *p, uint16_t v)
{
    *p++ = (uint8_t)v;
    *p++ = (uint8_t)(v >> 8);
    return p;
}

static uint8_t *put_u32(uint8_t *p, uint32_t v)
{
    for (int i = 0; i < 4; i++) *p++ = (uint8_t)(v >> (8 * i));
    return p;
}

static uint16_t get_u16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

static uint32_t get_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

// CRC-32/IEEE (reflected 0xEDB88320, init and xorout 0xFFFFFFFF): the same value as
// zlib.crc32 and java.util.zip.CRC32. Bitwise, because 1.8 kB/s does not justify a table.
uint32_t frame_crc32(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; bit++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

static uint8_t *begin(uint8_t *out, uint8_t type, uint16_t payload_len)
{
    out[0] = 0x54; // 'T'
    out[1] = 0x59; // 'Y'
    out[2] = 1;    // version
    out[3] = type;
    put_u16(out + 4, payload_len);
    return out + FRAME_HEADER_BYTES;
}

static size_t finish(uint8_t *out, const uint8_t *end)
{
    size_t payload_len = (size_t)(end - out) - FRAME_HEADER_BYTES;
    put_u32((uint8_t *)end, frame_crc32(out + 2, 4 + payload_len));
    return FRAME_HEADER_BYTES + payload_len + FRAME_CRC_BYTES;
}

size_t frame_hello(uint8_t *out, const hello_t *h)
{
    uint8_t *p = begin(out, FRAME_HELLO, 27);
    p = put_u16(p, h->fw_version);
    for (int i = 0; i < 6; i++) p = put_u8(p, h->mac[i]);
    p = put_u8(p, h->reset_reason);
    p = put_u32(p, WIRE_SAMPLE_PERIOD_US);
    p = put_u8(p, WIRE_CHANNELS);
    p = put_u8(p, h->atten);
    p = put_u16(p, (uint16_t)WIRE_SET_CAP);
    p = put_u16(p, (uint16_t)WIRE_RING_CAP);
    p = put_u32(p, h->active_set_id);
    p = put_u32(p, h->active_next_seq);
    return finish(out, p);
}

size_t frame_set_started(uint8_t *out, uint32_t set_id, uint8_t side)
{
    uint8_t *p = begin(out, FRAME_SET_STARTED, 5);
    p = put_u32(p, set_id);
    p = put_u8(p, side);
    return finish(out, p);
}

size_t frame_samples(uint8_t *out, uint32_t set_id, uint32_t first_seq,
                     const wire_sample_t *samples, uint8_t n)
{
    uint8_t *p = begin(out, FRAME_SAMPLES, (uint16_t)(9 + 16 * n));
    p = put_u32(p, set_id);
    p = put_u32(p, first_seq);
    p = put_u8(p, n);
    for (int i = 0; i < n; i++) {
        p = put_u32(p, samples[i].t_us);
        for (int ch = 0; ch < WIRE_CHANNELS; ch++) p = put_u16(p, samples[i].mv[ch]);
    }
    return finish(out, p);
}

size_t frame_set_end(uint8_t *out, uint32_t set_id, uint8_t reason, uint32_t sample_count)
{
    uint8_t *p = begin(out, FRAME_SET_END, 9);
    p = put_u32(p, set_id);
    p = put_u8(p, reason);
    p = put_u32(p, sample_count);
    return finish(out, p);
}

size_t frame_heartbeat(uint8_t *out, uint32_t uptime_ms, uint16_t ring_fill, uint16_t min_free_heap_kb)
{
    uint8_t *p = begin(out, FRAME_HEARTBEAT, 8);
    p = put_u32(p, uptime_ms);
    p = put_u16(p, ring_fill);
    p = put_u16(p, min_free_heap_kb);
    return finish(out, p);
}

static uint16_t command_len(uint8_t type)
{
    switch (type) {
    case FRAME_START: return 5;
    case FRAME_STOP:
    case FRAME_ABORT: return 4;
    case FRAME_RESUME: return 8;
    default: return 0;
    }
}

size_t frame_command(uint8_t *out, uint8_t type, uint32_t set_id, uint32_t arg)
{
    uint8_t *p = begin(out, type, command_len(type));
    p = put_u32(p, set_id);
    if (type == FRAME_START) p = put_u8(p, (uint8_t)arg);
    if (type == FRAME_RESUME) p = put_u32(p, arg);
    return finish(out, p);
}

int frame_parse_command(const uint8_t *buf, size_t len, command_t *cmd)
{
    if (len >= 1 && buf[0] != 0x54) return -1;
    if (len >= 2 && buf[1] != 0x59) return -1;
    if (len >= 3 && buf[2] != 1) return -1;
    if (len < FRAME_HEADER_BYTES) return 0;
    uint8_t type = buf[3];
    uint16_t payload_len = get_u16(buf + 4);
    if (payload_len > FRAME_MAX_PAYLOAD) return -1;
    uint16_t expected = command_len(type);
    if (expected == 0 || payload_len != expected) return -1;
    size_t total = FRAME_HEADER_BYTES + payload_len + FRAME_CRC_BYTES;
    if (len < total) return 0;
    if (frame_crc32(buf + 2, 4 + payload_len) != get_u32(buf + FRAME_HEADER_BYTES + payload_len)) return -1;

    const uint8_t *p = buf + FRAME_HEADER_BYTES;
    cmd->type = type;
    cmd->set_id = get_u32(p);
    cmd->side = 0;
    cmd->next_seq = 0;
    if (cmd->set_id == 0) return -1;
    if (type == FRAME_START) {
        cmd->side = p[4];
        if (cmd->side != 'L' && cmd->side != 'R') return -1;
    }
    if (type == FRAME_RESUME) {
        cmd->next_seq = get_u32(p + 4);
        if (cmd->next_seq > WIRE_SET_CAP) return -1;
    }
    return (int)total;
}
