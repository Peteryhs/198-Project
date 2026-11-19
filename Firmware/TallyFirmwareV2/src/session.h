#ifndef SESSION_H
#define SESSION_H

// Set lifecycle and the 3,000-sample ring. Pure C and not thread-safe: sampler.c wraps every
// call in one mutex. Kept free of ESP-IDF so firmware/tools/host_check.c can drive it.

#include <stdbool.h>
#include <stdint.h>

#include "frame.h"

#define SESSION_MAX_TICK_GAP_US 15000

typedef enum {
    SESSION_IDLE,    // no set; HELLO reports active_set_id 0
    SESSION_RUNNING, // sampling into the ring
    SESSION_ENDING,  // sampling stopped; unsent samples drain, then SET_END, then IDLE
} session_state_t;

typedef struct {
    session_state_t state;
    uint32_t set_id;
    uint8_t side;
    uint8_t end_reason;
    bool started_pending; // SET_STARTED not yet sent
    int64_t start_us;     // tick time of sample 0
    int64_t last_us;      // tick time of the newest sample
    uint32_t taken;       // samples written = next sequence number to sample
    uint32_t sent;        // next sequence number to send; [sent, taken) is the unsent backlog
    wire_sample_t ring[WIRE_RING_CAP];
} session_t;

typedef enum { RESUME_OK, RESUME_OVERRUN, RESUME_INVALID } resume_result_t;

void session_reset(session_t *s);
bool session_start(session_t *s, uint32_t set_id, uint8_t side);
bool session_stop(session_t *s, uint32_t set_id);
bool session_abort(session_t *s, uint32_t set_id);
resume_result_t session_resume(session_t *s, uint32_t set_id, uint32_t next_seq);

// One 10 ms tick. Ignored unless RUNNING. Ends the set on a >15 ms gap (timing), a full ring of
// unsent samples (ring_overrun, never overwriting), or the 60,000th sample (overflow).
void session_tick(session_t *s, int64_t now_us, const uint16_t mv[WIRE_CHANNELS]);

// Copies up to 10 unsent samples starting at s->sent. Returns n; does not advance s->sent.
uint8_t session_peek(const session_t *s, uint32_t *first_seq, wire_sample_t out[WIRE_SAMPLES_PER_FRAME]);
// Call after a SAMPLES frame of n samples from first_seq was fully sent.
void session_commit(session_t *s, uint32_t first_seq, uint8_t n);

// True when ENDING and the backlog is empty; fills the SET_END fields.
bool session_end_due(const session_t *s, uint32_t *set_id, uint8_t *reason, uint32_t *count);
// Call after SET_END was fully sent.
void session_end_delivered(session_t *s, uint32_t set_id);

uint32_t session_active_set_id(const session_t *s);
uint32_t session_next_seq(const session_t *s);
uint16_t session_ring_fill(const session_t *s);

#endif
