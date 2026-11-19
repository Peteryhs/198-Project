#ifndef SAMPLER_H
#define SAMPLER_H

#include "session.h"

// Starts the 10 ms esp_timer and the sampling task pinned to core 1 (Wi-Fi stays on core 0).
void sampler_start(void);

// The session is shared between the sampling task and the link server. Hold the lock for every
// session_* call and release it before any socket I/O.
session_t *sampler_lock(void);
void sampler_unlock(void);

#endif
