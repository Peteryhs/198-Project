#include "session.h"

#include <string.h>

static void end_set(session_t *s, uint8_t reason)
{
    s->state = SESSION_ENDING;
    s->end_reason = reason;
}

void session_reset(session_t *s)
{
    s->state = SESSION_IDLE;
    s->set_id = 0;
    s->side = 0;
    s->end_reason = END_DONE;
    s->started_pending = false;
    s->start_us = 0;
    s->last_us = 0;
    s->taken = 0;
    s->sent = 0;
}

bool session_start(session_t *s, uint32_t set_id, uint8_t side)
{
    if (s->state != SESSION_IDLE || set_id == 0) return false;
    session_reset(s);
    s->state = SESSION_RUNNING;
    s->set_id = set_id;
    s->side = side;
    s->started_pending = true;
    return true;
}

bool session_stop(session_t *s, uint32_t set_id)
{
    if (s->state != SESSION_RUNNING || set_id != s->set_id) return false;
    end_set(s, END_DONE);
    return true;
}

bool session_abort(session_t *s, uint32_t set_id)
{
    if (s->state == SESSION_IDLE || set_id != s->set_id) return false;
    // Clear the ring: unsent samples are discarded, so SET_END reports what the phone holds.
    // A still-pending SET_STARTED goes out first; the phone rejects SET_END for an unstarted set.
    s->taken = s->sent;
    end_set(s, END_ABORTED);
    return true;
}

resume_result_t session_resume(session_t *s, uint32_t set_id, uint32_t next_seq)
{
    if (s->state == SESSION_IDLE || set_id != s->set_id || next_seq > s->taken) return RESUME_INVALID;
    // A still-pending SET_STARTED never reached any phone, so it stays pending and goes out first.
    if (s->taken - next_seq > WIRE_RING_CAP) {
        // next_seq already left the ring. End at the phone's position: no gap, no skipped samples.
        s->taken = next_seq;
        s->sent = next_seq;
        end_set(s, END_RING_OVERRUN);
        return RESUME_OVERRUN;
    }
    s->sent = next_seq;
    return RESUME_OK;
}

void session_tick(session_t *s, int64_t now_us, const uint16_t mv[WIRE_CHANNELS])
{
    if (s->state != SESSION_RUNNING) return;
    if (s->taken == 0) {
        s->start_us = now_us;
    } else if (now_us - s->last_us > SESSION_MAX_TICK_GAP_US || now_us - s->last_us < 1000) {
        // Under 1 ms after a late wake, t_us / 1000 could repeat, which the phone rejects outright.
        end_set(s, END_TIMING);
        return;
    }
    if (s->taken - s->sent >= WIRE_RING_CAP) {
        end_set(s, END_RING_OVERRUN);
        return;
    }
    wire_sample_t *slot = &s->ring[s->taken % WIRE_RING_CAP];
    slot->t_us = (uint32_t)(now_us - s->start_us);
    memcpy(slot->mv, mv, sizeof(slot->mv));
    s->last_us = now_us;
    s->taken++;
    if (s->taken >= WIRE_SET_CAP) end_set(s, END_OVERFLOW);
}

uint8_t session_peek(const session_t *s, uint32_t *first_seq, wire_sample_t out[WIRE_SAMPLES_PER_FRAME])
{
    if (s->state == SESSION_IDLE || s->started_pending) return 0;
    uint32_t backlog = s->taken - s->sent;
    uint8_t n = backlog < WIRE_SAMPLES_PER_FRAME ? (uint8_t)backlog : WIRE_SAMPLES_PER_FRAME;
    for (uint8_t i = 0; i < n; i++) out[i] = s->ring[(s->sent + i) % WIRE_RING_CAP];
    *first_seq = s->sent;
    return n;
}

void session_commit(session_t *s, uint32_t first_seq, uint8_t n)
{
    // A RESUME or ABORT may have moved s->sent while the frame was on the wire.
    if (s->state != SESSION_IDLE && first_seq == s->sent && s->taken - s->sent >= n) s->sent += n;
}

bool session_end_due(const session_t *s, uint32_t *set_id, uint8_t *reason, uint32_t *count)
{
    if (s->state != SESSION_ENDING || s->sent != s->taken || s->started_pending) return false;
    *set_id = s->set_id;
    *reason = s->end_reason;
    *count = s->sent;
    return true;
}

void session_end_delivered(session_t *s, uint32_t set_id)
{
    if (s->state == SESSION_ENDING && s->set_id == set_id && s->sent == s->taken) session_reset(s);
}

uint32_t session_active_set_id(const session_t *s)
{
    return s->state == SESSION_IDLE ? 0 : s->set_id;
}

uint32_t session_next_seq(const session_t *s)
{
    return s->state == SESSION_IDLE ? 0 : s->taken;
}

uint16_t session_ring_fill(const session_t *s)
{
    return s->state == SESSION_IDLE ? 0 : (uint16_t)(s->taken - s->sent);
}
